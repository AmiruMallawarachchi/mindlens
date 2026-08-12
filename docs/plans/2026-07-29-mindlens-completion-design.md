# Mindlens completion — design

Date: 2026-07-29 · Status: Approved

## Context

Two design-project mockups exist in Claude Design:
- "Mindlens System" (`design.md` + `Mindlens System.dc.html`) — the original text spec used to build the Chat screen.
- "Mindlens UI Mockups" (`Mindlens Chat.dc.html`, `Mindlens Chat Mobile.dc.html`, `Mindlens Home.dc.html`) — hand-built, pixel-real mockups discovered mid-session. These are the authoritative source; the Chat screen was rebuilt to match them (Nimbus as a morphing blob, real breathe/music player cards, crisis panel copy, message actions, starter suggestions).

Progress, Journal, Memory, and Your Mindlens have no hand-built mockup — only `design.md` §4.2's text description. The backend for Progress (insight endpoint), Journal (CRUD + prompt), and Memory (CRUD) already exists and is tested.

## Decisions (user-approved)

1. **Theme**: day-default with a day/night toggle, matching the mockups' exact DAY/NIGHT palettes, persisted to `localStorage["ml-grade"]`.
2. **Routing**: `/` is the Home marketing page; the app (auth gate → chat) moves to `/app`.
3. **Remaining four pages**: built now, in the mockups' visual language (same tokens, panel/glass style, day/night) plus `design.md` §4.2's content spec — no separate mockup design phase.
4. **Priority**: chat polish, backend evidence, and a fully demoable app are all in scope — nothing is being cut.

## Scope

### A. Theme system
- Port DAY/NIGHT CSS variable sets verbatim from the mockups into `tokens.css` (`--paper`, `--deep`, `--ink`, `--muted`, `--faint`, `--panel`, `--panel-strong`, `--hairline`, `--hairline-strong`), mapped onto the existing `--ml-*` names so nothing else has to change.
- `data-grade="day"|"night"` on `<html>`, read from `localStorage["ml-grade"]` on mount, defaulting to `day`.
- Toggle button (sun/moon) in the chat header and the Home nav, shared logic.

### B. Routing
- `frontend/src/app/page.tsx` → Home (new).
- `frontend/src/app/app/page.tsx` → current `MindLensApp` (moved).
- Internal links updated ("Open the app", "Start a conversation" → `/app`).

### C. Home page
- Built from `Mindlens Home.dc.html` verbatim: nav, hero with animated blobs, portrait band (placeholder), philosophy quote, "How it works" (5 steps), Models band (5 model cards, dark), Emotion lab (interactive 12-state picker reusing the real `emotion.ts` module), Docs band, Safety band, footer.
- GSAP scroll-reveals reimplemented with `motion/react` (already a dependency) — same reveal-once effect, no new library.

### D. Chat completion
- Day/night toggle wired into the existing `ChatScreen`.
- Mobile breakpoint: sidebar collapses to a hamburger-triggered drawer under 780px (matching the mockup's mobile chat), inspector already hides under 1040px.

### E. Four remaining pages
- **Progress**: 3 metric cards (average mood, sessions, distress trend), 7-day emotion-coloured bars from real mood logs, weekly insight card from `GET /api/v1/dashboard/insight`, honest "N more sessions to unlock" placeholder under 7 sessions.
- **Journal**: prompt hero from `GET /api/v1/journal/prompt`, "Start writing" flow, recent-entries grid from `GET /api/v1/journal`, new-entry composer using existing CRUD.
- **Memory**: category cards (people / preferences / patterns / notes) from `GET /api/v1/memory`, edit + forget actions wired to existing PATCH/DELETE endpoints, empty states are honest, not fabricated.
- **Your Mindlens**: real page (not a modal) — Gentle↔Direct tone slider, memory depth selector, appearance (day/night + reduced-motion note), companion note. Requires one backend addition (below).

### F. Backend: preferences schema extension
`memory_recall.py` already reads `tone_preference` and `memory_depth` from the user's preferences document and acts on them (modality override, recall depth) — built earlier this session. But `PreferencesUpdate` in `app/routers/memory.py` doesn't yet accept those two fields, so there's no way to *set* them. Small, additive schema extension + tests; no behavior change to existing fields.

## Out of scope (unchanged from earlier)
- Memory *write* side (auto-extracting people/topics from conversation) — needs real NLP, too speculative.
- Full admin panel beyond existing health/model endpoints.
- Distortion model training/publishing.

## Order of implementation
1. Backend preferences schema extension + tests (small, unblocks Your Mindlens).
2. Theme system (foundation for everything visual).
3. Routing split (Home ⟷ /app).
4. Home page build.
5. Chat: day/night toggle + mobile drawer.
6. Progress, Journal, Memory, Your Mindlens pages.
7. Full verification: backend suite, frontend typecheck/lint/build, browser screenshots of every page in both grades.
