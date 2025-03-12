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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    # Get base URL from request
    base_url = str(request.base_url).rstrip('/')
    
    # Base URLs that are always present
    base_urls = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/history", "changefreq": "hourly", "priority": "0.8"}
    ]
    
    try:
        # Get all claim IDs from database
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, timestamp FROM cache ORDER BY timestamp DESC LIMIT 1000"
            ) as cursor:
                claims = await cursor.fetchall()

                # Add claim URLs to sitemap
                claim_urls = [
                    {
                        "loc": f"{base_url}/claim/{claim[0]}/view",
                        "lastmod": datetime.fromtimestamp(claim[1]).strftime("%Y-%m-%d"),
                        "changefreq": "weekly",
                        "priority": "0.6"
                    }
                    for claim in claims
                ]

                # Generate sitemap XML
                sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
                sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                
                # Add all URLs
                for url in base_urls + claim_urls:
                    sitemap += '  <url>\n'
                    sitemap += f'    <loc>{url["loc"]}</loc>\n'
                    if "lastmod" in url:
                        sitemap += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
                    sitemap += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
                    sitemap += f'    <priority>{url["priority"]}</priority>\n'
                    sitemap += '  </url>\n'
                
                sitemap += '</urlset>'
                
                return Response(content=sitemap, media_type="application/xml")
    except Exception as e:
        logger.error("Error generating sitemap: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Serve HTML pages with caching headers
@app.get("/")
async def read_root():
    return FileResponse(
        "static/index.html",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

@app.get("/claim/{claim_id}/view")
async def read_claim_page(claim_id: str = Path(..., min_length=8, max_length=8)):
    return FileResponse(
        "static/claim.html",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

@app.get("/history")
async def get_history_page():
    return FileResponse(
        "static/history.html",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "index, follow"
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = "factcheck.db"

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

# Helper function to interact with OpenRouter API
async def get_ai_response(query: str) -> dict:
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds

    # Get OpenRouter API key from environment variables
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    logger.info("Starting API request...")
    logger.info(f"API Key present: {bool(OPENROUTER_API_KEY)}")
    
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Islam Fact Checker",
        "Content-Type": "application/json"
    }
    logger.info("Headers configured:", headers)

    # Prompt template for fact-checking
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
            
            logger.info(f"Sending request to OpenRouter API (attempt {attempt + 1}/{MAX_RETRIES})...")
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
                
            response.raise_for_status()
            result = response.json()
            logger.info(result)
            
            # If we get here, the request was successful
            # Extract the content from the response
            content = result['choices'][0]['message']['content']
            logger.info("Response content: %s", content)
                
            # Remove LaTeX \boxed{} if present
            if content.startswith('\\boxed{'):
                content = content[6:].strip()  # Remove \boxed{ and any whitespace
            # Parse the content using ast.literal_eval which is more forgiving
            try:
                # Clean up the string to ensure it's a valid Python literal
                content = content.replace('\n', '').replace('    ', '')
                # Use literal_eval to parse the string into a Python dict
                parsed = ast.literal_eval(content)
                # Validate the response structure
                if not all(key in parsed for key in ['answer', 'sources', 'classification']):
                    raise ValueError("Missing required fields in response")
                return parsed
            except (ValueError, SyntaxError) as e:
                logger.error("Failed to parse response: %s\nContent: %s", str(e), content)
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
                continue
                
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Error response: {e.response.text}")
            
            # If this was our last attempt, raise a specific error
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(
                    status_code=503,
                    detail="Service temporarily unavailable. The AI service is not responding after multiple attempts. Please try again later."
                )
            
            # Otherwise, wait with exponential backoff before retrying
            retry_delay = INITIAL_RETRY_DELAY * (2 ** attempt)  # exponential backoff
            logger.info(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s\n%s", str(exc), traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "traceback": traceback.format_exc()
        }
    )

# Input validation models
class ClaimId(BaseModel):
    id: str = Field(
        ..., 
        min_length=8, 
        max_length=8, 
        pattern=r'^[a-zA-Z0-9]+$',
        description="8-character alphanumeric claim ID"
    )

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, le=10, description="Page number (1-10)")
    per_page: int = Field(10, ge=1, le=100, description="Items per page (1-100)")

class QueryText(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        pattern=r'^[\w\s.,!?\'"-]+$'
    )

@app.get("/claim/{claim_id}")
async def get_claim(claim_id: str = Path(..., min_length=8, max_length=8, pattern=r'^[a-zA-Z0-9]+$')):
    try:
        # Validate claim ID format (already done by Pydantic)
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
async def factcheck(query: QueryText):
    try:
        # Log sanitized input
        logger.info("Received factcheck request: %s", query.text)
        
        # Remove any potential dangerous characters
        sanitized_text = query.text.strip()
        
        # Check cache first
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, response, timestamp FROM cache WHERE query = ?",
                (query.text,)
            ) as cursor:
                result = await cursor.fetchone()
                
                # If found in cache and less than 24 hours old
                if result and (time.time() - result[2]) < 86400:
                    logger.info("Returning cached response")
                    cached_response = json.loads(result[1])
                    cached_response['id'] = result[0]  # Include the ID in response
                    return cached_response

        # Get response from AI
        logger.info("Getting fresh response from AI")
        response = await get_ai_response(query.text)
        
        # Cache the response
        logger.info("Caching the response")
        async with aiosqlite.connect(DB_PATH) as db:
            # Generate a unique ID for the claim (first 8 chars of sha256)
            claim_id = hashlib.sha256(query.text.encode()).hexdigest()[:8]
            
            # Store with unique ID
            await db.execute(
                "INSERT OR REPLACE INTO cache (id, query, response, timestamp) VALUES (?, ?, ?, ?)",
                (claim_id, query.text, json.dumps(response), time.time())
            )
            await db.commit()
            
            # Add the ID to response
            response['id'] = claim_id
            
        return response

    except Exception as e:
        logger.error("Error in factcheck: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}\n{traceback.format_exc()}")

@app.get("/api/history")
async def get_history(params: PaginationParams = Depends()):
    try:
        # Parameters are already validated by Pydantic
        offset = (params.page - 1) * params.per_page

        async with aiosqlite.connect(DB_PATH) as db:
            # Get total count
            async with db.execute("SELECT COUNT(*) FROM cache") as cursor:
                total_items = (await cursor.fetchone())[0]

            # Get paginated results
            async with db.execute(
                """
                SELECT id, query, response 
                FROM cache 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
                """,
                (params.per_page, offset)
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
                        "current_page": params.page,
                        "per_page": params.per_page,
                        "total_items": total_items,
                        "total_pages": max(1, (total_items + params.per_page - 1) // params.per_page)
                    }
                }
                
    except Exception as e:
        logger.error("Error retrieving history: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
