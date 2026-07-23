# MindLens

MindLens is a FastAPI backend and web client for privacy-conscious mental-health
support. The backend combines deterministic crisis screening, isolated ML
classifiers, retrieval from a curated therapy corpus, and a multi-agent response
pipeline. It is support software, not a replacement for professional care or
emergency services.

## Repository

- `backend/app`: API, WebSocket chat, authentication, agents, models, and RAG
- `backend/tests`: unit and integration coverage
- `frontend`: web client (deployed separately to Vercel)
- `render.yaml`: Render Blueprint for the backend and persistent Chroma storage
- `docs/API.md`: HTTP/WebSocket contract
- `docs/DEPLOYMENT.md`: Render and Vercel deployment runbook

## Backend Development

Requires Python 3.11 and MongoDB.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python backend/run.py
```

The local API listens on `http://127.0.0.1:8000`. Interactive API docs are
available at `/docs` in development only.

## Verification

```powershell
python -m ruff check backend
python -m pytest backend/tests --cov=backend/app --cov-report=term-missing
python -m pip_audit -r requirements.txt
python -m bandit -q -r backend/app -ll
python -m detect_secrets scan backend/app .env.example render.yaml
```

Production configuration fails closed when secrets, CORS origins, MongoDB, or
the live LLM provider are missing. Start with [.env.example](.env.example) and
follow [the deployment runbook](docs/DEPLOYMENT.md) before creating the Render
service.
