# MindLens: Why V1 Failed and Why V2 Is Better

> Evidence-based comparison of the two architectures. Every claim below is tied
> to a file, a commit, or a command. V1 code is preserved at the `pre-cleanup`
> git tag; current paths refer to the V2 tree.

## Executive summary

V1 was not a bad idea executed badly. It was a research-scale design — five
local Hugging Face models, fourteen agent classes, a local Chroma vector store,
and an unbounded orchestrator — deployed as if it were a small web app. Each
part worked in isolation; the system as a whole could not boot cheaply, could
not answer coherently, and could not tell the truth about its own health.

V2 replaces the parts that did not scale with hosted equivalents (Groq,
Pinecone) and replaces the unbounded orchestration with a small, explicit
LangGraph. The important change is not "more AI"; it is fewer, bounded steps
with deterministic safety first and a stable contract at the edge.

| Dimension | V1 | V2 |
|---|---|---|
| Inference | 5 local HF models, 2.5–3.5 GB resident | Groq `gpt-oss-20b` / `gpt-oss-120b` |
| Retrieval | local Chroma + ingest pipeline | Pinecone hosted index, fail-soft |
| Orchestration | 14-agent registry, unbounded selection | 7-node bounded graph, max 3 calls |
| Reply shape | several complete agent replies concatenated | one selected specialist, optional reviewer |
| Safety | model-dependent layers after orchestration | deterministic regex gate before any model call |
| Readiness | checked five local models | Mongo ping + real Groq configuration |
| Deployment | local models + tunnel / oversized host | Render + Vercel + hosted services |
| Tests | 722 passed, 10 failed, 12 errors at baseline | measured after cleanup (see report update) |

## Method

Evidence was collected from:

- the `pre-cleanup` tag and `cleanup/baseline-test-output.txt` (recorded at that
  tag);
- `cleanup/baseline-file-sizes.md` and `cleanup/baseline-dead-code-candidates.md`;
- the current V2 tree, including comments that document the failures they fixed;
- git history (`git log --oneline pre-cleanup..HEAD`).

The old Claude cleanup plan quoted 722 passed / 10 failed / 12 errors and
"400–500 line files". Those numbers were real **at the pre-cleanup tag**, not at
today's HEAD. This report keeps them as historical evidence and records a fresh
baseline after the boot fix.

## What V1 actually was

V1's live path was roughly:

```
WebSocket router (737 lines)
  -> Orchestrator (781 lines)
      -> model loader (419 lines) -> 5 local Hugging Face models
      -> local Chroma vector store (292 lines)
      -> AgentRegistry -> 14 agents
      -> ResponseAssembler (209 lines)
  -> stream to client
```

The pre-cleanup tree had **43 files over 300 lines**. The orchestrator, model
loader, chat router, and tests were each large enough that a change in one
concern required reading several others. That is a maintenance signal before it
is a performance signal.

## The seven failure modes

### 1. The resource budget was inverted

Five local models wanted roughly **2.5–3.5 GB resident** (the figure was
documented in `render.yaml`'s own header). On a free or small host that either
OOMs at startup or pushes the cost onto the first user message through a cold
load. The deployment docs tried three incompatible answers — Render, a Hugging
Face Docker Space, and a laptop behind ngrok — which is evidence that none of
them fit.

V2 has no local model weights. The backend is a normal FastAPI container; the
only cold-start cost is the platform's own sleep/wake behaviour.

### 2. Orchestration had no upper bound

V1 selected agents dynamically and let several of them speak. The assembler
eventually added `MAX_SPECIALIST_VOICES = 1` with a comment describing the
result: an empathy greeting followed by a distortion challenge followed by
another whole reply, "one wall of text" that "read like a committee rather than
one person".

V2's graph is fixed and small:

```
safety_gate -> assess -> memory_recall -> retrieve -> specialist -> [review] -> finalize
```

A normal turn makes at most three Groq calls (assessment, specialist, optional
reviewer). There is no registry to select from and no path that concatenates
multiple voices.

### 3. Local retrieval was a second deployment

Chroma plus an ingest CLI plus a reranker plus embedding-model settings meant
the retrieval stack had its own lifecycle, its own disk, and its own failure
modes. V1's readiness tests tried to verify the vector store's contents, which
tied health checks to a data pipeline.

V2 uses Pinecone with integrated embeddings. Retrieval is optional by design:
if it fails, the turn continues with `degraded: ["pinecone"]` and the graph
still produces a reply. Personal conversation text never enters the index; only
the curated therapy corpus is ingested.

### 4. The user's own message could be lost

The current message loop documents the fix in place: the user's turn is saved
**before** the pipeline runs, specifically so a pipeline or streaming failure
costs only the reply, never what the user typed. V1 wrote the turn after both
succeeded. In a mental-health product that is not a minor bug; it is the worst
possible failure mode.

### 5. The interface could claim things the backend did not know

The reasoning trail used to render "Clear - no crisis signals" as a literal
regardless of the safety gate's actual verdict, because the verdict was computed
and then dropped before the frame was built. The current frame builders carry
`safety`, `telemetry`, and `degraded` through explicitly. The same pattern
appeared in readiness: `/ready` reported models and RAG as healthy without
checking what the running system actually depended on.

V2's rule is narrower and stronger: persist what happened, and only claim what
was checked. `/ready` reports Mongo reachability, real Groq configuration
(including stub mode), and Pinecone configuration with the explicit caveat that
retrieval is fail-soft.

### 6. Three control loops were dead on arrival

`chat_services/memory.py` and `chat_services/checkins.py` wait for
`agent_outputs` entries with `agent == "personality"`, `agent ==
"session_memory_save"`, or `metadata.action == "schedule_checkin"`. V2's graph
emits only `{agent: route, metadata: {provider: "groq"}}`. The result:

- the introvert-score write never ran;
- automatic memory extraction never ran, so the Memory page's "what's been
  hard / what's helped" promise was backed by an empty collection;
- check-in scheduling never ran, so `CheckInAgent` was generating text for a
  scheduling write that never happened.

This is the most instructive V1 failure: each piece looked wired, the tests
passed, and the feature was still absent. A contract change in the orchestrator
silently orphaned downstream consumers. V2 fixes this by making the post-turn
writes explicit service calls, not inferences from an open-ended output list.

### 7. The test suite and the deployment story drifted

The recorded baseline was **722 passed, 10 failed, 12 errors**. The failures
were not random:

- `test_system.py` asserted a model-registry health endpoint V2 removed;
- `test_main.py` asserted readiness when five local models were preloaded, and
  that an empty Chroma store blocks readiness;
- `test_config.py` fixtures did not provide Pinecone settings;
- `test_vector_store.py` errored because the local Chroma path was removed.

These tests were not protecting users; they were protecting V1's shape. A suite
that only goes green when the old architecture is present makes the old
architecture impossible to retire. V2's tests assert the contract that actually
ships.

## What V2 does differently

1. **Deterministic safety first.** `safety_gate.py` runs before the assessment
   model. A crisis turn exits the graph into a template with real Sri Lankan
   resources; it does not depend on an LLM deciding to be careful.
2. **Bounded graph, stable contract.** `hosted_graph.py` compiles seven nodes
   and emits one dictionary (`result_contract`) that the WebSocket layer,
   persistence, and frontend all consume. Adding a node is a visible change,
   not an emergent one.
3. **One specialist, one voice.** The assessment picks a route; one specialist
   writes one reply. The optional reviewer can replace it but cannot stack a
   second voice on top.
4. **Hosted, fail-soft infrastructure.** Groq, Pinecone, and Langfuse each have
   an explicit degradation path. Mongo and the user's message do not.
5. **Privacy at the boundary.** `anonymizer.py` strips PII before model and
   retrieval calls; Langfuse receives metadata only; safety audit events store a
   SHA-256 hash of the message, not the message.
6. **Truthful operations.** `/health` is liveness; `/ready` is dependency
   readiness; `/api/v1/admin/system` reports the hosted service status. They no
   longer claim to check models that are not loaded.
7. **Tests aimed at the live contract.** The graph tests cover crisis exit
   before Groq/Pinecone, one specialist, assessment-triggered crisis, malformed
   JSON, and the optional reviewer. Router tests cover persistence and
   WebSocket auth.

## Measured baseline (pre-cleanup tag)

| Metric | Value | Source |
|---|---:|---|
| Tests passed | 722 | `cleanup/baseline-test-output.txt` |
| Tests failed | 10 | same |
| Test errors | 12 | same |
| Source files over 300 lines | 43 | `cleanup/baseline-file-sizes.md` |
| Largest backend file | 781 lines (`agents/orchestrator.py`) | `git show pre-cleanup:...` |
| Largest frontend file | 1,463 lines (`ai-elements/prompt-input.tsx`) | baseline size report |
| Legacy code removed in the first deletion batch | 2,112 lines / 19 files | `git diff --stat` |

A fresh post-fix baseline is recorded in `cleanup/post-fix-baseline.md` after
Phase 2. The report is updated with the final counts in Phase 7.

## What still had to change after this analysis

The V1/V2 split explains the architecture, but it did not finish the cleanup.
The remaining work is tracked in the finalization plan:

- fix the boot-blocking annotation in `hosted_graph_result.py`;
- commit the pending V1 deletions and get the suite to zero failures;
- make the deployment docs agree and make `/ready` truthful;
- remove the dead V1 agents and the V1 `BaseAgent` hierarchy;
- either rewire or remove the dead memory/check-in loops;
- add frontend tests and SEO;
- split the 2,787-line `globals.css` without deleting styles still in use.

## Lessons worth defending in an interview

- **Bounded beats clever.** A fixed graph with three model calls is easier to
  reason about, test, and operate than a registry that selects agents at
  runtime.
- **A fallback that hides failure is a second bug.** Empty completions, stubbed
  replies, and unreachable retrieval must be visible in the contract.
- **Persistence before inference.** Save what the user said before asking a
  model anything.
- **Health checks are claims.** Check the dependency you actually need, or say
  explicitly why you do not.
- **Tests can encode the past.** A green suite that asserts a removed
  architecture is not protection; it is drag.

## Appendix: reproduce the evidence

```bash
git show pre-cleanup:backend/app/agents/orchestrator.py | wc -l
git show pre-cleanup:backend/app/models/loader.py | wc -l
git show pre-cleanup:backend/app/rag/vector_store.py | wc -l
git log --oneline pre-cleanup..HEAD
grep -E "passed|failed|errors" cleanup/baseline-test-output.txt | tail -1
grep -c "OVER 300" cleanup/baseline-file-sizes.md
```
