# Post-fix baseline

Recorded on branch `cleanup/v2-final` after the boot fix and after committing
the pending V1 deletions. This supersedes the stale pre-cleanup numbers for
current work; the old numbers remain in `baseline-test-output.txt` as evidence
of the V1 contract mismatch.

## Backend

Command:

```bash
cd backend
APP_ENV=test DEBUG=false USE_OPENAI_STUBS=true \
  ../.venv/Scripts/python.exe -m pytest tests -q
```

Result: **615 passed, 0 failed, 0 errors** in 16.25s (Python 3.11.7).
Raw output: `cleanup/post-fix-test-output.txt`.

The suite now boots because `hosted_graph_result.py` no longer references an
undefined type at module level.

## Frontend

Commands:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Result: lint exit 0, typecheck exit 0, build exit 0 (Next.js 16.3.0, 8 static
pages). Raw output: `cleanup/post-fix-frontend-output.txt`.

## File sizes

249 source files counted under `backend/app/` and `frontend/src/`
(`.py`, `.ts`, `.tsx`, `.css`). Files over 300 lines: **2**, both CSS:

| Lines | File |
|---:|---|
| 2,787 | `frontend/src/app/globals.css` |
| 365 | `frontend/src/app/tokens.css` |

Largest code files are all under 300: `routers/onboarding.py` 291,
`agents/session_memory_save.py` 288, `routers/account.py` 287,
`agents/hosted_graph.py` 286, `lib/reasoning.ts` 281.

The only size work left is splitting `globals.css`; its legacy variables are
still referenced by live selectors, so it must not be deleted wholesale.

## Dead-code candidates still present

- V1 agent modules reachable only from `app/agents/__init__.py` and their own
  tests: challenge, distortion, empathy, journaling, mindfulness, personality,
  reflection, routine, `question_options`, `checkin_scheduler`,
  `session_memory_save`, `response_assembler`, `crisis_agent`.
- `ProgressAgent` and `CheckInAgent` are still used through the V1 `BaseAgent`
  hierarchy.
- Three post-turn loops are dead because V2's `agent_outputs` contract does not
  carry the metadata they look for: personality score, session memory
  extraction, and check-in scheduling.
- 12 frontend TS/TSX files have zero inbound imports (see the finalization plan
  for the list).
- 26 config settings are unused V1 fields.

These are intentional next-phase targets, not regressions.
