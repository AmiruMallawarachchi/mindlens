# Deploying MindLens

**What's actually live right now: a local backend + an ngrok Tunnel +
Vercel.** That's the section below titled "Backend: local + ngrok Tunnel
(the current live setup)" — read that one first. The Hugging Face
Docker Space section further down is a real, documented, $0 alternative
that was designed but never deployed; it's kept for if the tunnel approach
stops being good enough, the same way `render.yaml` is kept as a documented
alternative nobody currently runs. Don't follow the HF steps expecting them
to match what's live — they don't yet.

## Backend: local + ngrok Tunnel (the current live setup)

The backend runs on a developer machine, not a hosted platform, exposed to
the internet through an ngrok tunnel. Free, but it means **the demo depends
on that machine being on and connected**, and (unlike Cloudflare's quick
tunnels, which this project used earlier) ngrok requires a one-time free
account and authtoken. This is an accepted, deliberate limitation, not an
oversight: see `SYSTEM.md`'s external-services table.

### Start MongoDB first

The backend needs a running MongoDB before it will boot at all — it
fails closed rather than starting half-connected. Locally this is the
Windows `MongoDB` service, and **it does not reliably survive a sleep or
a machine restart** even though its start type is `Automatic` — this has
been observed to require a manual restart more than once in a single
day. Starting it needs an **elevated** PowerShell (a non-admin shell
fails with "Cannot open MongoDB service"):

```powershell
Start-Service MongoDB
```

Confirm it actually took before moving on — `Get-Service MongoDB` should
show `Running`, not `Stopped`.

### Start the backend

```bash
cd backend
../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

First boot takes ~15–20s (five ML models + the RAG index). Confirm it's
actually healthy before doing anything else:

```bash
curl http://127.0.0.1:8000/ready
```

`/health` only proves the process is up; `/ready` is the one that
actually checked MongoDB and all five models — use that one, not
`/health`, when confirming the backend is genuinely usable. If MongoDB
isn't running yet, the backend does not boot at all — `connect_db`
raises during startup and uvicorn exits with a `ServerSelectionTimeoutError`
traceback naming `localhost:27017`. That traceback is the tell: it means
"start Mongo and restart the backend," not a code problem to chase.

`--reload` does not reliably pick up code changes on this Windows setup —
after editing backend code, stop the process (Ctrl+C) and start it again
rather than trusting the reload flag.

### Start the tunnel

One-time setup: create a free account at
[dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup), copy the
authtoken from
[dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken),
then:

```bash
ngrok config add-authtoken <your-token>
ngrok http 8000
```

Unlike Cloudflare's quick tunnels (used earlier in this project), a free
ngrok account is issued one **permanent "dev domain"** — confirmed by
killing and restarting the agent repeatedly and observing the identical
hostname come back every time, with no `--domain` flag needed. This
project's dev domain is `playroom-operative-ninth.ngrok-free.dev`, visible
under **dashboard.ngrok.com/domains** ("yours forever," not accruing
endpoint hours). Practically: `NEXT_PUBLIC_API_BASE_URL` on Vercel only
needs setting **once**, not after every restart — see the note at the end
of this subsection for the one scenario where it would need to change
again. A local inspector for every request that passed through is at
`http://127.0.0.1:4040` while the tunnel is running.

On Windows, Defender has been observed quarantining `ngrok.exe` — either
the winget-installed binary or the one `ngrok update` downloads in place —
as a false positive. If `ngrok` suddenly stops launching, check **Windows
Security → Protection history** for a "Threat quarantined"/"Threat
blocked" entry naming `ngrok.exe` and restore it; it does not reappear
after a clean restore.

### If the dev domain ever has to change

This should be rare — the domain in `NEXT_PUBLIC_API_BASE_URL` and in
`backend/.env`'s `CORS_ORIGINS` only needs updating if the dev domain is
deleted from the ngrok dashboard, the ngrok account changes, or a different
domain is deliberately reserved. If that happens,
`mindlens-theta.vercel.app` will show "Couldn't reach Mindlens. It may be
down" on the login screen — this looks exactly like a real outage when
it's actually just a stale URL.

1. Copy the new `https://*.ngrok-free.dev` URL `ngrok` printed on startup
   (or read it from `http://127.0.0.1:4040/api/tunnels`).
2. `vercel env rm NEXT_PUBLIC_API_BASE_URL production` (it must already
   exist to remove), then `vercel env add NEXT_PUBLIC_API_BASE_URL
   production` — answer **no** to "Store as sensitive?" (Vercel rejects
   sensitive storage for `NEXT_PUBLIC_*` vars in Production/Preview) and
   paste the new URL as the value. The dashboard's **Settings →
   Environment Variables** works the same way if you'd rather not use the
   CLI.
3. **Redeploy is required**, not optional — `NEXT_PUBLIC_*` variables are
   baked into the JavaScript bundle at build time, so saving the new value
   alone does nothing until the next build picks it up:
   `vercel --prod` from the repo root (the Vercel project's Root Directory
   is `frontend`, so `vercel` must run from the repo root where `.vercel/`
   is linked, not from inside `frontend/`), or Deployments tab → latest
   deployment → **⋯ → Redeploy** in the dashboard.
4. Update `CORS_ORIGINS` in `backend/.env` if it references the old
   hostname anywhere (it currently doesn't need to — CORS is keyed on the
   *frontend's* origin, not the tunnel's).

### Troubleshooting: "Couldn't reach Mindlens" on the login screen

In order of likelihood:

1. **The tunnel isn't running.** Check for an `ngrok` process — if it's
   gone, `ngrok http 8000` (no flags needed) brings back the same
   permanent dev domain automatically.
2. **The backend isn't running.** `curl http://127.0.0.1:8000/health`
   locally; a tunnel forwarding to a dead port fails the same way.
3. **Vercel env var was updated but not redeployed.** The bundle still has
   the old URL baked in until a fresh build runs.
4. **The machine slept or lost network.** Free tunnels don't survive
   either; both the backend and `ngrok` need restarting.
5. **ngrok's free-tier browser interstitial.** ngrok serves an HTML "you
   are about to visit..." warning page — not the real JSON response — to
   any request it fingerprints as coming from a browser, unless that
   request carries an `ngrok-skip-browser-warning` header. This is silent:
   `curl` without a browser `User-Agent` sails through and looks fine,
   while the actual deployed frontend gets HTML back and fails to parse
   it as JSON. `frontend/src/lib/api.ts` sends this header on every
   request specifically to prevent this; if a future request path bypasses
   `request()` (a raw `fetch` added elsewhere), it needs the same header
   or it will hit this exact failure again.

## Backend on a Hugging Face Docker Space

Designed as the original $0 backend host — free Docker Spaces give far more
RAM than the five models need, and the weights already live on the same HF
account. **Not currently deployed**; the steps below are kept accurate and
ready, not aspirational, should the tunnel-and-laptop approach above stop
being sufficient (e.g. a demo that needs to run unattended, or without
depending on a specific machine being online).

Render is **not** used for the backend either. Its free tier is 512MB
against the five models' ~2.5–3.5GB resident need — a 5–7× gap, not a
tuning problem — and free Render has no persistent disk either.
`render.yaml` is kept as a documented, correct alternative for if that ever
changes (see its header comment for the plan size it actually needs); it
isn't part of this path.

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
7. `https://mindlens-theta.vercel.app/admin` — a standalone, unlinked ops
   dashboard (model status, DB connectivity, environment/release). Its own
   sign-in, a separate short-lived token from the normal login — see
   `backend/scripts/make_admin.py` for how an account becomes an admin.
   Deliberately shows no user data. Confirm all five models read `ready`
   here too; this is the page that would have caught this project's
   silent all-classifiers-failing bug at a glance instead of it surfacing
   as generic replies with no obvious cause.
