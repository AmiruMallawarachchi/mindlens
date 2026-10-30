# Local development runbook

> **Hosted deployment is not this file.** The current public deployment target is
> Render (backend) + Vercel (frontend), documented in
> [V2_HOSTED_DEPLOYMENT.md](V2_HOSTED_DEPLOYMENT.md). This page only covers
> running MindLens on a developer machine. The old ngrok and Hugging Face Space
> deployment instructions were removed because V2 has no local model weights or
> Chroma index to host.

## Prerequisites

- Python 3.11 and the repo's `.venv`.
- Node.js 22 and `frontend/node_modules` (`npm ci`).
- MongoDB running locally (or a `MONGODB_URL` pointing at Atlas).
- A Groq key if you want real replies; without one the backend serves stubs and
  `/ready` correctly reports `stub_mode`.

## 1. Start MongoDB

The backend fails closed if Mongo is unreachable. On Windows, start the service
from an elevated PowerShell:

```powershell
Start-Service MongoDB
Get-Service MongoDB
```

`Get-Service` must show `Running`, not `Stopped`.

## 2. Start the backend

```bash
cd backend
../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

V2 boots in seconds; there are no local models or vector index to preload.
`--reload` is unreliable on this Windows setup, so restart the process after
backend edits.

Confirm it is genuinely usable:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

`/health` is liveness only. `/ready` pings Mongo and checks that Groq is
configured for real inference. If `USE_OPENAI_STUBS=true`, `/ready` returns 503
with `inference.status = "stub_mode"` on purpose — a stub backend must not claim
to be ready. Pinecone is reported as configuration with `mode: "fail_soft"`;
retrieval failure degrades a turn but does not make the API unready.

If MongoDB is not running, the backend exits during startup with a
`ServerSelectionTimeoutError` naming `localhost:27017`. That is the signal to
start Mongo and retry, not a code problem to chase.

## 3. Start the frontend

`frontend/.env.local` should point at the local API:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Then:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`.

Do **not** set `NEXT_PUBLIC_PREVIEW_AUTH=1` outside local development. It
bypasses the auth gate and would let every visitor into chat as a fake logged-in
user. It must never be set in a Vercel environment.

## 4. Optional: expose the local API with ngrok

This is for testing from another device, not the deployment. The public app is
on Render.

```bash
ngrok http 8000
```

Set `NEXT_PUBLIC_API_BASE_URL` to the printed HTTPS URL and add that origin to
`CORS_ORIGINS`. The frontend derives the WebSocket URL from the API URL. Free
ngrok domains can change; a stale URL looks exactly like a backend outage.

## 5. Run the checks

```bash
cd backend
APP_ENV=test DEBUG=false USE_OPENAI_STUBS=true \
  ../.venv/Scripts/python -m pytest tests -q
../.venv/Scripts/python -m ruff check app tests
```

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Troubleshooting

- **MongoDB service will not start / backend exits with
  `ServerSelectionTimeoutError`:** start Mongo from an elevated shell and retry.
  This is an environment problem, not a code problem.
- **Login screen says "Couldn't reach MindLens":** check that the backend is
  running and that `NEXT_PUBLIC_API_BASE_URL` matches its origin. A stale ngrok
  URL produces the same message.
- **401 after 15 minutes:** the access token is short-lived by design; the
  refresh cookie should renew it. In cross-site production, the cookie needs
  `SameSite=None; Secure` and the Vercel origin must be in `CORS_ORIGINS`.
- **`/ready` returns 503 in development:** check `USE_OPENAI_STUBS` and
  `GROQ_API_KEY`. Stub mode is intentionally not "ready".
