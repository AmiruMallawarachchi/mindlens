# MindLens

MindLens is a FastAPI backend and web client for privacy-conscious mental-health
support. The backend combines deterministic crisis screening, isolated ML
classifiers, retrieval from a curated therapy corpus, and a multi-agent response
pipeline. It is support software, not a replacement for professional care or
emergency services.

## Repository

- `backend/app`: API, WebSocket chat, authentication, agents, models, and RAG
- `backend/scripts`: one-off maintenance scripts — currently just
  `make_admin.py`, which promotes an already-registered user to admin (see
  Admin dashboard, below)
- `backend/tests`: unit and integration coverage
- `frontend`: web client (deployed separately to Vercel)
- `render.yaml`: documented Render Blueprint alternative (not the primary
  deployment — see docs/DEPLOYMENT.md for why)
- `docs/API.md`: HTTP/WebSocket contract
- `docs/DEPLOYMENT.md`: the full deployment runbook — what's actually live
  today (a local backend through an ngrok tunnel + Vercel), the Hugging
  Face Space alternative that's designed but not deployed, and the release
  checklist

## Running the full stack locally

Three things, started in this order. This is also what the deployed
frontend at `mindlens-theta.vercel.app` talks to — there is no separate
hosted backend; see "The Vercel deployment", below.

### 1. MongoDB

In an **elevated** PowerShell — a normal shell fails with "Cannot open
MongoDB service on computer '.'":

```powershell
Start-Service MongoDB
```

This has been observed to **not survive a machine sleep or restart**, even
with its start type set to `Automatic`. If the backend fails to boot with a
`ServerSelectionTimeoutError` naming `localhost:27017`, this is why —
restart Mongo and restart the backend, it isn't a code problem.

### 2. Backend

Requires Python 3.11.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item backend\.env.example backend\.env
python backend/run.py
```

The API listens on `http://127.0.0.1:8000`. Interactive docs are at `/docs`
in development only. First boot takes ~15–20s while five ML models and the
RAG index load. Confirm it's actually healthy — **`/ready`, not
`/health`** — before trusting anything downstream:

```powershell
curl http://127.0.0.1:8000/ready
```

`/health` only proves the process is up; `/ready` is the one that actually
checked MongoDB and all five classifiers. `--reload` does **not** reliably
fire on this Windows setup — if backend behaviour doesn't match the source
after an edit, stop the process and start it again rather than trusting the
flag.

### 3. Frontend

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

## The Vercel deployment

`mindlens-theta.vercel.app` is a **frontend-only** deployment. There is no
separately hosted backend behind it — it talks to the same local backend
from step 2 above, reached through a permanent ngrok tunnel
(`docs/DEPLOYMENT.md` has the full setup). Practically:

- **The deployed site only works while your local backend and the tunnel
  are both running.** Nobody else can use it if your machine is asleep or
  disconnected — an accepted, deliberate limitation for a project at this
  stage, not an oversight.
- **The tunnel's URL is permanent**, so redeploying is only needed after a
  *frontend code* change, not after every backend restart.
- **To redeploy** (push a frontend change live): `vercel --prod` from the
  **repository root**, not from inside `frontend/` — the Vercel project's
  configured Root Directory is `frontend`, and the CLI applies that on top
  of the current directory, so running it from inside `frontend/` looks
  for `frontend/frontend` and fails.
- Full detail, including what to do if the tunnel's hostname ever has to
  change, is in `docs/DEPLOYMENT.md`.

### Admin dashboard

`https://mindlens-theta.vercel.app/admin` (or `localhost:3000/admin`
locally) — a standalone page, not linked from the product, showing model
status, database connectivity and environment/release. Nothing else: no
user list, no conversations, no memory. Its own sign-in and its own
short-lived token, entirely separate from a normal account login.

No account is an admin by default. Register normally, then promote it:

```powershell
cd backend
..\.venv\Scripts\python scripts\make_admin.py you@example.com
```

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
