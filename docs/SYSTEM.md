# MindLens - SYSTEM.md
## Version: 1.0 | Final Baseline Architecture | Generated: 2026-07-03
## Author: Amiru Umavin Mallawa Arachchi | Cardiff Metropolitan University / ICBT Campus

> This document is the single source of truth for MindLens.
> It defines the backend, frontend, machine-learning models, safety system,
> agent behavior, data architecture, testing expectations, deployment strategy,
> and non-negotiable rules.
>
> Any AI assistant or developer working on MindLens must read this file before
> making changes. Do not invent new architecture, models, therapies, storage
> systems, or UI flows outside this document. If something is unclear, ask the
> student before changing the system direction.

---

## 0. Architecture At A Glance

| Area | Final Specification |
|---|---|
| Product | MindLens, a personalized mental wellbeing companion |
| Target users | Teen users aged 16-19 and young adults aged 20-30 |
| Tone | Wise coaching friend: practical, warm, personalized, non-clinical |
| Release scope | Text-only web app. No voice pipeline in this release |
| Frontend | Next.js 15, Claude-style three-column layout |
| Backend | FastAPI, async-first, MongoDB, WebSocket chat |
| Realtime transport | WebSocket for chat and streaming agent activity |
| LLM provider | Groq only for therapy generation |
| LLM routing | A smaller/faster Groq model for simple turns, a larger one for emotional or complex turns — see §9 for the current pair; Groq's lineup has changed underneath this once already |
| ML models | Five MindLens Hugging Face models: emotion, mental health, crisis, RAG reranker, distortion |
| Safety | Hardwired safety gate runs before every agent and cannot be bypassed |
| Crisis response | Template-only crisis agent. Zero LLM calls during crisis |
| RAG | ChromaDB vector retrieval plus MindLens RAG reranker |
| Memory | MongoDB user profile, session memory, people graph, progress records |
| Music | iTunes Search API — no login or connection step, static fallback if unreachable |
| Scheduler | APScheduler inside FastAPI for check-ins. No Redis required |
| Admin | Separate admin surface for users, health, model status, reports, and sessions |
| Security | JWT in httpOnly cookies, ownership-scoped MongoDB queries, rate limits everywhere |
| Project rule | Safety, privacy, and student architecture decisions override convenience |

---

## 1. Project Identity

**MindLens** is a multi-agent agentic AI system for personalized mental health
detection, supportive conversation, therapy-style interventions, and
longitudinal wellbeing management.

| Attribute | Value |
|---|---|
| Student | Amiru Umavin Mallawa Arachchi |
| Student number | CL/BSCSD/33/82 |
| Cardiff number | st20311878 |
| Institution | Cardiff Metropolitan University / ICBT Campus, Colombo, Sri Lanka |
| Program | BSc (Hons) Software Engineering - Final Year Project |
| Deadline | August 11, 2026 |
| GitHub | github.com/AmiruMallawarachchi |
| Model host | Hugging Face: AmiruMallawarachchi |

MindLens is **not** a clinical service, diagnostic tool, emergency service, or
replacement for professional care. It is a personalized wellbeing companion that
helps users understand emotions, reflect, regulate distress, build routines, and
notice progress over time.

Core philosophy:

> Therapy did not fix me. Therapy gave me the tools to fix myself, over and over
> again for the rest of my life.

MindLens should help users build those tools.

---

## 2. Product Philosophy - The Wise Coaching Friend

MindLens must never sound like a generic mental-health chatbot. It should sound
like a wise, emotionally intelligent friend who knows the user, remembers what
matters, asks good questions, and gives practical choices.

### 2.1 Voice And Style

MindLens responses must:

- Use the user's preferred name naturally.
- Remember relevant people in the user's life when context makes it useful.
- Ask for the root cause before giving advice.
- Normalize emotion without dismissing it.
- Connect emotional support to practical next steps.
- Offer choices at the end: music, breathing, journaling, planning, or talking.
- Stay concise, usually 4-5 sentences.
- Avoid robotic validation phrases.

MindLens must not say:

- "I understand your feelings."
- "That must be hard."
- "I hear you."
- "As an AI language model."
- "You have depression/anxiety/PTSD."
- "You should take medication."

MindLens can say:

- "That pressure makes sense, Amiru."
- "Let's slow this down and find the real reason first."
- "Is this fear about failing, disappointing someone, or feeling unprepared?"
- "We can handle this in pieces."
- "Do you want music, breathing, journaling, or just to talk for a minute?"

### 2.2 Age-Adaptive Tone

| Age group | Rule | Tone |
|---|---|---|
| Teen | `user.age <= 19` | Shorter, lighter, more casual, school/family/peer aware |
| Young adult | `user.age >= 20` | Slightly deeper, structured, career/relationship aware |

Age changes tone only. It must not weaken safety behavior.

### 2.3 Therapy Identity

MindLens uses therapy-informed approaches, but it does not pretend to be a
therapist. The interface may show a subtle therapy mode badge:

- CBT
- DBT
- ACT
- Motivational Interviewing
- Mindfulness
- Narrative reflection

The user may request a mode change, but safety and clinical-risk routing always
override user preference.

---

## 3. Final System Architecture

```text
USER
  |
  v
Next.js 15 Frontend
  - Sidebar: sessions, new chat, settings
  - Main chat: messages, mode badge, input
  - Right panel: thinking, EOS, memory, model health
  - Dashboard: progress, mood, routines, memory
  - Onboarding: profile, age, preferences, goals
  - Admin: health, users, models, reports
  |
  v
FastAPI Backend
  |
  +-- Auth middleware
  +-- Rate limit middleware
  +-- Request ownership checks
  +-- PII anonymizer
  |
  v
Layer 0: Safety Gate
  - Regex crisis scan
  - MindLens crisis model
  - Semantic crisis similarity
  - Any trigger routes to CrisisAgent only
  |
  v
Parallel ML Inference
  - Emotion classifier
  - Mental-health classifier
  - Distortion classifier
  - RAG reranker where retrieval is needed
  |
  v
Emotional Operating System
  - emotion, distress, modality, trust, fatigue
  - receptiveness, age group, memory, people graph
  |
  v
Agent Orchestrator
  - chooses and runs agents
  - calls Groq only when safe
  - retrieves RAG knowledge where useful
  |
  v
Response Assembler
  - combines outputs
  - validates response
  - appends disclaimer
  - streams to frontend
  |
  v
MongoDB Memory + Sessions + Audit Logs
```

---

## 4. Technology Stack

### 4.1 Backend

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Runtime | Python 3.11+ |
| Realtime | WebSocket |
| Database | MongoDB Atlas or local MongoDB |
| Async DB driver | Motor |
| Scheduler | APScheduler |
| Auth | JWT access and refresh tokens in httpOnly cookies |
| Password hashing | bcrypt |
| LLM | Groq |
| Local ML | Hugging Face Transformers + PyTorch |
| Vector store | ChromaDB embedded |
| Testing | pytest, pytest-asyncio |
| Linting | Ruff |
| Typing | mypy |

### 4.2 Frontend

| Layer | Technology |
|---|---|
| Framework | Next.js 15 |
| Language | TypeScript |
| UI | React |
| Styling | Tailwind CSS |
| Realtime | WebSocket |
| Auth | Cookie-based session flow |
| Deployment | Vercel or Railway static/frontend |

### 4.3 External Services

| Service | Purpose |
|---|---|
| Groq | Therapy response generation |
| Hugging Face | Hosted model repositories |
| Apple iTunes Search API | Music track search, no auth required |
| MongoDB Atlas | Production persistence |
| Vercel | Frontend deployment target |
| Cloudflare Tunnel | Exposes the backend (models loaded in-process, so it runs on developer hardware, not a hosted platform) — see docs/DEPLOYMENT.md for why |

---

## 5. MindLens Model Registry

MindLens uses five dedicated models. These models are first-class parts of the
architecture and must be loaded, monitored, tested, and exposed in admin/model
health views.

### 5.1 Model 1 - Emotion Classifier

| Field | Value |
|---|---|
| Hugging Face ID | `AmiruMallawarachchi/mindlens-emotion-classifier` |
| Task | Text classification |
| Size | Approximately 0.1B parameters |
| Role | Detect user emotion and emotional tone |
| Pipeline name | `emotion` |
| Used by | EOS builder, empathy agent, music agent, mindfulness agent, dashboard |
| Expected output | Emotion label scores |
| Minimum acceptance | 80% test accuracy before final wiring |

Purpose:

- Identify surface emotion.
- Help infer core emotion.
- Drive intervention selection.
- Feed progress charts.
- Adjust music, journaling, and mindfulness choices.

### 5.2 Model 2 - Mental Health Classifier

| Field | Value |
|---|---|
| Hugging Face ID | `AmiruMallawarachchi/mindlens-mh-classifier` |
| Task | Text classification |
| Size | Approximately 0.1B parameters |
| Role | Detect mental-health related signal categories |
| Pipeline name | `mental_health` |
| Used by | EOS builder, progress agent, dashboard, safety escalation |
| Expected output | Multi-label condition/stress signal scores |
| Minimum acceptance | 80% test accuracy before final wiring |

Purpose:

- Detect signals such as anxiety, depression, stress, burnout, and PTSD-like
  language.
- Support wellbeing tracking without diagnosing.
- Increase distress score when risk signals rise.

Important:

The model output must never be shown as a diagnosis. It is an internal signal.

### 5.3 Model 3 - Crisis Classifier

| Field | Value |
|---|---|
| Hugging Face ID | `AmiruMallawarachchi/mindlens-crisis` |
| Task | Crisis text classification |
| Size | Approximately 67M parameters |
| Role | Detect crisis or self-harm risk |
| Pipeline name | `crisis` |
| Used by | Safety gate only |
| Threshold | 0.45 |
| Minimum acceptance | High recall, greater than 95% on red-team crisis set |

Purpose:

- Detect self-harm, suicidal ideation, harm-to-others, severe hopelessness, and
  coded crisis language.
- Trigger crisis mode before any normal agent runs.

Non-negotiable:

If this model triggers, MindLens must not call Groq. It must route to
template-only crisis support.

### 5.4 Model 4 - RAG Reranker

| Field | Value |
|---|---|
| Hugging Face ID | `AmiruMallawarachchi/mindlens-rag-reranker` |
| Task | Text classification / relevance reranking |
| Size | Approximately 22.7M parameters |
| Role | Rerank retrieved therapy knowledge |
| Pipeline name | `rag_reranker` |
| Used by | RAG retriever, agent prompt context, admin model health |
| Minimum acceptance | 80% relevance accuracy on evaluation set |

Purpose:

- Improve retrieved therapy knowledge before LLM generation.
- Prefer context that matches emotion, age group, modality, and user situation.
- Reduce irrelevant or generic RAG injection.

RAG flow:

```text
User text + EOS
  -> ChromaDB candidate retrieval
  -> MindLens RAG reranker
  -> top-k safe context chunks
  -> agent prompt context
```

### 5.5 Model 5 - Cognitive Distortion Classifier

| Field | Value |
|---|---|
| Hugging Face ID | `AmiruMallawarachchi/mindlens-distortion-classifier` |
| Status | Planned / about to be completed |
| Task | Cognitive distortion classification |
| Role | Detect distorted thinking patterns |
| Pipeline name | `distortion` |
| Used by | Distortion agent, challenge agent, CBT mode |
| Expected labels | 10 CBT distortion categories plus none/unclear |
| Minimum acceptance | 80% test accuracy before final wiring |

Expected distortion labels:

- All-or-nothing thinking
- Catastrophizing
- Overgeneralization
- Mental filter
- Disqualifying the positive
- Mind reading
- Fortune telling
- Emotional reasoning
- Should statements
- Personalization
- Labeling
- None / unclear

Purpose:

- Detect thinking patterns using a dedicated classifier, not a prompted LLM
  guess.
- Trigger gentle CBT reflection only when the user is stable enough.
- Avoid challenging users during crisis or very high distress.

Temporary rule:

Until the fifth model is fully wired, heuristic or LLM fallback may be used only
as a development bridge. The final architecture requires this dedicated model.

---

## 6. Emotional Operating System

The Emotional Operating System (EOS) is the central state object built for every
safe user turn.

EOS fields:

| Field | Meaning |
|---|---|
| `surface_emotion` | Emotion directly expressed |
| `core_emotion` | Likely deeper emotion |
| `suppressed_emotion` | Emotion possibly hidden or secondary |
| `distress_level` | 0.0 to 1.0 composite distress |
| `valence` | positive, negative, or neutral |
| `modality` | CBT, DBT, ACT, MI, Mindfulness, Narrative |
| `trust_level` | User trust in MindLens |
| `alliance_score` | Relationship strength with system |
| `session_depth` | Depth of current session |
| `mental_fatigue` | Fatigue/burnout signal |
| `receptiveness` | Openness to music, breathing, journaling, challenge, routine |
| `age_group` | teen or adult |
| `people_graph` | Important people in the user's life |
| `llm_tier` | fast or deep |
| `agent_flags` | Which agents should run |

Distress calculation must combine:

- Crisis signal.
- Negative emotion severity.
- Mental-health signal intensity.
- Sudden escalation across turns.
- Repetition, all-caps, and intensity markers.

EOS is internal. The frontend may show a safe, simplified version in the thinking
panel, but raw model outputs are admin/developer-only.

---

## 7. Agent System

MindLens uses specialized agents. Agents do not decide safety. Safety is already
decided before they run.

### 7.1 Required Agents

| Agent | Role |
|---|---|
| `safety_gate` | Runs before everything, routes crisis |
| `crisis_agent` | Template-only crisis response |
| `empathy_agent` | Main warm response and root-cause question |
| `mindfulness_agent` | Breathing, grounding, body scan |
| `reflection_agent` | Summarizes patterns and emotional meaning |
| `distortion_agent` | Uses distortion model for CBT pattern detection |
| `challenge_agent` | Gentle Socratic challenge when safe |
| `routine_agent` | Builds small practical routines |
| `journaling_agent` | Offers reflective prompts |
| `music_agent` | Recommends real, playable tracks via iTunes search |
| `checkin_agent` | Generates proactive follow-up message |
| `checkin_scheduler` | Schedules future check-ins |
| `progress_agent` | Weekly progress and insight summaries |
| `personality_agent` | Adapts tone to user style |
| `session_memory_save` | Saves session memory and extracted facts |

### 7.2 Agent Routing Rules

| Condition | Agents |
|---|---|
| Crisis detected | `crisis_agent` only |
| Every safe turn | `empathy_agent`, `session_memory_save` |
| Distress above 0.5 | `mindfulness_agent` |
| Music receptive or distress above 0.4 | `music_agent` |
| CBT modality active | `distortion_agent` |
| Trust high and stability safe | `challenge_agent` |
| Fatigue high | `routine_agent` |
| Journaling receptive and stable | `journaling_agent` |
| Every 3 turns | `checkin_scheduler` |
| Every 5 turns or session end | `progress_agent` |

### 7.3 Response Assembly Order

1. Crisis response, if crisis.
2. Empathy.
3. Mindfulness.
4. Reflection.
5. Distortion insight.
6. Challenge question.
7. Routine/action plan.
8. Journaling.
9. Music.
10. Check-in/progress.
11. Mandatory disclaimer.

The final response must feel like one coherent message, not separate agent
fragments pasted together.

---

## 8. Safety Architecture

Safety is Layer 0. It runs before every agent, every model-driven therapy
decision, every RAG retrieval, and every Groq call.

### 8.1 Safety Gate Layers

| Layer | Method | Where | Target latency |
|---|---|---|---|
| L1 | Regex crisis pattern scan | `safety_gate.evaluate()` | less than 1ms |
| L2 | `mindlens-crisis` classifier, fires above 0.45 | orchestrator, after L1 clears | less than 60ms |

Either trigger means crisis mode.

L1 is deliberately first and independent of model health: if the
classifier is down, unloaded or returns nothing, the regex screen still
runs and still catches. A turn where the classifier was unavailable is
logged as degraded rather than passing silently.

**There is no semantic-search layer.** An earlier design called for a
third layer doing embedding search against a crisis corpus; it was never
built, and this table previously described it as if it were. It is not in
the code, so it is not claimed here. Adding it would improve recall on
paraphrased crisis language that neither the patterns nor the classifier
catch — that is the honest gap, and it is future work.

### 8.1.1 Known limitation: L2 over-triggers on ordinary distress

Measured against the deployed `mindlens-crisis` classifier:

| Message | Score | Verdict |
|---|---|---|
| "I want to kill myself" | 0.88 | crisis, correct |
| "It is mostly that I am scared it will not be good enough." | 0.82 | **false positive** |
| "so i need a help okay" | 0.72 | **false positive** |
| "There is no point in living" | 0.59 | crisis, correct |
| "I have been really anxious about my final year project." | 0.03 | safe, correct |

On a 15-benign / 6-crisis probe set at the shipped 0.45 threshold: 6/6
crisis caught, 2/15 benign flagged. Raising the threshold does not fix
this. At 0.85 the false positives vanish but only 4/6 real crisis
messages are caught — the two lost include "There is no point in
living". Six hundredths separate a student worrying about coursework
from a genuine suicide statement, so the classes are not linearly
separable by score at any cutoff.

The cause is train/serve mismatch, in three parts:

1. **Composition.** The training set's `safe` class is Reddit meme
   chatter; its `crisis` class is long, sincere, distressed posts. The
   model never saw text that was emotionally serious and *not* a crisis,
   so it learned "heartfelt equals crisis".
2. **Preprocessing.** The upstream corpus is lemmatized and
   stopword-stripped ("not see point anymore"). Nothing in the serving
   path preprocesses anything — `predict_all` passes raw user text
   directly to the model.
3. **Length.** Training posts have a median of 30 words; real chat
   messages are four to fifteen.

Aggregate F1 concealed all of this, because the test split was drawn
from the same distribution as the training data.

The threshold is deliberately left at 0.45. It errs toward interrupting
a conversation that did not need interrupting, rather than missing one
that did — the right direction for this failure to point, but a real
cost to the experience, and stated here rather than smoothed over.

`scripts/build_crisis_dataset.py` rebuilds the corpus against all three
mismatches and `scripts/train_crisis_model.py` retrains from it,
publishing to a separate repo so the live classifier is not overwritten
before the numbers are checked. Until that lands, the limitation above
is current.

### 8.2 Crisis Mode

When crisis is detected:

- Do not call Groq.
- Do not call empathy/mindfulness/music/challenge agents.
- Do not retrieve RAG therapy context.
- Do not provide long therapy explanations.
- Use only approved crisis templates.
- Include Sri Lankan emergency resources.
- Save the safety event to audit logs.

Required crisis resources:

- NIMH Sri Lanka: 1926
- Emergency: 119
- Local suicide prevention resources where available

### 8.3 Crisis Threshold

The crisis model threshold is `0.45`.

Never raise this threshold for convenience, cost, or false-positive reduction
without a student-approved safety review. The system prioritizes recall.

---

## 9. LLM Architecture

Groq is the only therapy generation provider.

| Tier | Model | Use |
|---|---|---|
| Fast | `openai/gpt-oss-20b` | Simple safe turns, short responses |
| Deep | `openai/gpt-oss-120b` | Emotional, complex, high-distress safe turns |

Both are reasoning models — Groq's `llama-3.1-8b-instant`/`llama-3.3-70b-versatile`
pair (the original choice here) was removed from Groq's catalog entirely, not
just renamed, discovered when every reply started silently falling back to
the canned stub. Reasoning models spend completion tokens on hidden
chain-of-thought before the visible answer; every call pins
`reasoning_effort: "low"` (`groq_client.py`) so that overhead stays small
instead of occasionally consuming the whole token budget and returning
nothing.

Use deep tier when:

- Distress is at least 0.5.
- Session depth is meaningful.
- Multiple emotions conflict.
- User asks for serious help.
- Memory/person context matters.

Never use LLMs for:

- Crisis response.
- Diagnosis.
- Medication advice.
- Safety gate override.
- Secret or system-prompt decisions.

All Groq calls must:

- Have an 8 second timeout.
- Use separate system and user messages.
- Keep user text out of system prompts.
- Use PII-anonymized text where model inference does not need raw PII.
- Cap max tokens by agent.
- Fall back gracefully.

---

## 10. Memory System

MindLens memory exists to personalize support, not to surveil the user.

### 10.1 Memory Types

| Type | Contents |
|---|---|
| User profile | Name, nickname, age, age group, preferences |
| People graph | Important people, relationships, context |
| Session memory | Session turns, summaries, EOS timeline |
| Long-term memory | Stable patterns, goals, coping preferences |
| Progress memory | Mood trends, interventions used, weekly insights |
| Check-in memory | Scheduled and delivered check-ins |

### 10.2 User Control

Users must be able to:

- View stored memory.
- Delete memory entries.
- Delete people from people graph.
- Delete account and all associated data.

Deletion propagation target: under 60 seconds.

### 10.3 Memory Safety

- Never store plaintext passwords.
- Never store unnecessary secrets.
- Do not inject more than the most relevant memory into prompts.
- If a person is deleted from memory, future prompts must not reference them.
- Session summaries may retain historical mentions only with deleted-person tags.

---

## 11. RAG System

RAG provides therapy-informed knowledge, grounding, and intervention structure.

### 11.1 Retrieval Flow

```text
Input:
  user message
  EOS
  active modality
  age group
  optional distortion label

Process:
  ChromaDB vector retrieval
  MMR diversity selection
  MindLens RAG reranker
  safety filter
  top-k context injection
```

### 11.2 RAG Rules

- RAG must not run during crisis mode.
- RAG context must be short and relevant.
- RAG must not contain diagnostic claims.
- RAG must be filtered before prompt injection.
- Admin/dev tools may show retrieved chunks.
- User-facing thinking panel may show simplified memory and knowledge summaries.

---

## 12. Music System

Music is an intervention, not decoration.

Originally designed around Spotify OAuth (user-connected playback and
personalization). Not shipped: Spotify's Web API has required the
*developer's own account* to hold an active Premium subscription since
February/March 2026, on top of the `/recommendations` endpoint this design
depended on being withdrawn for new apps in November 2024. Rebuilt on
Apple's iTunes Search API instead — no auth, no account connection, no
personal subscription required by anyone.

### 12.1 How it works

| Path | Description |
|---|---|
| iTunes search | Emotion maps to a genre + mood search term (no login, no connection step); returns real tracks with a 30-second preview clip the client plays directly |
| Static fallback | Used only if iTunes itself is unreachable — names a track and artist, never a fabricated link |

### 12.2 Music Agent Rules

The music agent considers:

- Emotion.
- Distress.
- Energy level.
- User preference.
- Time of day.
- Whether the user wants regulation, comfort, focus, or release.

Music must not be suggested during crisis as a substitute for emergency support.

---

## 13. Frontend Specification

The frontend must be a usable product, not a marketing page.

### 13.1 Main Layout

MindLens uses a Claude-style three-column interface:

| Region | Contents |
|---|---|
| Left sidebar | New chat, session history, dashboard, settings |
| Center | Chat, therapy mode badge, messages, input |
| Right panel | Thinking, EOS, agents, memory, model transparency |

### 13.2 Pages

| Page | Purpose |
|---|---|
| Chat | Main conversation experience |
| Onboarding | Age, nickname, preferences, goals, consent |
| Dashboard | Mood trends, progress, routines, memory |
| Memory | View and manage stored memory |
| Admin | System health, users, models, sessions, reports |

### 13.3 Thinking Panel

Collapsed by default. Shows safe transparency:

- Agents used.
- Emotion/distress summary.
- Therapy mode.
- Memory recalled.
- Music/routine/journaling suggestions.

Do not show raw hidden prompts to normal users.

### 13.4 Admin Model Health Drawer

Admin/dev view must show:

- Model ID.
- Loaded status.
- Last inference latency.
- Error count.
- Accuracy/evaluation summary.
- Fallback mode.
- Last updated metadata.

---

## 14. API Surface

### 14.1 Core Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/register` | Register user |
| `POST /api/v1/auth/login` | Login |
| `POST /api/v1/auth/refresh` | Refresh access |
| `POST /api/v1/auth/logout` | Logout |
| `GET /api/v1/auth/me` | Current user |
| `POST /api/v1/sessions` | Create session |
| `GET /api/v1/sessions` | List owned sessions |
| `GET /api/v1/sessions/{id}` | Read owned session |
| `DELETE /api/v1/sessions/{id}` | End/delete owned session |
| `GET /api/v1/memory` | View memory |
| `DELETE /api/v1/memory/{id}` | Delete memory item |
| `GET /api/v1/dashboard` | Progress dashboard data |
| `POST /api/v1/onboarding` | Save onboarding |
| `WS /ws/chat/{session_id}` | Realtime chat |

### 14.2 Admin Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/admin/login` | Admin login |
| `GET /api/v1/admin/health` | System health |
| `GET /api/v1/admin/models` | Model health |
| `GET /api/v1/admin/users` | User list |
| `GET /api/v1/admin/sessions/{id}` | Session inspector |
| `GET /api/v1/admin/reports` | Safety/user-study reports |

### 14.3 Security Rule For Every Endpoint

Every endpoint must pass this checklist:

- Auth required unless explicitly public.
- Rate limit enforced.
- MongoDB query scoped by `user_id` from JWT.
- Client-provided `user_id` ignored for ownership.
- No secrets returned.
- No raw PII in logs.
- Validation through Pydantic.
- Safe error messages only.

---

## 15. Database Design

Required MongoDB collections:

| Collection | Purpose |
|---|---|
| `users` | User accounts and profile |
| `sessions` | Chat sessions and turns |
| `user_memory` | Long-term memory |
| `user_memory_archive` | Trimmed archived memory |
| `pending_checkins` | Scheduled check-ins |
| `audit_log` | Sensitive operations |
| `token_blocklist` | Revoked JWTs |
| `model_health` | Model status snapshots |
| `reports` | Evaluation and admin reports |

Indexes:

- `users.email` unique.
- `sessions.user_id`.
- `sessions.session_id`.
- `user_memory.user_id`.
- `pending_checkins.user_id`.
- `pending_checkins.expires_at` TTL.
- `token_blocklist.exp` TTL.
- `audit_log.timestamp`.

---

## 16. Authentication And Security

### 16.1 Token Rules

- Access tokens must be in httpOnly cookies.
- Refresh tokens must be in httpOnly cookies.
- Do not use localStorage for JWTs.
- Do not pass tokens in URL parameters.
- WebSocket authentication must happen through secure handshake/header/cookie
  mechanisms.

### 16.2 Security Requirements

- No secrets in code or Git.
- All secrets come from environment variables.
- Passwords hashed with bcrypt.
- Login lockout after 5 failed attempts for 15 minutes.
- JWT tampering returns 401.
- Admin routes require admin role.
- All sensitive actions are audit logged.
- Prompt injection attempts are logged as security events.
- User text never enters the system prompt string.

### 16.3 PII Protection

PII must be stripped before model calls where raw PII is unnecessary:

- Email.
- Phone.
- Address.
- NIC/passport-like IDs.
- Bank/account numbers.
- Full names where detected.

No model-call logs may contain raw PII.

---

## 17. Reliability And Startup

### 17.1 Startup Sequence

On FastAPI startup:

1. Connect to MongoDB.
2. Verify indexes.
3. Load all required models, or mark unavailable.
4. Initialize ChromaDB.
5. Populate RAG if empty.
6. Start APScheduler.
7. Verify Groq connectivity.
8. Expose readiness status.

### 17.2 Graceful Degradation

| Failure | Behavior |
|---|---|
| Groq down | Template fallback, session continues |
| MongoDB down | Retry, then safe 503 |
| iTunes unreachable | Static fallback, no fabricated links |
| RAG empty | Agents continue without RAG |
| Model unavailable | Mark unhealthy, use approved fallback only |
| Scheduler down | Restart or resume on next startup |

No normal user flow should crash silently.

---

## 18. Performance Targets

| Operation | Target | Max |
|---|---:|---:|
| Regex safety scan | less than 1ms | 5ms |
| Crisis classifier | less than 60ms | 100ms |
| Semantic safety search | less than 80ms | 150ms |
| Parallel model inference | less than 200ms | 500ms |
| EOS construction | less than 5ms | 20ms |
| RAG retrieval and rerank | less than 150ms | 300ms |
| Groq first token | less than 800ms | 1500ms |
| Simple full response | less than 1500ms | 3000ms |
| Complex full response | less than 2000ms | 5000ms |
| MongoDB indexed read | less than 20ms | 50ms |
| WebSocket overhead | less than 10ms | 30ms |

---

## 19. Testing Strategy

### 19.1 Required Test Groups

| Group | Required coverage |
|---|---|
| Unit tests | Agents, EOS, models, auth, memory, RAG |
| Integration tests | Full chat pipeline, safety gate, WebSocket, DB |
| Security tests | JWT, ownership, rate limit, prompt injection |
| Safety tests | Crisis red-team set, zero LLM in crisis |
| Model tests | Accuracy, latency, label mapping |
| Frontend tests | Onboarding, chat, dashboard, admin |
| Load tests | 50 concurrent users |

### 19.2 Safety Acceptance

- Crisis recall greater than 95% on red-team set.
- False positive rate under 15% on benign set.
- Zero Groq calls during crisis.
- NIMH number included in 100% of crisis responses.
- PII stripped in 100% of model-call test cases.

### 19.3 Model Acceptance

Each of the five models must reach at least 80% test accuracy or its approved
metric before final publication/wiring.

Models:

1. Emotion classifier.
2. Mental-health classifier.
3. Crisis classifier.
4. RAG reranker.
5. Cognitive distortion classifier.

---

## 20. Deployment

### 20.1 Backend

Target:

- Railway.
- Python 3.11+.
- Uvicorn/FastAPI.
- Environment-based secrets.
- MongoDB Atlas.
- Persistent ChromaDB path where supported.

### 20.2 Frontend

Target:

- Vercel or Railway.
- Next.js 15.
- Environment-specific backend URL.
- Secure cookie support.

### 20.3 Required Environment Variables

```text
APP_ENV
MONGODB_URL
MONGODB_DB_NAME
JWT_SECRET_KEY
JWT_REFRESH_SECRET_KEY
ADMIN_JWT_SECRET
ENCRYPTION_KEY
GROQ_API_KEY
HF_TOKEN
CORS_ORIGINS
```

---

## 21. User Study And Evaluation

MindLens must support final-year evaluation with measurable outcomes.

| Criterion | Target |
|---|---:|
| Empathy rating | At least 4.0 / 5.0 |
| Felt personalized | At least 80% agree |
| Onboarding completion | 100% in study group |
| Would use again | At least 4 of 5 users |
| Therapy mode understood | At least 80% |
| PHQ-9 change after 3 sessions | More than 3-point improvement where applicable |
| Felt different from chatbot | At least 4 of 5 agree |

MindLens must store anonymized evaluation artifacts suitable for the final
project report.

---

## 22. Corner Cases

MindLens must handle:

- Empty messages.
- Very long messages.
- Emoji-only messages.
- Repeated messages.
- All-caps distress.
- Sinhala/Tamil/non-English messages.
- Offensive input.
- Prompt injection.
- Fictional self-harm text.
- User disconnect mid-response.
- Two tabs open.
- Expired JWT.
- Deleted account with old token.
- MongoDB timeout.
- Groq timeout.
- iTunes unreachable.
- RAG empty.
- Model unavailable.

No corner case should produce an unhandled exception, unsafe response, or broken
session state.

---

## 23. Build Phases

### Phase 1 - Verification Console

Goal: prove backend, models, agents, WebSocket, and safety.

Deliverables:

- Model health endpoint.
- Test chat console.
- Safety gate visible in logs/admin.
- EOS output visible in dev panel.
- WebSocket streaming works.

### Phase 2 - Core Product

Goal: usable MindLens app.

Deliverables:

- Onboarding.
- Real chat UI.
- Memory.
- Dashboard.
- RAG wired.
- Check-ins.
- Music recommendations (iTunes search).

### Phase 3 - Polish And Admin

Goal: final demo and evaluation readiness.

Deliverables:

- Full admin dashboard.
- Model health drawer.
- Session inspector.
- Mobile polish.
- User-study reports.
- Deployment hardening.

---

## 24. Non-Negotiable Rules

### Safety

1. Safety gate runs first on every message.
2. Crisis threshold is 0.45.
3. Crisis agent uses zero LLM calls.
4. Crisis response uses approved templates only.
5. Never diagnose.
6. Never recommend medication.
7. Always append the MindLens non-clinical disclaimer.
8. PII is stripped before model calls.

### Security

9. JWTs live in httpOnly cookies, not localStorage.
10. Do not pass tokens in URLs.
11. Every MongoDB query is scoped by authenticated user ownership.
12. Never trust client-provided `user_id`.
13. No secrets in code or Git.
14. Rate limiting exists on every endpoint.
15. Audit log every sensitive operation.
16. User text never enters system prompts.

### Reliability

17. Every external call has a timeout.
18. Every external dependency has a fallback.
19. Sessions are saved after every completed turn.
20. No unhandled exceptions in normal operation.

### Quality

21. The five MindLens models are the official model registry.
22. The distortion model is dedicated, not an LLM guess.
23. Groq is the only therapy generation provider.
24. Text-only release. Do not add voice in this version.
25. User controls memory.
26. Test every changed file.
27. Crisis red-team tests run before final release.
28. Student decisions override assistant assumptions.

---

## 25. Definition Of Done

MindLens v1.0 is complete when:

- User can onboard, chat, view progress, and manage memory.
- Safety gate is hardwired before all agents.
- All five models are registered, loadable, monitored, and tested.
- Crisis response never calls Groq.
- RAG retrieval and reranking are wired into safe turns.
- Groq fast/deep tier routing works.
- WebSocket chat streams responses and thinking updates.
- Admin can inspect model health and system health.
- Security checklist passes.
- Red-team safety tests pass.
- User-study workflow is ready.
- Production deployment runs without secrets in code.

---

## 26. Current Implementation Priority

The implementation should proceed in this order:

1. Replace old architecture assumptions with this v1.0 document.
2. Hardwire safety gate into the live chat/orchestrator path.
3. Register all five model IDs in configuration.
4. Add model health reporting.
5. Wire RAG retrieval and the RAG reranker.
6. Replace distortion heuristic with the dedicated distortion model when ready.
7. Build the real Next.js chat UI.
8. Build onboarding, memory, dashboard, and admin pages.
9. Run full unit, integration, safety, and security tests.
10. Deploy and run final user-study evaluation.

---

*MindLens SYSTEM.md v1.0 - Final Baseline Architecture.*
*This file replaces all previous SYSTEM.md drafts and is the starting point for final implementation.*
