# Dead-code candidates (report only)

Read-only search based on the current `cleanup/baseline` commit. This is a candidate list, not a deletion recommendation or proof that a file can be removed. The count is **13 candidate source files in four clusters**. Tests, developer scripts, compatibility exports, and possible future V1 support are relevant references and must be resolved before removal.

## 1. Legacy local Chroma RAG (3 files)

| Candidate | References outside its own tests | Assessment |
|---|---|---|
| `backend/app/rag/vector_store.py` | Referenced by `backend/app/rag/ingest.py` and `backend/app/rag/retriever.py`; no active router or `main.py` import found. Its `connect()` raises `RuntimeError("Local ChromaDB was removed in MindLens V2; use Pinecone")` when the Chroma dependency is unavailable. | Candidate for retirement or an explicitly supported local mode. The remaining module references form a legacy-only dependency chain. |
| `backend/app/rag/ingest.py` | Imports `get_vector_store` from `vector_store.py`; presents a `python -m app.rag.ingest` CLI in its module docs. No active runtime entry point found. | Candidate for retirement after checking whether anyone still uses the manual CLI or local corpus workflow. |
| `backend/app/rag/retriever.py` | Used by `backend/app/agents/orchestrator.py`; no import from the hosted graph or current routers found. Its tests exercise the legacy retriever. | Candidate together with the legacy orchestrator and vector store; do not remove independently. |

## 2. Local model manager (1 file)

| Candidate | References outside its own tests | Assessment |
|---|---|---|
| `backend/app/models/loader.py` | Imported by the legacy `agents/orchestrator.py` and lazily by the local `rag/retriever.py`. No import from `main.py`, current routers, or the hosted graph found. Model settings in `config.py` are also consumed by this legacy path. | Candidate for retirement with the V1 inference path, subject to confirming no supported offline/local workflow remains. |

## 3. Legacy orchestrator (1 file)

| Candidate | References outside its own tests | Assessment |
|---|---|---|
| `backend/app/agents/orchestrator.py` | The current chat router calls `get_hosted_orchestrator()` from `hosted_graph.py`; no production import of `Orchestrator` was found. Its internal references connect the V1 agent/model/RAG stack. The router has comments describing the older orchestrator, but no executable import/call. | Candidate for retirement as one unit with the V1 modules. Many tests depend on it, so the test suite must be deliberately migrated or the legacy path explicitly retained. |

## 4. Unreferenced AI UI component set (8 files)

Static import search under `frontend/src/` found no importing module outside this set for these components. `agent.tsx` imports `code-block.tsx`, so that is an internal dependency of an otherwise unreferenced component.

| Candidate files | Search result |
|---|---|
| `frontend/src/components/ai-elements/agent.tsx` | No imports from application source found; referenced internally by `code-block.tsx` relationship in the opposite direction. |
| `frontend/src/components/ai-elements/checkpoint.tsx` | No imports from application source found. |
| `frontend/src/components/ai-elements/code-block.tsx` | Imported only by the candidate `agent.tsx`; no app-level import found. |
| `frontend/src/components/ai-elements/confirmation.tsx` | No imports from application source found. |
| `frontend/src/components/ai-elements/context.tsx` | No imports from application source found. |
| `frontend/src/components/ai-elements/inline-citation.tsx` | No imports from application source found. |
| `frontend/src/components/ai-elements/shimmer.tsx` | No imports from application source found. |
| `frontend/src/components/ai-elements/suggestion.tsx` | No imports from application source found. |

## Search notes and limits

- Backend searches covered `backend/app`, `backend/scripts`, `scripts`, documentation, and test references; candidate descriptions distinguish runtime imports from internal legacy-stack references.
- Frontend searches covered import paths within `frontend/src/`. String-based/dynamic loading and external consumers are not ruled out.
- `backend/app/agents/__init__.py` re-exports numerous legacy agent classes. Some are directly used by current routes (for example, `ProgressAgent` and `CheckInAgent`), so this report does not label the whole agent directory dead.
- The older `docs/documentation.md` and `docs/SYSTEM.md` contain many V1 architecture references, but they are historical documentation and are not counted as code candidates.
- No files were deleted or edited during this search; only this report was created.
