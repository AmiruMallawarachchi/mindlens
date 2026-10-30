# MindLens V2 hosted deployment

This is the single source of truth for how MindLens is deployed. The current
target is the FastAPI backend on **Render** and the Next.js frontend on
**Vercel**. Inference is Groq, retrieval is Pinecone, persistence is MongoDB
Atlas, and tracing is Langfuse Cloud.

Local development lives in [DEPLOYMENT.md](DEPLOYMENT.md). That file is not a
deployment guide.

## Current state

- Frontend: `https://mindlens-theta.vercel.app` serves the marketing page and
  the application shell. Its production bundle still targets the retired tunnel
  `https://playroom-operative-ninth.ngrok-free.dev`, so the deployed chat cannot
  reach an API.
- Backend: **not yet deployed.** `render.yaml` defines the Docker web service,
  but no Render account has created it. `https://mindlens-api.onrender.com`
  does not answer, so that hostname is a placeholder, not a live endpoint.
- `NEXT_PUBLIC_*` variables are baked into the bundle at build time. Setting
  the API URL in the Vercel dashboard changes nothing until a new build runs.

To finish the deployment, follow the steps in this document in order: create the
Render service from the blueprint, set the secrets, create and ingest the
Pinecone index, then rebuild Vercel with `NEXT_PUBLIC_API_BASE_URL` pointing at
the Render URL.

## Required services

- MongoDB Atlas Free cluster for application data.
- Groq API key with the selected chat models enabled.
- Pinecone Starter index using the hosted `llama-text-embed-v2` model. Run
  `python scripts/create_pinecone_index.py` once, then
  `python scripts/ingest_pinecone.py`. Both operations are idempotent.
- Langfuse Cloud Hobby project. Set `LANGFUSE_ENABLED=true` only after both
  Langfuse keys are present.
- Render Docker web service using `render.yaml`.

V2 has no local model weights, no Chroma index, and no preload step. The Render
free service sleeps after about 15 minutes without traffic and cold-starts in
about a minute. Its filesystem is ephemeral; no database, model, or vector index
may be stored there. The service runs one worker because WebSocket connection
state and rate limits are process-local.

## Environment variables

Set these in the Render dashboard (or let the blueprint generate the JWT
secrets). Never commit values.

| Key | Value |
|---|---|
| `APP_ENV` | `production` |
| `USE_OPENAI_STUBS` | `false` |
| `MONGODB_URL` | Atlas connection string, least-privilege user |
| `MONGODB_DB_NAME` | `mindlens` |
| `GROQ_API_KEY` | production Groq credential |
| `PINECONE_API_KEY` | Pinecone project key |
| `PINECONE_INDEX_NAME` | index created by `scripts/create_pinecone_index.py` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | only when tracing is enabled |
| `LANGFUSE_ENABLED` | `true` after both keys are present |
| `CORS_ORIGINS` | exact Vercel production origin (and any preview origins) |
| `JWT_SECRET_KEY` / `JWT_REFRESH_SECRET_KEY` / `ADMIN_JWT_SECRET` | three independent values |
| `ENCRYPTION_KEY` | a Fernet key generated for this deployment |

`RENDER_GIT_COMMIT` is injected by Render and surfaced by `/health`.

On Vercel, set `NEXT_PUBLIC_API_BASE_URL` to the Render service URL, for example
`https://mindlens-api.onrender.com`. The frontend derives the WebSocket URL from
it. Do **not** set `NEXT_PUBLIC_PREVIEW_AUTH` in Vercel; it bypasses the auth
gate.

## Readiness contract

`GET /ready` returns 200 only when:

- MongoDB answers `ping`;
- `GROQ_API_KEY` is set;
- `USE_OPENAI_STUBS` is `false`.

The response also reports:

- `inference.status`: `configured`, `missing_key`, or `stub_mode`;
- `rag.status`: `configured` or `not_configured`, with `mode: "fail_soft"`.
  Pinecone is deliberately not pinged on every health check because retrieval
  is fail-soft; a failed search degrades one turn, it does not make the API
  unready;
- `observability`: Langfuse enabled/configured flags. Tracing is optional and
  never gates readiness.

## MongoDB data

The application needs the existing collections (`users`, `sessions`,
`user_memory`, `mood_logs`, `safety_events`, `journal_entries`,
`pending_checkins`, `progress_insights`, `token_blocklist`). If the Render
service points at a new Atlas cluster, migrate a backup explicitly:

1. Back up the source database with `mongodump`.
2. Restore into Atlas with `mongorestore`.
3. Compare collection names and document counts.
4. Verify one migrated account can authenticate and load sessions, memory,
   journal, and progress.
5. Change Render's `MONGODB_URL`.

Do not delete the backup until verification is complete. This step touches real
user data and requires explicit approval.

## Vercel

1. Set `NEXT_PUBLIC_API_BASE_URL` to the Render URL in the Production
   environment. Preview deployments need their own origin in `CORS_ORIGINS` if
   they should reach the API.
2. Redeploy; a variable change alone does not rebuild the bundle.
3. Add the exact Vercel origin(s) to `CORS_ORIGINS` on Render. Wildcard origins
   are rejected in production, and the WebSocket handshake checks the same list.
4. Confirm the refresh cookie works cross-site: production uses
   `SameSite=None; Secure`, so both sides must be HTTPS.

## Verification

1. `GET /health` returns 200 with the release commit.
2. `GET /ready` returns 200 with `inference.status: "configured"`,
   `stub_mode: false`, and `rag.mode: "fail_soft"`.
3. Open the Vercel origin, register or log in, and send one real message.
   Confirm a model-generated reply, the thinking trail, and persistence after a
   reload.
4. Create a journal entry, reopen it, and load Memory and Progress.
5. Confirm the WebSocket handshake succeeds from the Vercel origin.
6. Check Render logs for request IDs and confirm no connection strings, tokens,
   or JWT secrets appear.
7. `https://mindlens-theta.vercel.app/admin` is the separate ops dashboard. It
   shows hosted service status, not local model readiness.

## Langfuse privacy

V2 sends metadata only: graph nodes, route, branch, degradation status, RAG
status, and service information. User text, prompts, generated replies, raw user
IDs, and session IDs are excluded from Langfuse observations.
