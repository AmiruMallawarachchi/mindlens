# Changelog

All notable changes to MindLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First release verified against a running system rather than a test suite —
local MongoDB, real Groq calls, and the app driven end to end in a browser.
That verification is what surfaced most of the fixes below: each one passed
its unit tests while being broken in production, because the tests used
fakes for the parts that were actually failing.

### Fixed
- **RAG returned nothing on every turn.** Paths resolved against the current
  working directory, so the documented run command read from a second,
  never-ingested store; the corpus was a 7-entry smoke fixture; and
  `hnsw:search_ef` sat below the `fetch_k` the retriever asks for, failing
  intermittently. MMR, the cross-encoder reranker and the age-group boost
  had therefore never influenced a reply.
- **Replies were dropped in silence.** `EmotionalOperatingState`'s datetime
  fields aren't JSON-serializable without `mode="json"`, so `send_json`
  raised mid-send and tore down the WebSocket — the user saw nothing, not
  even an error. Observed while sending the safe fallback *after* the safety
  validator had correctly blocked a response.
- **The medication guard blocked ordinary replies**, firing on bare
  "I recommend" / "you should take" with no medication context required.
- **The user's message could be lost.** Both turns were written only after
  the pipeline and streaming succeeded, so any failure discarded what they
  typed. The user turn is now saved first.
- Model cold-loads are serialized; four concurrent loads were exhausting
  memory and timing out.
- Every validation error in the app showed the raw HTTP reason phrase
  ("Unprocessable Entity") instead of what actually failed.
- Page reloads accumulated empty sessions, which also inflated the
  seven-session gate on the weekly insight.

### Added
- Memory extraction: a person, hard topic or coping strategy mentioned in
  conversation now reaches the Memory page, where it can be edited or
  deleted. Previously nothing wrote to memory outside onboarding.
- Therapy corpus grown from 7 to 60 sourced entries (WHO, NHS, DBT, ACT,
  self-compassion, behavioural activation), each with a citation.
- Confirm-then-delete on destructive memory actions; journal entries can be
  edited and deleted.
- 28-class multi-label emotion trainer, generated from
  `emotion_labels.py` so the label order can't drift.

### Changed
- Tone, memory depth and social-disposition settings now reach the reply.
  They saved correctly before but were never read back.
- Distortion training taxonomy corrected: the cleaning and training
  notebooks disagreed on label spellings, so several classes trained on
  zero examples.

### Security
- Verified `backend/.env` has never been committed and is correctly ignored.
- Dropped `optimum`/`onnx` and moved `transformers` to 5.15.0, clearing five
  known CVEs. `optimum-onnx` caps `transformers` below 4.58, and every fix
  for those advisories lands in 5.x — so the quantization dependency was
  pinning the whole app to a vulnerable release. It existed only for an
  int8 ONNX path that was disabled by default and measurably made resident
  memory *worse* (ONNX Runtime loads alongside torch, not instead of it),
  so it was buying nothing and costing five advisories.

### Known limitations
- The distortion classifier scores **0.17 macro-F1** on ~690 weakly-labelled
  examples — a real result with a real data-thinness limit, not a bug.
- The emotion classifier is `SamLowe/roberta-base-go_emotions`, a public
  checkpoint, not a model trained for this project. Four of the five are
  fine-tuned here; the home page now marks which is which.
- **That adopted classifier misreads this domain.** Now that real confidence
  scores are surfaced, spot checks show clearly negative messages landing on
  the wrong label: "so anxious about my exam next week" → *excitement*
  (0.57), "my sister and I had a huge fight and I feel awful" → *disgust*
  (0.47). It was trained on Reddit comments, not on people describing
  distress. This is the strongest argument for finishing the in-house
  28-class trainer added in this release.
- The five models still load in float32 and want roughly 2.5–3.5 GB
  resident. `PRELOAD_MODELS=true` moves that cost to startup so no user
  waits on it, but it does not reduce it — the deployment target has to
  have the headroom. Genuinely shrinking it means dropping torch from the
  inference path entirely, which is not done here.

## [0.2.0] - 2026-06-16

### Added
- Multi-agent orchestrator with asyncio.gather parallel inference
- Empathy agent with Groq 8B/70B dual-tier routing
- Mindfulness agent with LLM-generated exercises
- Crisis agent with template-only responses (ZERO LLM)
- Safety gate with 2-layer detection — a deterministic keyword screen, then an isolated crisis classifier (threshold: 0.45)
- Emotional Operating System (EOS) state model
- Session memory with rolling summarization
- Longitudinal memory with mood trends and people graph
- FastAPI backend with lifespan management
- MongoDB connection with Motor async driver
- Pydantic v2 configuration management
- GitHub issue templates, PR template, CODEOWNERS
- MIT LICENSE
- SECURITY.md with vulnerability reporting policy
- CONTRIBUTING.md with setup guidelines
- CODE_OF_CONDUCT.md

### Changed
- Migrated from sequential to parallel model inference
- Updated crisis threshold to 0.45 (maximize recall)

### Security
- Added PII stripping to each turn's message before model calls
- Refresh token in an httpOnly cookie; short-lived access token in
  localStorage (see `frontend/src/lib/api.ts`)
- Rate limiting planned for all endpoints

## [0.1.0] - 2026-04-15

### Added
- 3 trained transformer models:
  - Crisis detection: DistilBERT fine-tuned on 230k samples
  - Emotion classification: RoBERTa go-emotions 28-class
  - Mental health: MentalBERT 5-label classifier
- Data cleaning pipelines for all datasets
- Jupyter notebooks for model training and evaluation
- Basic FastAPI skeleton with health checks
- MongoDB connection setup