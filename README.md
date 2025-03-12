# Islam Fact Checker

A fast, AI-powered chatbot specialized in fact-checking claims about Islam. Built with FastAPI and OpenRouter API.

## Features

- 🤖 AI-powered fact-checking using OpenRouter API (Deepseek R1 Zero model)
- 📚 Provides context from Quran, hadiths, and scholarly sources
- 🔍 Clean, responsive chat interface
- 🔎 Search functionality for past fact-checks
- 🐦 Twitter sharing integration
- 💾 SQLite-based caching system
- 🌐 Multi-language support with auto-detection

## Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/islam-fact-checker.git
cd islam-fact-checker
```

2. Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
# Create .env file
echo "OPENROUTER_API_KEY=your_api_key_here" > .env
```

5. Run the application
```bash
cd app
uvicorn main:app --reload
```

6. Open your browser and navigate to [http://localhost:8000](http://localhost:8000)

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### API Endpoints

- `POST /factcheck`: Submit a claim for fact-checking
  ```json
  {
    "text": "Your claim here",
    "language": "optional language code"
  }
  ```

- `GET /search?q=query`: Search through past fact-checks

## Deployment

### Requirements

- Python 3.8+
- OpenRouter API key
- (Optional) Domain name for production deployment

### Production Deployment

1. Set secure environment variables
2. Update CORS settings in main.py for your domain
3. Use a production ASGI server (e.g., Gunicorn with Uvicorn workers)
4. Set up SSL/TLS certificates
5. Configure reverse proxy (e.g., Nginx)

Example Nginx configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /path/to/your/app/static;
        expires 1h;
        add_header Cache-Control "public, no-transform";
    }
}
```

## Architecture

- Frontend: HTML, CSS, JavaScript
- Backend: FastAPI (Python)
- AI: OpenRouter API with Deepseek R1 Zero
- Database: SQLite
- Caching: 24-hour response caching
- Language: Auto-detection and multi-language support

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenRouter](https://openrouter.ai/)
- [Deepseek](https://deepseek.ai/)
