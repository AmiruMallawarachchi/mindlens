# MindLens V2 codebase map

A navigational map of the code that ships. It answers three questions fast:
where does a request go, what owns each piece of behaviour, and which file do I
open to change it. For the reasoning behind the V1-to-V2 move, read
[V1_V2_REPORT.md](V1_V2_REPORT.md).

## 1. Runtime shape

```
Browser
  ├─ REST  /api/v1/*        FastAPI routers  ──> services / MongoDB
  └─ WS    /ws/chat/{id}    chat router      ──> LangGraph ──> Groq / Pinecone
                                                 └─ persistence ──> MongoDB
```

- **Frontend:** Next.js 16 App Router, React 19, TypeScript, Tailwind utilities
  plus the `ml-*` design tokens.
- **Backend:** FastAPI on Python 3.11, Motor for MongoDB, LangGraph for the
  bounded turn, Groq for inference, Pinecone for retrieval, Langfuse for
  metadata-only tracing.
- **Deployment:** Vercel serves `frontend/`; Render serves `backend/` from
  `render.yaml`. `docs/V2_HOSTED_DEPLOYMENT.md` is the only deployment
  runbook.

## 2. Backend map (`backend/app`)

### Entry and configuration

| File | Responsibility |
|---|---|
| `main.py` | App factory, lifespan (Mongo connect/close), router registration, `/health`, `/ready` |
| `config.py` | Every environment setting, parsed once through Pydantic |
| `db.py` | Motor client and database handle |
| `observability.py` | Langfuse client; sends allowlisted metadata, never prompts or user IDs |

### The turn (`agents/`)

| File | Responsibility |
|---|---|
| `hosted_graph.py` | The seven nodes, conditional edges, and their prompts |
| `hosted_graph_state.py` | `HostedGraphState` TypedDict, EOS construction, recall and specialist-context helpers |
| `hosted_graph_result.py` | `result_contract()` — the one dictionary every consumer reads |
| `safety_gate.py` | Deterministic crisis screening and vetted crisis templates |
| `groq_client.py` / `groq_types.py` | Hosted chat client, timeouts, tier selection |
| `groq_stub.py` | Deterministic offline replies when no key is configured |
| `response_validator.py` | Final reply guard (empty, malformed, unsafe) |
| `streaming.py` / `streaming_pipeline.py` / `streaming_response.py` | Turn a result into `stage_update`, `thinking_update`, `stream_chunk`, and `response` frames |
| `__init__.py` | Package docstring only; no eager agent registry |

### Core rules (`core/`)

| File | Responsibility |
|---|---|
| `emotional_os*.py` | The Emotional Operating State model, enums, and factories |
| `memory_recall.py` | Pure recall: people, topics, coping, preferences, depth rules |
| `anonymizer.py` | Strips emails, phone numbers, IDs before Groq/Pinecone |
| `connection_manager.py` | One WebSocket per user; route frames to it |
| `connection_messages.py` | Frame builders, so payload shapes live in one place |
| `crisis_resources.py` | Sri Lankan crisis contacts used by templates |
| `emotion_labels.py` | Human labels for emotion ids |

### HTTP and WebSocket (`routers/`)

| File | Responsibility |
|---|---|
| `auth.py` | Composes the auth route modules below and re-exports their helpers |
| `auth_user_routes.py` | Register, login, refresh |
| `auth_profile_routes.py` | `GET/PATCH /me` |
| `auth_logout_routes.py` | Logout and token blocklist |
| `auth_admin_routes.py` | Admin login, user list, user count |
| `auth_helpers.py`, `auth_schemas.py` | Password hashing, request/response shapes |
| `session.py` + `session_service.py` + `session_schemas.py` | Session CRUD and transcript reads |
| `chat.py` | WebSocket authentication, connect/disconnect lifecycle, pending check-ins |
| `chat_services/flow.py` | The per-message loop: validate, persist, run graph, stream, post-turn writes |
| `chat_services/persistence.py` | Load history; save user turn, assistant turn, mood log, safety event, session close |
| `chat_services/memory.py` | Race-safe `user_memory` bootstrap and merge |
| `dashboard.py` | Mood series, summary, weekly insight (calls `services/progress.py`) |
| `journal.py` | Prompt, list, read, create, update, delete |
| `memory.py` + `memory_service.py` + `memory_schemas.py` | User-visible memory: people, preferences, patterns, notes |
| `onboarding.py` + `onboarding_service.py` + `onboarding_schemas.py` | Status, step, complete |
| `account.py` | Device sessions, data export, account deletion |
| `system.py` | Admin operational and hosted-service status |

### Side effects around the graph (`services/`)

These are plain functions, not agents. They run after the reply exists so a
failure cannot cost the user their message or the reply.

| File | Responsibility |
|---|---|
| `memory_extraction.py` | Pure extraction of a person, hard topic, or coping strategy from one message |
| `checkins.py` | Pick a wake-up time, generate the check-in text, schedule and deliver it |
| `progress.py` | Generate the weekly insight from aggregate history |

### Supporting packages

| Folder | Responsibility |
|---|---|
| `middleware/` | JWT creation/validation, current-user dependencies, auth rate limits, PII checks |
| `memory/` | Session buffer, in-memory session model, persistence helpers used by chat |
| `rag/` | `hosted_retriever.py` — Pinecone search; fail-soft by contract |
| `utils/logger.py` | Structured logger factory |

### Tests

- `tests/unit/agents/` — graph contracts, safety red-team cases, validation,
  streaming, Groq degradation.
- `tests/unit/routers/` — auth, chat persistence, one full WebSocket turn,
  journal, memory, dashboard, account.
- `tests/unit/services/` — extraction, check-in scheduling, progress insight.
- `tests/unit/core/`, `tests/unit/middleware/`, `tests/unit/memory/` — pure
  rules and auth plumbing.
- `tests/integration/test_full_pipeline.py` — the graph end to end with stubs.

## 3. Four request flows

### Auth (REST)

```
client → POST /api/v1/auth/register | /login
       → auth_user_routes → hash/verify → users + user_sessions
       → access token (short) + refresh token (httpOnly cookie)
client → GET /api/v1/auth/me            (Authorization: Bearer …)
       → middleware/auth_dependencies.require_user
client → POST /api/v1/auth/refresh      → rotate access token
       → POST /api/v1/auth/logout       → blocklist the token jti
```

### Chat (WebSocket)

```
client connects /ws/chat/{session_id}
  → chat.py extracts the JWT (cookie, header, or mindlens.jwt.<token> subprotocol)
  → validates origin and session ownership
  → ConnectionManager registers the single socket for this user
  → sends any pending check-in
client sends {type:"message", text, session_id, timestamp}
  → flow.py: rate limit → length cap → history + memory load → persist user turn
  → HostedGraphOrchestrator.run_full_pipeline()
  → stream_pipeline_result() frames
  → persist assistant turn, mood log, safety event
  → extract memory and merge into user_memory (skipped on crisis)
disconnect
  → save session close → schedule one check-in for this session
```

### Journal (REST)

```
GET  /api/v1/journal/prompt              deterministic daily prompt
GET  /api/v1/journal?limit=30            summaries for the list
POST /api/v1/journal                     {title?, text, prompt_used?}
GET  /api/v1/journal/{entry_id}
PUT  /api/v1/journal/{entry_id}
DELETE /api/v1/journal/{entry_id}
```

### Dashboard (REST)

```
GET /api/v1/dashboard/mood       recent mood log entries
GET /api/v1/dashboard/summary    counts and averages
GET /api/v1/dashboard/insight    cached weekly insight; regenerates every 7 sessions
```

## 4. Frontend map (`frontend/src`)

### Routes (`app/`)

| File | Responsibility |
|---|---|
| `layout.tsx` | Fonts, metadata, grade bootstrap script, tooltip provider |
| `page.tsx` | Public home page plus JSON-LD |
| `app/page.tsx` | Signed-in application shell |
| `admin/page.tsx` | Admin console |
| `companion-lab/` | Development avatar grid; 404 in production |
| `error.tsx`, `global-error.tsx`, `not-found.tsx` | Error surfaces |
| `robots.ts`, `sitemap.ts` | Crawler policy and public route list |
| `globals.css` | Imports Tailwind, tokens, and component recipes; base element styles |

### Chat (`components/chat/`)

- `chat-screen.tsx` — layout and live region.
- `message-flow.tsx` plus `message-flow-actions.tsx` — transcript, emotion read,
  reasoning, pipeline trace.
- `pipeline-trace.tsx`, `reasoning-trail.tsx`, `live-stage-trail.tsx` — what the
  backend actually reported, rendered stage by stage.
- `composer.tsx`, `use-composer-dictation.ts` — input, send, dictation.
- `chat-sidebar*.tsx` — session list, navigation, footer.
- `crisis-banner.tsx` — crisis resources; `breathe-card.tsx` — breathing exercise.

### State and transport (`lib/`)

| File | Responsibility |
|---|---|
| `websocket.ts` | `MindLensSocket`: subprotocol auth, reconnect, token refresh, message frames |
| `use-chat-frames.ts` | Reduces server frames into messages, thinking state, crisis state |
| `use-chat-runtime.ts`, `use-chat-sessions.ts`, `use-chat-presentation.ts` | Connection lifecycle, session list, appearance |
| `use-mindlens-client.ts` | The composition hook the app screens consume |
| `api.ts` and `api_*.ts` | Typed REST wrappers |
| `types*.ts` | Shared payload types, grouped by API domain |
| `emotion.ts`, `emotion-catalog.ts` | Emotion ids, palette, CSS variables |
| `reasoning.ts`, `reasoning-agents.ts` | Prose trail and agent phrases |
| `site.ts` | Public site URL, name, description |

### Screens (`components/`)

| Folder | Responsibility |
|---|---|
| `home/` | Marketing page sections, copy, motion, emotion field |
| `pages/` | Journal, Memory, Progress screens and their hooks |
| `settings/` | Account, appearance, general, memory, privacy |
| `onboarding/` | Five-step first-run flow |
| `auth-gate.tsx` | Login/register form |
| `admin/` | Admin login, dashboard, system panel |
| `field/` | The animated emotion field behind the app |
| `companion/` | Five avatar implementations and their shared family |
| `ai-elements/`, `ui/` | Vendored primitives (conversation, prompt input, task, tool, buttons, dialogs) |
| `brand/` | Logo and wordmark |

### Styles (`styles/`)

- `tokens.css` — colour, emotion channels, day/night grades, type, radii.
- `components.css` — `ml-glass`, `ml-eyebrow`, `ml-display`, grain, focus.

## 5. MongoDB collections

| Collection | Contents |
|---|---|
| `users` | Account, age group, onboarding flag, preferences |
| `user_sessions` | Refresh sessions and device list (`jti`, user agent, timestamps) |
| `token_blocklist` | Logged-out access tokens until expiry |
| `sessions` | Chat sessions and their `turns` transcript |
| `user_memory` | People, trigger topics, coping, preferences, raw notes |
| `journal_entries` | Title, text, prompt used, timestamps |
| `mood_logs` | One mood point per completed turn |
| `pending_checkins` | One scheduled check-in per closed session |
| `progress_insights` | Cached weekly insight per user |
| `safety_events` | Safety verdicts; message stored as a hash |
| `audit_log` | Admin and account-level audit entries |

Every user-owned query is scoped by `user_id`; there is no cross-user read path.

## 6. External services

| Service | Used for | Failure behaviour |
|---|---|---|
| MongoDB Atlas | All persistence | Fail closed: the app does not start or claim ready |
| Groq | Assessment, specialist, reviewer | Fall back to stub text, mark `degraded`, never invent confidence |
| Pinecone | Curated therapy retrieval | Turn continues without notes; `rag.status = "failed"` |
| Langfuse | Metadata-only traces | Tracing stops; the turn is unaffected |
| Vercel / Render | Hosting | Platform-level; documented in the deployment runbook |

## 7. Trace one chat turn

1. **Send.** `composer.tsx` calls `MindLensSocket.sendMessage(text)` in
   `lib/websocket.ts`, which sends
   `{type:"message", text, session_id, timestamp}`.
2. **Authenticate.** `routers/chat.py` validates the JWT from the subprotocol
   and checks the user owns the session.
3. **Loop.** `chat_services/flow.py` rate-limits, caps length, loads the last
   ten turns and `user_memory`, then writes the user turn **before** inference.
4. **Safety.** `hosted_graph.py::_safety_gate` runs regex screening. A crisis
   match sets `crisis_flag` and routes straight to `finalize`; Groq and Pinecone
   are not called.
5. **Assess.** `_assess` asks the 70B model for constrained JSON (emotion,
   distress, route, review flag) and builds the EOS.
6. **Recall.** `_memory_recall` calls `memory_recall.recall_for_turn`, merges
   typed preferences onto the EOS, and emits a `stage_update`.
7. **Retrieve.** `_retrieve` skips trivial or crisis turns; otherwise Pinecone
   returns curated passages or the turn records `degraded: ["pinecone"]`.
8. **Reply.** `_specialist` asks the 8B or 70B model for one reply in the chosen
   route's voice, using the specialist context.
9. **Review.** High-distress or complex turns get one 70B reviewer that can
   approve or replace the reply.
10. **Finalize.** `response_validator.py` guards the text and
    `hosted_graph_result.result_contract` builds the single result dictionary.
11. **Stream.** `streaming_pipeline.py` sends `thinking_update`, then
    `stream_chunk` frames, then `response`. `use-chat-frames.ts` builds a
    provisional bubble and replaces it with the authoritative text.
12. **Persist.** `flow.py` saves the assistant turn, a mood log, and a safety
    event, then extracts memory facts into `user_memory`.
13. **Close.** On disconnect, `chat.py` marks the session ended and
    `services/checkins.py` schedules one check-in for the next visit.

## 8. Where to change what

| I want to change… | Open… |
|---|---|
| The reply voice or routing | `backend/app/agents/hosted_graph.py` |
| What counts as a crisis | `backend/app/agents/safety_gate.py` and its red-team tests |
| What memory is recalled | `backend/app/core/memory_recall.py` |
| What gets written to memory | `backend/app/services/memory_extraction.py` |
| When a check-in is scheduled | `backend/app/services/checkins.py` |
| A REST payload | the matching `*_schemas.py` and router |
| A WebSocket frame | `backend/app/core/connection_messages.py`, then `frontend/src/lib/types_chat.ts` |
| Chat rendering | `frontend/src/components/chat/` |
| Colours, type, day/night | `frontend/src/styles/tokens.css` |
| Public metadata | `frontend/src/app/layout.tsx` and `frontend/src/lib/site.ts` |
