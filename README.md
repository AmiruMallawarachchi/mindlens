# MindLens V2

> A privacy-conscious hosted LangGraph multi-agent chat system for reflective mental-health support.

MindLens is a portfolio-grade full-stack AI system demonstrating how to build a reliable multi-agent product around a sensitive user experience. It combines a FastAPI API, Next.js chat application, LangGraph orchestration, Groq-hosted models, Pinecone hosted retrieval, MongoDB Atlas persistence, and metadata-only Langfuse observability.

MindLens is not medical advice, diagnosis, therapy, or an emergency service.

**Live frontend:** [mindlens-theta.vercel.app](https://mindlens-theta.vercel.app) · **Source:** [GitHub](https://github.com/AmiruMallawarachchi/mindlens)

The frontend may be unavailable while the backend is sleeping or before cloud credentials are configured. The architecture remains reviewable offline through the diagrams, source, and mocked tests below.

## Why this project is interesting

- Real bounded LangGraph workflow with explicit nodes and conditional edges.
- Deterministic crisis protection before any model call.
- Structured model assessment instead of unconstrained orchestration.
- One selected specialist per ordinary turn, with an optional reviewer.
- Hard maximum of three Groq calls on a normal turn.
- Hosted retrieval over a curated corpus; personal conversations never enter Pinecone.
- PII anonymization before external model calls.
- Langfuse traces exclude prompts, responses, user IDs, and session IDs.
- Stable REST and WebSocket contracts between backend and frontend.
- Graceful degradation when retrieval, tracing, or hosted inference fails.
- Credential-free documentation and tests for recruiter review.

## Architecture

```mermaid
flowchart LR
    U[User] --> V[Vercel Next.js frontend]
    V <-->|REST + WebSocket| R[Render FastAPI backend]
    R --> G[LangGraph supervisor]
    G --> S[Deterministic safety gate]
    S -->|crisis| C[Crisis template]
    S -->|safe| A[Groq assessment]
    A --> M[MongoDB memory recall]
    M --> P[Pinecone hosted retrieval]
    P --> X[Selected specialist]
    X --> Q{Complex turn?}
    Q -->|yes| W[Groq reviewer]
    Q -->|no| F[Validation + persistence]
    W --> F
    F --> V
    R --> DB[(MongoDB Atlas)]
    G -. metadata only .-> L[Langfuse Cloud]
```

## LangGraph workflow

```mermaid
flowchart TD
    START((START)) --> SG[safety_gate]
    SG -->|crisis| FIN[finalize]
    SG -->|safe| AS[assess]
    AS -->|model risk| FIN
    AS -->|ordinary turn| MR[memory_recall]
    MR --> RET[retrieve]
    RET --> SP[specialist]
    SP -->|review_required| REV[review]
    SP -->|normal| FIN
    REV --> FIN
    FIN --> END((END))
```

The graph is deliberately bounded. A deterministic crisis match exits before Groq and Pinecone. An ordinary turn uses assessment plus specialist generation. A complex turn may add one reviewer.

## Repository map

```text
backend/app/agents/hosted_graph.py   LangGraph state, nodes, routing
backend/app/observability.py         Metadata-only Langfuse tracing
backend/app/rag/hosted_retriever.py  Pinecone hosted search adapter
backend/app/routers/chat.py          REST/WebSocket chat entrypoint
backend/tests/unit/agents/            V2 graph contract tests
frontend/src/components/chat/         Chat and pipeline UI
scripts/create_pinecone_index.py      Idempotent index creation
scripts/ingest_pinecone.py            Curated corpus ingestion
docs/ARCHITECTURE.md                  Detailed technical architecture
docs/RECRUITER_DEMO.md                Offline portfolio walkthrough
docs/V2_HOSTED_DEPLOYMENT.md          Cloud deployment and migration
render.yaml                            Render backend blueprint
```

## Recruiter-friendly review path

A reviewer does not need private credentials to understand the system:

1. Read this README and the diagrams.
2. Read [the architecture document](docs/ARCHITECTURE.md).
3. Follow [the recruiter demo guide](docs/RECRUITER_DEMO.md).
4. Inspect [`hosted_graph.py`](backend/app/agents/hosted_graph.py).
5. Run the mocked graph tests in [`test_hosted_graph.py`](backend/tests/unit/agents/test_hosted_graph.py).

The graph tests mock Groq and Pinecone, so routing, crisis exits, malformed model output, and call limits remain inspectable offline.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item backend\.env.example backend\.env
cd backend
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`; the application lives at `/app`. Backend health endpoints are `/health` and `/ready`.

## Tests and quality checks

```powershell
python -m pytest backend/tests/unit/agents/test_hosted_graph.py -q
cd frontend
npm run lint
npx tsc --noEmit
```

## Deployment architecture

| Layer | Service | Responsibility |
|---|---|---|
| Web client | Vercel | Next.js application and chat UI |
| API | Render | FastAPI, WebSocket, LangGraph runtime |
| Generation | Groq | Hosted assessment and response generation |
| Retrieval | Pinecone | Hosted embeddings and corpus search |
| Persistence | MongoDB Atlas | Accounts, sessions, memories, journals, progress |
| Observability | Langfuse Cloud | Allowlisted metadata-only traces |

See [V2 hosted deployment](docs/V2_HOSTED_DEPLOYMENT.md) for secrets, Pinecone setup, Atlas migration, Render, Vercel, CORS, and WebSocket configuration. Free tiers can sleep or impose quotas; those constraints are documented rather than hidden.

## Privacy and safety

- Crisis screening occurs before external model calls.
- Model-detected risk stops specialist generation.
- Conversation text is anonymized before Groq and Pinecone calls.
- Conversations and memories are never indexed in Pinecone.
- Langfuse receives graph/service metadata only.
- Responses are validated before returning to the client.
- Failures produce explicit degraded behavior rather than invented emotional certainty.
- The UI does not display uncalibrated numeric emotion confidence.

## Engineering trade-offs

MindLens uses a small supervisor graph instead of unconstrained agent loops. This improves safety, latency, cost predictability, and debugging. Hosted services replace local model weights, PyTorch, SentenceTransformers, and Chroma in the deployed runtime. The existing product shell and API/WebSocket shapes are preserved to reduce frontend migration risk.

## Status

Implemented: LangGraph runtime, Groq inference, Pinecone adapters and ingestion, Langfuse tracing, Render/Vercel configuration, Atlas migration runbook, recruiter documentation, and V2 graph tests.

Environment-specific: entering provider credentials, creating cloud projects, migrating private MongoDB data, deploying services, and migrating remaining legacy V1 tests that expect local model/Chroma behavior.

## Responsible use

MindLens is a demonstration of software architecture and responsible AI engineering. It must not substitute for qualified mental-health professionals or emergency services.
