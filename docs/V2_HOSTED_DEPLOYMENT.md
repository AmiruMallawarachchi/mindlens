# MindLens V2 hosted deployment

V2 runs the FastAPI backend on Render and keeps the Next.js frontend on Vercel.
Inference is supplied by Groq, retrieval by Pinecone, application data by
MongoDB Atlas, and graph observability by Langfuse Cloud.

## Required services

- MongoDB Atlas Free cluster for application data.
- Groq API key and a project with the selected chat models enabled.
- Pinecone Starter index using the hosted `llama-text-embed-v2` model. Run
  `python scripts/create_pinecone_index.py` once, then
  `python scripts/ingest_pinecone.py`. Both operations are idempotent.
- Langfuse Cloud Hobby project. Set `LANGFUSE_ENABLED=true` only after both
  Langfuse keys are present.
- Render Docker web service using `render.yaml`.

The Render free service sleeps after 15 minutes without traffic and can take
about a minute to wake. The app must tolerate this cold start. Its filesystem
is ephemeral; no database, model, or vector index may be stored there.

## Environment variables

Set the values from `backend/.env.example` in Render. `CORS_ORIGINS` must be
the Vercel origin, and the Vercel `NEXT_PUBLIC_API_BASE_URL` must point to the
Render API. The WebSocket URL is derived from that API URL by the frontend.

## MongoDB migration

1. Back up the current local database with `mongodump`.
2. Restore it into the Atlas database with `mongorestore`.
3. Compare collection names and document counts.
4. Verify one migrated account can authenticate and load its sessions, memory,
   journal, and progress data.
5. Change Render's `MONGODB_URL` to the Atlas connection string.

Do not delete the local backup until the verification is complete.

## Langfuse privacy

V2 sends metadata only: graph nodes, route, branch, degradation status, RAG
status, and service information. User text, prompts, generated replies, raw
user IDs, and session IDs are excluded from Langfuse observations.
