# Deploying MindLens

Everything below is a $0 setup: a free Hugging Face Docker Space for the
backend (models included, in-process, no code changes to how they load),
Vercel Hobby for the frontend, MongoDB Atlas's free M0 tier for the
database, and Groq's free tier for generation.

Render is **not** used for the backend. Its free tier is 512MB against the
five models' ~2.5–3.5GB resident need — a 5–7× gap, not a tuning problem —
and free Render has no persistent disk either. `render.yaml` is kept as a
documented, correct alternative for if that ever changes (see its header
comment for the plan size it actually needs); it isn't part of this path.

## Backend on a Hugging Face Docker Space

### 1. Create the Space

On huggingface.co → **New Space** → pick a name → **SDK: Docker** → choose
visibility → Create. This gives you an empty Space repo at
`https://huggingface.co/spaces/<you>/<space-name>`, with its own git remote.

### 2. Add the frontmatter Hugging Face needs

A Docker Space is configured by YAML frontmatter that must live literally in
`README.md` at the Space repo's root — that's how Spaces work, not a choice
made here. This repo's real `README.md` is the GitHub-facing project
description and deliberately isn't touched: adding HF frontmatter to it
would render as a broken `---` block on GitHub's own page.

The clean way to reconcile the two: a small branch that exists only to carry
the Space's own `README.md`, never merged back and never pushed to GitHub.

```bash
git checkout -b hf-space-deploy main   # or the branch you're deploying
```

Prepend this to the top of `README.md` on that branch only:

```yaml
---
title: Mindlens API
emoji: 🧠
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8000
dockerfile: backend/Dockerfile
pinned: false
---
```

`dockerfile:` points at the Dockerfile inside this monorepo rather than
requiring a separate repo for the Space — the same
`dockerfilePath`/`dockerContext` split `render.yaml` already uses. The build
context is still the repo root, and `.dockerignore` already excludes
`frontend/`, `training/`, `notebooks/` and `data/` from it, so the image
build stays lean without any further changes.

Commit that one change, then:

```bash
git remote add space https://huggingface.co/spaces/<you>/<space-name>
git push space hf-space-deploy:main
```

For every later update: rebase or merge the real branch into
`hf-space-deploy` and `git push space hf-space-deploy:main` again — the
frontmatter commit stays on top and GitHub's `README.md` is never touched.

### 3. Set secrets

Space → **Settings → Variables and secrets**. Nothing here is generated for
you the way Render's Blueprint does it — generate the three JWT secrets
yourself the same way `backend/.env.example` documents:
`python -c "import secrets; print(secrets.token_hex(32))"`, three independent
values, never reused between access/refresh/admin.

| Key | Value |
|---|---|
| `MONGODB_URL` | Atlas connection string, least-privilege user |
| `MONGODB_DB_NAME` | `mindlens` |
| `GROQ_API_KEY` | production Groq credential |
| `HF_TOKEN` | required — needed to pull the private `mindlens-*` model repos |
| `CORS_ORIGINS` | JSON array of the exact Vercel production + preview origins |
| `ENCRYPTION_KEY` | a Fernet key generated specifically for this deployment |
| `JWT_SECRET_KEY` / `JWT_REFRESH_SECRET_KEY` / `ADMIN_JWT_SECRET` | three independent generated values |
| `APP_ENV` | `production` |
| `USE_OPENAI_STUBS` | `false` |
| `PRELOAD_MODELS` | `true` — see below |
| `PRELOAD_RAG` | `true` |

Leave `CHROMADB_PERSIST_DIR` unset. Its default resolves under `/app`
(`config.py`'s `_REPO_ROOT` anchoring), which the Dockerfile already
`chown`s to the app user — no override needed, and free Spaces have no
persistent disk to point it at anyway. `PRELOAD_RAG=true` rebuilds the index
from `therapy_knowledge.json` on every boot regardless — verified locally at
67 chunks in ~10s, so the lack of persistence costs nothing.

`PRELOAD_MODELS=true` matters more here than it did on Render: it moves the
cost of loading all five models from a user's first message to server
startup. Verified locally — 60 seconds, zero errors, all five `ready` before
`/ready` reports 200 — versus the alternative, observed directly: two of
five classifiers timing out under concurrent cold-load pressure on a user's
actual first turn.

The service runs one worker (`Dockerfile`'s CMD) because WebSocket
connection state and rate limits are process-local. Introduce Redis before
increasing worker or instance count.

### 4. First boot

Space logs show the build, then the same startup sequence as local dev:
Mongo connect, five models loading serially (`_load_lock`), RAG ingest. Once
`/ready` returns `{"ready": true, ...}` with `rag.chunks > 0` and all five
models `"status": "ready"`, it's live at
`https://<you>-<space-name>.hf.space`.

Free Spaces sleep after inactivity. The next request wakes it, and that
first request pays the full boot cost again — budget real time (locally,
full boot is ~60s) before a live demo or a viva. A public Space is also a
publicly reachable API the moment it's live: rate limits exist
(`config.py`), but registering and hitting it is open to anyone who finds
the URL. Decide deliberately, not by default, whether that's acceptable
before making the Space public.

## Frontend on Vercel

Set these in the Vercel project's environment variables (Production, and
Preview if preview deployments should hit the live backend too):

- `NEXT_PUBLIC_API_BASE_URL`: the Space's public URL —
  `https://<you>-<space-name>.hf.space`. REST calls and the WebSocket URL
  are both derived from this (`websocket.ts`); `NEXT_PUBLIC_WS_BASE_URL`
  only needs setting if the WebSocket endpoint lives somewhere else.
- **Do not set `NEXT_PUBLIC_PREVIEW_AUTH`.** It exists only for local dev
  without a reachable backend (`frontend/.env.local`, gitignored) and
  bypasses the auth gate entirely — every visitor lands in chat as a fake
  logged-in user with no real account. If it's ever `1` in a Vercel
  environment, every visitor to that deployment skips authentication. There
  is no legitimate reason to set it there.

The client sends the access token as an `Authorization` bearer header for
normal API calls, so those need no CSRF handling. The one exception is
`/api/v1/auth/refresh`, which uses `credentials: "include"` to send the
7-day httpOnly refresh cookie (`frontend/src/lib/api.ts`) — that cookie is
`SameSite=None; Secure` in production, so the Space must be served over
HTTPS and the Vercel origin must be in `CORS_ORIGINS` with credentials
allowed, or every session will silently expire after 15 minutes instead of
refreshing.

Add the final Vercel domains to `CORS_ORIGINS` on the Space. Preview
deployments need explicit origins; wildcard origins are rejected in
production (`config.py`), and `_origin_allowed` gates the WebSocket
handshake on the same list (`chat.py`).

## Release check

1. Confirm `/health` and `/ready` both return 200 — `/ready` should show all
   five models `"status": "ready"` and `rag.chunks > 0` before trusting
   anything downstream.
2. Register and log in from the deployed Vercel origin, not localhost.
3. Send a real message. Confirm a genuine reply, not the generic fallback —
   check the reasoning trail actually references the room's read, and that
   the reply draws on the corpus rather than reading generic.
4. Run the crisis-response smoke test and confirm no generative agent
   executes — template-only, matches `crisis_agent.py`.
5. Mention a person in chat; confirm it appears on the Memory page, editable
   and deletable.
6. Check Space logs for request IDs and confirm no connection strings,
   tokens, or the JWT secrets are present anywhere in them.
