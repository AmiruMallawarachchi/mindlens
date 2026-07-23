# Deploying MindLens

## Backend on Render

The repository includes `render.yaml` and `backend/Dockerfile`. Create a Render
Blueprint from the repository, then provide the environment values marked
`sync: false`.

Required production values:

- `MONGODB_URL`: MongoDB Atlas connection string with a least-privilege user.
- `GROQ_API_KEY`: production Groq credential.
- `HF_TOKEN`: required when any configured model is private.
- `CORS_ORIGINS`: JSON array containing the exact Vercel production and preview
  origins that should be trusted.
- `ENCRYPTION_KEY`: a valid Fernet key generated specifically for this service.

Render generates independent JWT signing secrets through the Blueprint. Do not
reuse them between access, refresh, and admin tokens.

The service intentionally runs one worker because WebSocket connection state and
rate limits are process-local. Introduce Redis before increasing the worker or
instance count.

The persistent disk stores Chroma data, and the curated corpus is ingested before
the readiness check succeeds. Model preloading is disabled in the Blueprint
because the five local models require a memory-sized Render plan.
Enable `PRELOAD_MODELS=true` only after verifying the instance can load all five;
when enabled, deployment fails fast if any model cannot load.

## Frontend on Vercel

Set the frontend's public API URL to the Render HTTPS URL and its WebSocket URL to
the corresponding `wss://` endpoint. Every REST request that relies on cookies
must use `credentials: "include"` and state-changing requests must include the
CSRF token returned by login or refresh.

Add the final Vercel domains to `CORS_ORIGINS`. Preview deployments need explicit
origins; wildcard origins are rejected in production.

## Release check

1. Confirm `/health` returns 200.
2. Confirm `/ready` returns 200.
3. Register and log in from the deployed Vercel origin.
4. Create a session and open a secure WebSocket.
5. Run the crisis-response smoke test and confirm no generative agent executes.
6. Check Render logs for request IDs and confirm no connection strings or tokens
   are present.
