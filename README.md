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
- `render.yaml`: documented Render Blueprint alternative (not the primary
  deployment — see docs/DEPLOYMENT.md for why)
- `docs/API.md`: HTTP/WebSocket contract
- `docs/DEPLOYMENT.md`: Hugging Face Space + Vercel deployment runbook

## Backend Development

Requires Python 3.11 and MongoDB.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item backend\.env.example backend\.env
python backend/run.py
```

The local API listens on `http://127.0.0.1:8000`. Interactive API docs are
available at `/docs` in development only.

## Frontend Development

Requires Node 20+.

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local  # set NEXT_PUBLIC_API_BASE_URL if the
                                          # backend isn't on localhost:8000
npm run dev
```

The client listens on `http://localhost:3000`. `/` is the marketing page; the
product lives at `/app`. See `frontend/src/lib/preview.ts` for a way to render
the chat UI without a running backend during frontend-only work — never enable
`NEXT_PUBLIC_PREVIEW_AUTH` outside local dev (it bypasses auth entirely).

## Verification

```powershell
python -m ruff check backend
python -m pytest backend/tests --cov=backend/app --cov-report=term-missing
python -m pip_audit -r requirements.txt
python -m bandit -q -r backend/app -ll
python -m detect_secrets scan backend/app backend/.env.example render.yaml

cd frontend
npm run lint
npm run build
```

Production configuration fails closed when secrets, CORS origins, MongoDB, or
the live LLM provider are missing. Start with
[backend/.env.example](backend/.env.example) and follow
[the deployment runbook](docs/DEPLOYMENT.md) before deploying.
