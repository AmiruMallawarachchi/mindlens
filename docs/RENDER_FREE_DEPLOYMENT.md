# Render Free Demonstration Deployment

This deployment path is only for a strictly zero-cost MindLens demonstration:
Render Free backend, Vercel Hobby frontend, MongoDB Atlas Free database, Groq
free quota, and Hugging Face Hub downloads only. Do not enter payment
information, enable pay-as-you-go, create paid Hugging Face endpoints, or add
paid Render resources.

## Cost Guardrails

- Root `render.yaml` uses exactly one Render web service with `plan: free`.
- `numInstances: 1`, one Uvicorn worker, no persistent disk, no Redis, no cron,
  no background worker, and no paid database.
- The paid Render example is archived at `deploy/render.paid.example.yaml` and
  must not be deployed without explicit approval.
- Stop before changing anything that could create charges.

## Runtime Limits

Render Free is expected to provide roughly 512 MB RAM and limited shared CPU
around 0.1 CPU for this demo. Cold starts after inactivity are expected.
First inference may be slow because models are never preloaded.

`DEPLOYMENT_MODE=render_free_demo` keeps the full local/full implementation in
the codebase while changing runtime behavior:

- `PRELOAD_MODELS=false`
- `PRELOAD_RAG=false`
- `MODEL_BACKEND=onnx`
- `CHROMADB_PERSIST_DIR=/tmp/mindlens/chroma`
- `RAG_RETRIEVAL_MODE=auto`

## Models

Live Hugging Face inventory checked on July 23, 2026:

| Classifier | Hub repo | Public files found | Free-demo expectation |
| --- | --- | --- | --- |
| Crisis | `AmiruMallawarachchi/mindlens-crisis` | `model.safetensors`, tokenizer/config files | Highest priority for INT8 ONNX export; may still be slow on cold start. |
| Emotion | `AmiruMallawarachchi/mindlens-emotion-classifier` | `model.safetensors`, tokenizer/config files | Exportable if local/dev dependencies can load the repo. |
| Mental health | `AmiruMallawarachchi/mindlens-mh-classifier` | `model.safetensors`, tokenizer/config files | Exportable, but larger memory pressure than crisis. |
| Cognitive distortion | `AmiruMallawarachchi/mindlens-distortion-classifier` | API returned unauthorized/not public | Missing for reproducible export until access is fixed. |
| RAG reranker | `AmiruMallawarachchi/mindlens-rag-reranker` | `model.safetensors`, tokenizer/config files | Optional; lexical RAG fallback is preferred on free tier. |

No exported ONNX artifacts are committed. Use:

```bash
python scripts/export_classifiers_to_onnx.py --model crisis --output-dir artifacts/onnx
```

Copy a tested artifact directory to `/tmp/mindlens/models/<name>` in the running
service only after confirming it fits. Without those artifacts, model status
will report `error` or `not_loaded`; the app must not claim the model executed.

Estimated memory:

- FastAPI/Motor/Groq/runtime: about 120-180 MB.
- ONNX Runtime plus tokenizer: about 50-100 MB before a model is loaded.
- Crisis INT8 ONNX target: roughly 70-140 MB resident during inference.
- RAG lexical fallback: small JSON corpus only, usually under 20 MB.
- Full PyTorch/Chroma/SentenceTransformer path: not expected to fit reliably in
  512 MB and is intentionally excluded from the free Docker image.

## RAG Without Disk

Render Free has no persistent disk. Chroma, if installed in a future variant,
must use `/tmp/mindlens/chroma` and only rebuild the curated therapy corpus.
User memories must stay in MongoDB Atlas and must never be written into Chroma.

The demo can fall back from vector retrieval to lexical retrieval over
`backend/data/therapy_knowledge.json`. Each turn reports whether RAG used
`vector`, `lexical`, or `none`.

## Required Render Secrets

Set these in Render as secret values. Do not commit or print them.

- `MONGODB_URL`: MongoDB Atlas Free cluster URI with a least-privilege user.
- `GROQ_API_KEY`: free quota key only.
- `HF_TOKEN`: only needed for private Hub downloads.
- `ENCRYPTION_KEY`: valid Fernet key.

Render generates independent `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, and
`ADMIN_JWT_SECRET` in the Blueprint.

Rotate any MongoDB credential that appeared in local logs before launch.

## Vercel Variables

Use Vercel Hobby. Configure the frontend with the Render HTTPS API origin and
the matching secure WebSocket origin. Then keep `CORS_ORIGINS` exact in Render:
production Vercel domain, preview branch domain, and local development origin
only when needed.

## Smoke Tests

After a real deployment, verify:

1. Render service plan is Free, instance count is one, and no disks, Redis,
   cron jobs, workers, paid databases, or paid model endpoints exist.
2. `GET /health` returns 200.
3. `GET /ready` returns 200 and honestly shows lazy, degraded, or unavailable
   model state.
4. Register and log in from the Vercel origin.
5. Open a WebSocket session and send a normal support message.
6. Send a crisis test message and confirm crisis response returns without RAG,
   Groq generation, or normal agents.
7. Exhausted Groq quota returns graceful service-unavailable behavior rather
   than retries that imply paid overflow.

Docker memory testing command, when Docker is available:

```bash
docker build -f backend/Dockerfile.render-free -t mindlens-render-free .
docker run --rm --memory=512m --cpus=0.1 -p 8000:8000 mindlens-render-free
```
