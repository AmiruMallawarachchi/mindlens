# Mindlens

A wellbeing companion that reads the feeling underneath what someone writes,
remembers what matters, and helps them build tools to steady themselves.
Final-year project, built to production standards.

Users type things here they have told nobody. Every rule below exists
because of that.

## Stack

- **Frontend** — Next.js 15 (App Router, Turbopack), React 19, TypeScript,
  Tailwind. `/` is the marketing site, `/app` is the product.
- **Backend** — FastAPI, Motor/MongoDB Atlas, JWT in httpOnly cookies.
- **Agents** — a fixed safety gate, then five small models, then a team of
  therapy-modality agents. Groq for generation.

## Running it

```bash
# backend
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend
cd frontend && npm run dev
```

PowerShell (`;` instead of `&&`):

```powershell
# backend
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend
cd frontend; npm run dev
```

`--reload` does **not** reliably fire on this Windows setup. If backend
behaviour doesn't match the source, restart the process before debugging the
code.

`frontend/.env.local` has `NEXT_PUBLIC_PREVIEW_AUTH`. `1` bypasses login with
fixtures for UI work; it must be `0` to test anything real. It must never be
set in a deployed environment — it disables authentication entirely.

## Non-negotiables

These are product rules, not preferences.

1. **Never ship a control that does nothing.** If a setting can be changed,
   trace it all the way to the behaviour it changes before calling it done.
   A control that saves but is never read is the most common bug in this
   repo. Prefer leaving a feature out over shipping a fake one.
2. **Never claim something the code doesn't do.** Especially about privacy,
   safety, encryption or memory. An accurate small promise beats an
   impressive vague one; a false claim discovered later destroys the only
   thing this product sells. State limitations plainly — the honesty is the
   feature.
3. **The safety gate runs first on every turn and cannot be bypassed.**
   Crisis responses come from human-written templates with zero LLM calls.
   No preference, personality, instruction or setting may alter a crisis
   response.
4. **Nothing is remembered without appearing in Memory**, where the user can
   edit or delete it. Delete means delete — a hard delete across every
   collection, not a flag.
5. **User-authored text entering a prompt is untrusted.** Fence it, cap it,
   strip structure-faking characters, and state that it cannot override the
   safety rules. It may shape style, never behaviour.
6. **Every user-scoped database query filters by `user_id`.** Partial
   updates use dotted paths — never `$set` a whole subdocument.

## Design system

The source of truth is the approved Claude Design mockups, not prose specs.
Two projects exist: "Mindlens UI Mockups" (Chat, Chat Mobile, Home) and
"Mindlens System" (the decision archive, including the Progress / Journal /
Memory / Your Mindlens screens). **Check the mockup before building a screen
from a description.** Building from a text spec when a mockup existed has
cost real rework here.

- **Tokens only.** Colours come from `--ml-*` and `--e1/--e2/--e3` in
  `frontend/src/app/tokens.css`. No raw hex in components except where a
  value is genuinely outside the system (a fixed error red).
- **Day is the default grade**; night is a token swap via `data-grade`.
  Everything must be legible in both.
- **Emotion drives colour**, crossfading over 1.6s — never snapping. The
  read the UI *displays* and the palette it *paints with* are separate
  concerns: pinning a palette must not change what the classifier is
  reported to have said.
- **Radii and spacing** come from the `--r-*` scale.
- Nimbus and the nine other companions live in `lib/companions.ts`. The
  companion is a single morphing shape, not a layered cloud.

## UI/UX rules

1. **Honest empty and error states.** Never render a placeholder that looks
   like real data. If something failed, say what failed, near the thing that
   failed. One failing request must not blank a whole page.
2. **Loading is not a blank screen.** But don't show a spinner for something
   that resolves in 100ms either.
3. **Errors are recoverable and specific.** "Couldn't save that" beats
   "Error". Never a raw exception.
4. **Destructive actions need friction and an escape.** Irreversible ones
   need a typed confirmation, and the exit should be as easy to find as the
   confirm.
5. **Motion is restrained.** Long eases, few things moving at once, one
   focal point per screen. Everything respects
   `prefers-reduced-motion`.
6. **Accessible by default.** Real `aria-label`s, keyboard reachable, focus
   visible, contrast that holds in both grades. Note: an `aria-label`
   overrides text content for the accessible name — keep them consistent.
7. **The tone is a calm friend, not a clinician and not a brand.** Plain
   words. Never diagnose. Never say "I understand how you feel".

## Verifying work

Two different failures happen here and neither catches the other:

- **Logic that didn't apply** — saves, returns 200, changes nothing.
  Invisible in a screenshot. Caught by asserting facts: API status and body,
  computed CSS values, values re-read after a reload.
- **A visual fix that didn't land** — code changed, "fixed" was claimed, and
  on screen it is still wrong. Invisible in an API response. Caught only by
  looking.

So do both, and note the rule that gets skipped most:

**Taking a screenshot is not looking at one.** Open it with the Read tool
and actually view it. Never write "fixed" or "renders correctly" about
something you have not viewed — say "not visually confirmed" instead.
Screenshot the specific element (`clip` / `locator.screenshot()`), not just
the page: a broken 20px control is unreadable in a full-page shot.

Check both day and night grades, and re-check narrow widths if layout moved.
Always test the negative path.

Before saying a change is done:

```bash
cd frontend && npx tsc --noEmit && npx eslint src
cd backend && ../.venv/Scripts/python -m ruff check app/ && ../.venv/Scripts/python -m pytest tests/ -q
```

## Subagents

`.claude/agents/` — use them rather than doing these by eye:

- `dead-control-hunter` — after any settings/preferences change.
- `contract-sync` — after changing a model, endpoint or shared type.
- `persistence-review` — after touching a router that writes to Mongo.
- `claim-auditor` — before release, or when privacy/safety copy changes.
- `flow-verifier` — before calling any user-facing change done.
