# Qoder prompts for the MindLens V2 finalization

Use one phase per session. Paste the opening prompt, then the phase prompt, and
do not move on until the gate is met. This file mirrors the approved plan but is
written as copy-paste instructions.

## Opening prompt (paste first, every session)

> You are working on MindLens at `D:\AI Projects\mindlens`. The current branch is
> `cleanup/v2-final`; `pre-cleanup` preserves the V1 tree and `pre-v2-final`
> preserves the tree before this cleanup.
>
> Rules for every phase:
> - Make small, reviewable commits whose message says what changed and why.
> - Before deleting a file or block, grep the whole repo for importers/callers.
>   If anything still depends on it, stop and ask.
> - Run the relevant tests after every meaningful change, not only at the end.
> - Never skip, xfail, or comment out a failing test to fake green. Delete a
>   stale test with a one-line reason, or fix the real bug.
> - Explain every non-trivial change in plain language: what it did before, what
>   it does now, why.
> - Never print, stage, or commit `backend/.env` or `frontend/.env.local`.
> - Stop and ask before touching authentication, data deletion, or real user
>   data.
> - End with: files changed, files deleted and why, test counts before/after,
>   open questions.
>
> Execute only the phase I name. Do not start the next phase.

## Phase 0 — Evidence freeze

> Phase 0 only. Do not edit application code.
>
> 1. Confirm branch `cleanup/v2-final` and tag `pre-v2-final`.
> 2. Verify the 19 pending deletions (orchestration, models, legacy RAG) have
>    zero importers. Record the grep.
> 3. Capture `git log --oneline pre-cleanup..HEAD`, `git diff --stat`, and the
>    pre-cleanup sizes of the V1 orchestrator, loader, vector store, assembler,
>    and chat router.
> 4. Write `docs/V1_V2_REPORT.md` as an evidence table: claim, file/commit,
>    command. Do not fill in numbers you have not measured.
> 5. Write this prompts file if it is missing.
>
> Gate: every claim has evidence; no code deleted yet.

## Phase 1 — Boot fix

> Phase 1 only. `backend/app/agents/hosted_graph_result.py` declares
> `_hosted_orchestrator: HostedGraphOrchestrator | None = None` at module level
> without `from __future__ import annotations`, so Python 3.11 raises NameError
> on import. The real singleton is in `hosted_graph.py`.
>
> Delete the dead declaration (lines 45-48). Do not add a future import; that
> hides dead code. Run:
>
> ```bash
> cd backend
> python -c "import app.main"
> python -m pytest tests/unit/test_import_smoke.py -q
> ```
>
> Gate: both pass. Commit: `fix(agents): remove undefined hosted orchestrator annotation`.

## Phase 2 — Commit deletions and baseline

> Phase 2 only.
>
> 1. Re-grep the 19 pending deletions; commit them as one deletion commit.
> 2. Run the full backend suite with the CI environment.
> 3. For each failure/error: if it asserts V1 behavior that V2 removed, delete
>    the test with a one-line reason; if it reveals a real bug, fix the code.
> 4. Run frontend `npm ci`, `npm run lint`, `npm run build`.
> 5. Write the measured counts to `cleanup/post-fix-baseline.md`.
>
> Gate: pytest 0 failed, 0 errors; frontend lint/build pass; clean tree.

## Phase 3 — Deployment truth

> Phase 3 only. First ask me: is the backend live on Render, or on a local
> machine behind ngrok, with Vercel for the frontend? Probe both URLs read-only.
> Do not guess.
>
> Then make `docs/V2_HOSTED_DEPLOYMENT.md` the single source of truth and update
> `README.md`, `docs/DEPLOYMENT.md`, `docs/ARCHITECTURE.md`, `docs/SYSTEM.md`,
> and `render.yaml` to match. Remove V1 model/HF prose from `render.yaml`.
>
> Update `/ready` in `backend/app/main.py`: Mongo ping; Groq key **and**
> `USE_OPENAI_STUBS=false`; report Pinecone as configured-not-pinged because
> retrieval is fail-soft; report Langfuse configured/enabled. Update
> `backend/tests/unit/test_main.py`.
>
> Gate: all docs agree; `/ready` returns 200 only with Mongo + real Groq; tests
> pass.

## Phase 4 — Retire V1 backend code

> Phase 4 only.
>
> 1. Move `CRISIS_RESOURCES` to `backend/app/core/crisis_resources.py`; update
>    `hosted_graph.py`.
> 2. Replace `self.assembler._validator` with `ResponseValidator`; delete
>    `response_assembler.py` and its test.
> 3. Delete the dead specialists and their tests: challenge, distortion,
>    empathy, journaling, mindfulness, personality, reflection, routine,
>    question_options, crisis (after the constant move).
> 4. Delete `_save_introvert_score` and its loop after confirming no reader.
> 5. Trim `app/agents/__init__.py`; remove unused imports and mojibake.
> 6. Remove the 26 unused V1 settings in `config.py`; update
>    `tests/unit/test_config.py`.
> 7. Do not delete `progress_agent`, `checkin_agent`, `session_memory_save`,
>    `checkin_scheduler`, or `base_agent` yet.
>
> Gate: app imports, full pytest green, no `from app.agents import` outside the
> package, WebSocket tests pass.

## Phase 5 — Check-in and memory

> Phase 5 only. Ask me first: rewire the features or remove them?
>
> Rewire: port `ProgressAgent` to a plain service; port `SessionMemorySave` to
> `extract_memory(user_text, eos) -> dict` and call it from `flow.py` after the
> assistant turn; port `CheckInScheduler` + `CheckInAgent` to
> `app/services/checkins.py` and schedule once per session on disconnect, with
> timezone-aware UTC. Delete the V1 agent classes, `base_agent.py`, their tests,
> and unused conftest fixtures. Keep the graph at max three Groq calls.
>
> Remove: delete the loops, agents, frontend `checkin` handling, and Memory-page
> copy that promises automatic extraction, in one explicit commit.
>
> Gate: an end-to-end turn either writes memory/check-in data or the UI no
> longer claims it does; tests cover the chosen behavior.

## Phase 6 — Frontend

> Phase 6 only.
>
> 1. Add `vitest.config.ts`, `src/test/setup.ts`, `test`/`typecheck` scripts,
>    Vitest + RTL + jsdom, and 6-10 tests for login, chat send/receive, and
>    journal create. Align `eslint-config-next` with Next 16.
> 2. Delete the 12 zero-inbound files, rerunning the import scan after each
>    cluster. Never delete a file with a dynamic import or CSS reference.
> 3. Add `metadataBase`, canonical, Open Graph, Twitter, `robots.ts`,
>    `sitemap.ts`; normalize user-facing "Mindlens" to "MindLens".
> 4. Guard `companion-lab` in production.
> 5. Split `globals.css` into ordered files under `src/styles/`, each under 300
>    lines. Do not delete the legacy palette; it is still used.
>
> Gate: `npx tsc --noEmit`, lint, Vitest, build all pass; manual visual check in
> day and night modes.

## Phase 7 — CI, docs, deploy

> Phase 7 only.
>
> 1. Add frontend typecheck and test steps to `.github/workflows/ci.yml`.
> 2. Finish `docs/V1_V2_REPORT.md` and `docs/CODEBASE_MAP.md`; the map must cover
>    every backend/frontend module, the auth/chat/journal/dashboard flows, data
>    collections, external services, and one end-to-end chat turn.
> 3. Reconcile docs; archive or delete stale ones after folding their useful
>    numbers into the report.
> 4. Run the full verification, commit, open a PR, wait for CI green, merge, and
>    tag `v0.4.0`.
> 5. Ask me before deploying. Verify `/health`, `/ready`, login, one chat turn,
>    journal create, and WebSocket from the deployed origin. If credentials are
>    unavailable, hand over the exact steps instead of claiming deployment.
>
> Gate: definition of done true; CI green; live checks pass.
