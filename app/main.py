from fastapi import FastAPI, HTTPException, Request, Path, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import aiosqlite
import sqlite3
import json
import os
from langdetect import detect
import requests
from typing import Optional
from datetime import datetime
import time
import traceback
import logging
import hashlib
import ast

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Islam Fact Checker",
    description="AI-powered Islamic claim verification with scholarly sources",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure static files based on environment
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path - Use environment variable or default to app directory
DB_PATH = os.getenv('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'factcheck.db'))

# Models
class Query(BaseModel):
    text: str
    language: Optional[str] = None

class Response(BaseModel):
    answer: str
    sources: list[str]
    classification: str
    translated: bool = False

# Initialize database
async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                id TEXT PRIMARY KEY,
                query TEXT UNIQUE,
                response TEXT,
                timestamp REAL
            )
        """)
        await db.commit()

@app.on_event("startup")
async def startup_event():
    await init_db()

# Helper function to get static file path
def get_static_file(filename: str) -> str:
    return os.path.join(STATIC_DIR, filename)

# Helper function to interact with OpenRouter API
async def get_ai_response(query: str) -> dict:
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    logger.info("Starting API request...")
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Islam Fact Checker",
        "Content-Type": "application/json"
    }

    system_prompt = """You are a knowledgeable Islamic scholar and fact-checker. 
    Analyze the following claim about Islam, providing:
    1. Full context with relevant Quranic verses or hadiths
    2. Citations from classical scholars
    3. Perspectives from Western academics
    4. A clear classification (Accurate/Misleading/False/Debated)
    Return your response in this exact JSON format:
    {
        "answer": "Your detailed analysis here",
        "sources": ["source1", "source2", "source3"],
        "classification": "one of: Accurate, Misleading, False, or Debated"
    }"""

    prompt = f"Claim to analyze: {query}"

    for attempt in range(MAX_RETRIES):
        try:
            payload = {
                "model": "deepseek/deepseek-r1-zero:free",
                "messages": [
                    {"role": "user", "content": system_prompt + "\n" + prompt}
                ]
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
                
            response.raise_for_status()
            result = response.json()
            
            content = result['choices'][0]['message']['content']
            logger.info("Response content: %s", content)
                
            if content.startswith('\\boxed{'):
                content = content[6:].strip()
            try:
                content = content.replace('\n', '').replace('    ', '')
                parsed = ast.literal_eval(content)
                if not all(key in parsed for key in ['answer', 'sources', 'classification']):
                    raise ValueError("Missing required fields in response")
                return parsed
            except (ValueError, SyntaxError) as e:
                logger.error("Failed to parse response: %s\nContent: %s", str(e), content)
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
                continue
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(
                    status_code=503,
                    detail="Service temporarily unavailable. Please try again later."
                )
            retry_delay = INITIAL_RETRY_DELAY * (2 ** attempt)
            time.sleep(retry_delay)

# SEO Routes
@app.get("/robots.txt")
async def get_robots(request: Request):
    base_url = str(request.base_url).rstrip('/')
    return PlainTextResponse(f"""User-agent: *
Allow: /
Allow: /history
Allow: /claim/*/view

Sitemap: {base_url}/sitemap.xml""")

@app.get("/sitemap.xml")
async def get_sitemap(request: Request):
    base_url = str(request.base_url).rstrip('/')
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, timestamp FROM cache ORDER BY timestamp DESC LIMIT 1000"
            ) as cursor:
                claims = await cursor.fetchall()
                base_urls = [
                    {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
                    {"loc": f"{base_url}/history", "changefreq": "hourly", "priority": "0.8"}
                ]
                claim_urls = [
                    {
                        "loc": f"{base_url}/claim/{claim[0]}/view",
                        "lastmod": datetime.fromtimestamp(claim[1]).strftime("%Y-%m-%d"),
                        "changefreq": "weekly",
                        "priority": "0.6"
                    }
                    for claim in claims
                ]
                sitemap = generate_sitemap(base_urls + claim_urls)
                return Response(content=sitemap, media_type="application/xml")
    except Exception as e:
        logger.error("Error generating sitemap: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

def generate_sitemap(urls):
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        sitemap += '  <url>\n'
        sitemap += f'    <loc>{url["loc"]}</loc>\n'
        if "lastmod" in url:
            sitemap += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
        sitemap += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
        sitemap += f'    <priority>{url["priority"]}</priority>\n'
        sitemap += '  </url>\n'
    sitemap += '</urlset>'
    return sitemap

# Serve HTML pages with caching headers
@app.get("/")
async def read_root():
    return FileResponse(
        get_static_file("index.html"),
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

@app.get("/claim/{claim_id}/view")
async def read_claim_page(claim_id: str = Path(..., min_length=8, max_length=8)):
    return FileResponse(
        get_static_file("claim.html"),
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

@app.get("/history")
async def get_history_page():
    return FileResponse(
        get_static_file("history.html"),
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

@app.get("/claim/{claim_id}")
async def get_claim(claim_id: str = Path(..., min_length=8, max_length=8, pattern=r'^[a-zA-Z0-9]+$')):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT query, response FROM cache WHERE id = ?",
                (claim_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Claim not found")
                
                response_data = json.loads(result[1])
                response_data['id'] = claim_id
                response_data['query'] = result[0]
                return response_data
                
    except Exception as e:
        logger.error("Error retrieving claim: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/factcheck")
async def factcheck(query: Query):
    try:
        sanitized_text = query.text.strip()
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, response, timestamp FROM cache WHERE query = ?",
                (query.text,)
            ) as cursor:
                result = await cursor.fetchone()
                
                if result and (time.time() - result[2]) < 86400:
                    cached_response = json.loads(result[1])
                    cached_response['id'] = result[0]
                    return cached_response

        response = await get_ai_response(query.text)
        
        async with aiosqlite.connect(DB_PATH) as db:
            claim_id = hashlib.sha256(query.text.encode()).hexdigest()[:8]
            
            await db.execute(
                "INSERT OR REPLACE INTO cache (id, query, response, timestamp) VALUES (?, ?, ?, ?)",
                (claim_id, query.text, json.dumps(response), time.time())
            )
            await db.commit()
            
            response['id'] = claim_id
            
        return response

    except Exception as e:
        logger.error("Error in factcheck: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/api/history")
async def get_history(params: Optional[dict] = None):
    try:
        page = int(params.get('page', 1)) if params else 1
        per_page = min(int(params.get('per_page', 10)) if params else 10, 100)
        offset = (page - 1) * per_page

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM cache") as cursor:
                total_items = (await cursor.fetchone())[0]

            async with db.execute(
                """
                SELECT id, query, response 
                FROM cache 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
                """,
                (per_page, offset)
            ) as cursor:
                results = await cursor.fetchall()
                
                claims = []
                for row in results:
                    response_data = json.loads(row[2])
                    claims.append({
                        "id": row[0],
                        "query": row[1],
                        "classification": response_data["classification"]
                    })
                
                return {
                    "claims": claims,
                    "pagination": {
                        "current_page": page,
                        "per_page": per_page,
                        "total_items": total_items,
                        "total_pages": max(1, (total_items + per_page - 1) // per_page)
                    }
                }
                
    except Exception as e:
        logger.error("Error retrieving history: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
