# MindLens — DESIGN.md

**Version:** 2.0 · Warm-paper direction · July 2026
**Status:** Design source of truth for the web client. Supersedes the dark-indigo-glass system in `frontend/src/app/tokens.css`.
**Scope:** Everything visual and interactive in the MindLens web client — colour, type, layout, motion, component anatomy, emotion behaviour, day/night grading, accessibility, and the mapping from backend payloads to UI state.

Read alongside `docs/SYSTEM.md` (architecture, models, safety rules — non-negotiable) and `docs/API.md` (payload shapes). **Where this document and SYSTEM.md disagree on behaviour, SYSTEM.md wins.** This document owns appearance only.

---

## 0. How to use this document

Three mockup files in the design project are the executable reference:

| File | What it specifies |
|---|---|
| `Mindlens Home.dc.html` | Marketing / publication site — hero, pipeline, models, emotion lab, docs, safety, footer |
| `Mindlens Chat.dc.html` | Desktop app — sidebar / conversation / inspector, all message anatomy, intervention players |
| `Mindlens Chat Mobile.dc.html` | Mobile chat — condensed anatomy, quick-feel chips |

The mockups are single-file HTML with inline styles. **Do not port them literally.** Port the *tokens, ratios, anatomy and behaviour* described below into the Next.js app as Tailwind theme values + CSS custom properties. Where a number appears in this document it is authoritative; where only the mockup has it, the mockup is authoritative.

### Implementation order (recommended)

1. §1 tokens → `tokens.css` + `tailwind.config.ts` theme extension.
2. §2 emotion field → `lib/emotion.ts` (replace existing palette, keep the classifier-folding logic).
3. §3 day/night grading → `ThemeProvider` + `localStorage` key `ml-grade`.
4. §5 chat shell + §6 message anatomy → `components/chat/*`.
5. §7 intervention players → `components/chat/breathe-card.tsx`, `music-card.tsx`.
6. §8 Nimbus → `components/nimbus.tsx`.
7. §9 marketing site → `app/(marketing)/page.tsx`.

---

## 1. Foundations

### 1.1 The direction, in one paragraph

MindLens looks like **warm paper with weather on it**. The surface is a soft off-white oat, the ink is warm charcoal, and everything structural is quiet: hairline borders, no heavy shadows, no chrome. All colour saturation in the product comes from *one source only* — the user's current emotional read, which lights the page from behind through soft blurred gradient fields. The interface should feel like a calm, well-lit room that changes its light depending on who walked in. It must never feel clinical (no charts-as-decoration, no medical blue, no dashboards) and never feel like a toy (no emoji as UI, no bouncy easing, no bright flat brand colours).

Reference vocabulary: editorial event-page layout — enormous tight-tracked display type, generous whitespace, mono eyebrow labels, a single serif voice for emotional moments.

### 1.2 Neutral tokens

Two grades (§3). Both are registered with `@property` so they can be transitioned.

```css
/* DAY (default) */
--paper:           #f3eee4;              /* page ground, warm oat */
--deep:            #0f0b08;              /* inverted sections (models/emotions band) */
--ink:             #221d15;              /* primary text, warm charcoal */
--muted:           rgba(34,29,21,0.62);  /* body copy, secondary */
--faint:           rgba(34,29,21,0.44);  /* eyebrow labels, meta, timestamps */
--panel:           rgba(255,252,246,0.66);/* glass panel fill */
--panel-strong:    rgba(255,252,246,0.90);/* message bubbles, raised cards */
--hairline:        rgba(20,16,10,0.09);  /* default 1px border */
--hairline-strong: rgba(20,16,10,0.12);  /* interactive borders, chips */
--logo-filter:     none;

/* NIGHT */
--paper:           #0a0b10;
--deep:            #141622;
--ink:             #f7f6f1;
--muted:           rgba(246,244,239,0.62);
--faint:           rgba(246,244,239,0.42);
--panel:           rgba(17,18,27,0.66);
--panel-strong:    rgba(20,21,31,0.92);
--hairline:        rgba(255,255,255,0.09);
--hairline-strong: rgba(255,255,255,0.16);
--logo-filter:     invert(0.92) hue-rotate(180deg);
```

**Rules**
- No component may hardcode a neutral hex. Every neutral is one of the nine tokens above.
- Interactive tints are always derived, never new colours: `color-mix(in oklab, var(--ink) 6%, transparent)` for hover, `color-mix(in oklab, var(--e1) 14%, transparent)` for selected.
- `--deep` sections keep their own light-on-dark text at `rgba(247,243,236, .45–1)`; they do **not** invert in night mode (they get slightly cooler via the token).

### 1.3 Type

| Role | Family | Size / weight / tracking |
|---|---|---|
| Display (hero, section H2) | **Instrument Sans** | `clamp(36px, 5vw, 148px)` · 550 · `-.04em` · lh .98–1.02 |
| Emotional voice (pull quotes, phase labels, screen titles, card titles) | **Newsreader** | 15–52px · 300–400 · often italic · lh 1.2–1.45 |
| UI + body | **Instrument Sans** | 12–17px · 400/500/600 · lh 1.55–1.7 |
| Eyebrow / meta / numeric | **Geist Mono** | 8.5–11.5px · 400/500 · `.12–.14em` · UPPERCASE |

**Rules**
- Newsreader is reserved for moments with feeling in them. Never use it for buttons, labels, or data.
- Geist Mono is for machine truth: confidences, timers, model ids, timestamps, step numbers. Never for prose.
- Body copy gets `text-wrap: pretty`; display headings get `text-wrap: balance`.
- Minimum readable size in the app is 10.5px and only for mono meta; body never below 12.5px.
- Slide/marketing display type is set with negative tracking; small mono is set with wide positive tracking. This contrast *is* the type system.

### 1.4 Radii, borders, elevation

```
radius: 9–11px  small controls (icon buttons, nav rows, session rows)
        13–18px inline cards, inputs, list rows
        20–24px composer, intervention players, section cards
        22px    shell panels (sidebar, conversation, inspector)
        44px    inverted section corners (marketing)
        99px    pills, chips, transport buttons
```

- Borders are always `1px solid var(--hairline)` — `1.5px` only to mark a selected state.
- **No neutral drop shadows on flat UI.** Elevation is either glass (`backdrop-filter: blur(20–24px) saturate(1.2)`) or an *emotion-coloured* glow: `0 18px 40px -16px var(--e1)`.
- Message bubbles get one soft warm shadow only: `0 10px 26px -18px rgba(36,26,14,.35)`.

### 1.5 Spacing & layout

8px base scale. Shell gutter 12px; panel padding 14–24px; conversation column `max-width: 720px` centred; section padding `110–140px` vertical on marketing, 24px horizontal minimum.

---

## 2. The emotion field

This is the defining system of the product. **The interface is lit by what the user feels.**

### 2.1 Palette — 12 states

Each state carries three colours. `--e1` is the primary field colour, `--e2` the secondary (gradients, highlights), `--e3` a deep ground used only in inverted sections.

| id | Display name | `--e1` | `--e2` | `--e3` | Temperament |
|---|---|---|---|---|---|
| `calm` | Calm | `#3fd0c9` | `#4a86ff` | `#0d2233` | slow drift |
| `hopeful` | Hopeful | `#52d6bb` | `#ffb45c` | `#123330` | lifting |
| `joyful` | Joyful | `#ffc75c` | `#ff8a5c` | `#3a1f1a` | bright pulse |
| `tender` | Tender | `#ff9bb8` | `#ffc27a` | `#2e1524` | warm bloom |
| `balanced` | Balanced | `#8f86ff` | `#65d7dd` | `#1b1a3a` | even |
| `anxious` | Anxious | `#a693ff` | `#69bed7` | `#241f4d` | quick tremor |
| `low` | Low | `#7f7fd6` | `#cf7089` | `#171a3a` | heavy sink |
| `grief` | Grieving | `#6b74b8` | `#9a6fa8` | `#12142e` | still |
| `angry` | Angry | `#ff6941` | `#ffb15f` | `#33130e` | ember flare |
| `envious` | Envious | `#9fd85e` | `#3fbfa0` | `#152a1c` | sharp edge |
| `ashamed` | Ashamed | `#f28ba8` | `#b07ad6` | `#2a1428` | shrink |
| `flat` | Flat | `#8d9bb0` | `#6f7d94` | `#171b22` | low hum |

A 13th pseudo-state `warm` (`#ff7a4d` / `#ffb45c` / `#2b1410`) is the **resting** field for the marketing hero and any pre-classification state. It is never a classifier output.

### 2.2 Mapping classifier output to a state

The backend returns GoEmotions' 28 classes plus a mental-health signal. `lib/emotion.ts` folds 28 → 12 (keep the existing folding table; only the palette changes). Contract:

```ts
type EmotionState = { id: EmotionId; c1: string; c2: string; c3: string;
                      subs: string[]; temperament: string };
```

- `subs` are the raw sub-labels shown as outline chips beside the read (e.g. anxious → `nervous`, `dread`, `overwhelmed`).
- If confidence `< 0.45`, fall back to `balanced` and render the read chip at reduced emphasis. Never show a state the model isn't reasonably sure of.
- **Crisis overrides the field to `balanced`.** A crisis turn must not paint the room red or purple; it steadies it. Enforced in the mockup by `showCrisis ? EMOTIONS.balanced : active`.

### 2.3 How the field is applied

`--e1/--e2/--e3` are set on a single wrapper element that also owns `background: var(--paper)` and `color: var(--ink)`, so both the field and the grade inherit down. Everything downstream references the vars — **no component receives an emotion colour as a prop.**

Five application patterns, and only these five:

1. **Ambient field** — 2–3 absolutely positioned circles, `38–52vw`, `radial-gradient(circle, color-mix(in oklab, var(--e1) 30–38%, transparent), transparent 70%)`, `filter: blur(70–90px)`, drifting on 14–24s ease-in-out loops. Behind everything, `pointer-events: none`.
2. **Accent** — small marks: read-chip dots, trail bullets, step numbers, active-row tint, link hover.
3. **Glow** — `box-shadow: 0 Npx Mpx -Xpx var(--e1)` on the send button, Nimbus, players, the CTA.
4. **Focus ring** — composer carries `box-shadow: 0 0 0 4px color-mix(in oklab, var(--e1) 14%, transparent)`.
5. **Full-bleed player ground** — see §7.1; must mix toward `#120e0a`, never toward white.

Plus a grain overlay: inline SVG `feTurbulence`, `baseFrequency 0.8`, opacity `.045–.05`, `mix-blend-mode: multiply` (day) — this is what stops the gradients reading as "AI gradient slop."

### 2.4 Transition law

```
--e1/--e2/--e3 : 1600ms cubic-bezier(.22,.61,.36,1)
neutral tokens : 700ms ease
```

**Emotion colour never snaps.** 1.6s is deliberately slow enough to be felt as a mood shift rather than seen as a state change. Anything that reads as an instant recolour is a bug. `@property` registration is required for these to interpolate.

`prefers-reduced-motion: reduce` disables all `animation` but **keeps colour transitions** — the emotional signal survives; only the drifting stops.

---

## 3. Day / night grading

- One control, present on all three surfaces: a 34px circular icon button, moon glyph in day, sun glyph in night. Placement: marketing nav (left of the CTA), chat header (left of the inspector toggle), mobile header (left of Nimbus).
- Persisted to `localStorage` under **`ml-grade`** (`"day" | "night"`), read on mount, shared across all routes.
- Swaps the nine neutral tokens in §1.2 over 700ms. **The emotion palette does not change between grades** — the field is who the user is; the grade is the room's lighting.
- The logo is a single dark-ink PNG; night mode applies `filter: var(--logo-filter)`.
- Respect `prefers-color-scheme` for the first visit only; an explicit choice always wins afterwards.

---

## 4. Iconography & logo

- **Logo:** `mindlens-logo.png` — the hand-drawn lens/eye mark, warm-charcoal ink on transparent. Nav 22px tall, footer 20px, mobile caption 26px. Never recolour it; only invert via `--logo-filter`. Always paired with the wordmark at 15px/600/`-.02em` in app chrome.
- **Icons:** 1.7–1.8px stroke, `stroke-linecap: round`, `currentColor`, 13–15px in UI, 20px in feature cards. Lucide-compatible geometry. Never fill except for transport glyphs (play/pause/skip), which are solid.
- **No emoji anywhere in the UI.** Emotion is communicated by colour, Nimbus, and words. (Emoji may appear in *user-typed message content* — that's their voice, not ours.)
- Assigned icons: Chat = message-circle · Progress = trending-up · Journal = pencil · Memory = database · Settings = sliders · Inspector = panel-right · Attach = plus · Voice = mic · Copy = copy · Regenerate = rotate-ccw · Read aloud = volume · Scroll = chevron-down · Privacy = lock.

---

## 5. Chat shell (desktop)

Three columns in a 12px-gutter flex row, each a 22px-radius glass panel (`--panel` + `blur(24px) saturate(1.2)` + `1px var(--hairline)`), on the ambient field. Full viewport height, `overflow: hidden` on the shell; only the message list and inspector scroll.

```
┌──────────┬────────────────────────────────┬─────────────┐
│ Sidebar  │ Header                         │ Music panel │
│ 262px    ├────────────────────────────────┤ 336px       │
│          │ Message list (scroll)          │  companion  │
│  logo    │   max-width 760px, centred     │  track card │
│  new     │   trail · reply · options      │  privacy    │
│  nav     ├────────────────────────────────┤             │
│  history │ ▼ scroll-to-bottom (42px band) │  (mounted   │
│  privacy ├────────────────────────────────┤   only when │
│  legal   │ composer                       │   a track   │
└──────────┴────────────────────────────────┴─  exists)  ─┘
```

**The right column is a music panel, not a permanent inspector.** It is
mounted only when the turn produced a track, and its header toggle is
rendered only alongside one — a toggle for an empty panel is a control that
does nothing. What it used to hold is gone or moved:

- **The field grid is deleted.** §5.3 already described it as a demo
  affordance rather than a mood logger, and open item #4 required it be gated
  or converted before production. Tapping it repainted the room but changed
  nothing the model believed.
- **Today's weather moved to Progress**, which already fetches the same mood
  logs for its 7-day chart.
- **What we worked on is deleted.** It mapped agents through a 13-entry label
  table that silently dropped any agent missing from it and listed six —
  cbt, dbt, act, mi, narrative, planning — that are not agents and never run.
  The reasoning trail reports the real per-turn list instead.

**Breakpoints**: music panel hides `≤980px`; sidebar hides `≤780px`. Both are
progressive disclosure, not content loss — the sidebar behind a drawer, the
panel's content still reachable in the turn that produced it.

### 5.1 Sidebar (250px)

Logo + wordmark → **New conversation** button (13px/500, gradient `color-mix` of `--e1`/`--e2` at 22%/14%, emotion-tinted border, `⌘K` hint in mono at 50% opacity) → nav rows (icon 15px + label, active row = `--panel-strong` + hairline + weight 500) → scrollable session history grouped by mono eyebrow (`TODAY`, `PREVIOUS 7 DAYS`), rows truncate with ellipsis, active row tinted `color-mix(--e1 10%)` → pinned privacy note with lock icon at 10.5px `--faint`.

Session titles are model-generated short phrases in the user's own register ("Two weeks to the viva", "3am thoughts again") — never "Conversation 4".

### 5.2 Header

Mono eyebrow `THE ROOM IS LISTENING` (`--faint`, nowrap) over the session title in Newsreader 23px/300, truncating. Right side: connection pill (mono 10px, 7px green dot, `#52d6bb` when live), day/night toggle, inspector toggle. Title block needs `min-width: 150px` so it never collapses.

### 5.3 Music panel (336px)

1. **Companion hero** — 92px stage in an 18px-radius card with a
   `color-mix(--e1 13%)` gradient wash. Caption in Newsreader 15.5px:
   *"{name} is holding {state} with you"*, state italic in
   `color-mix(in oklab, var(--e1) 75%, var(--ink))`.
2. **The track** — the music card (§7.2), with real `<audio>` playback of the
   30-second preview. Rendered here and *only* here; it used to also appear
   inline in the turn, which showed the same card twice.
3. Privacy note, pinned bottom.

---

## 6. Message anatomy

### 6.1 User turn

Right-aligned, `max-width: 540px`, `padding: 13px 17px`, `border-radius: 18px 18px 5px 18px`, `--panel-strong` + hairline, 14.5px/1.6, one soft warm shadow. Below it, right-aligned, the **emotion read strip**:

- **Primary chip** — pill, `1px solid color-mix(--e1 50%)`, `background color-mix(--e1 13%)`; contains a 10px organic blob (`border-radius: 38% 62% 55% 45%/45% 40% 60% 55%`) filled `linear-gradient(140deg, c1, c2)`, the state name at 11.5px/500, and the confidence in mono 9.5px `--faint`.
- **Sub chips** — outline pills, 10.5px `--muted`, max 3.
- **Blend chip** — dashed border, `✦ Anticipation`, when surface and core emotions differ meaningfully (e.g. anxious + hopeful). This is the "surface vs core" idea made visible.

**Copy law:** the read is phrased as weather, never as diagnosis. "Anxious 0.87" is acceptable because the number is visibly a confidence; "Anxiety: moderate" is not.

### 6.2 Assistant turn

30px Nimbus avatar (§8) in a left gutter, then a 14px-gap column:

1. **Reasoning trail** — collapsible, triggered by a mono `HOW I GOT HERE` row with a 6px emotion dot and a `show`/`hide` affordance. Open state is an `<ol>` with a vertical gradient rail (`linear-gradient(to bottom, color-mix(--e1 55%), transparent)`) and 7px bullets. Each step: mono 9.5px uppercase label + 12.5px/1.55 `--muted` sentence.

   Canonical step labels, in order: **SAFETY GATE → EMOTION READ → MEMORY → APPROACH**. Steps are written in first person, plainly, as one sentence each — the same register as Claude's thinking summaries. They must be honest reflections of what the pipeline did (including the routed model), never theatre.

2. **Response body** — 14.5px/1.68, `text-wrap: pretty`. Voice: a wise coaching friend. 4–5 sentences. Validate → one root-cause question or reframe → close with a choice of next step. Never clinical, never a bulleted plan unless asked.

3. **Message actions** — three 28px ghost icon buttons (copy, regenerate, read aloud), `--faint`, hover tints to `--muted` on a 6% ink wash.

4. **Intervention players** (§7) when the turn offers one, in an `auto-fit minmax(258px, 1fr)` grid.

### 6.3 Streaming turn

Same anatomy, plus: an 11px spinner ring in `--e1` beside a shimmering `WORKING IT THROUGH` label (background-clip text sweep, 2.2s linear), trail steps appearing progressively with glowing bullets, and a 2px caret block on the last partial line blinking at 1s step-end. Agent activity from the WebSocket maps 1:1 onto trail steps — a step appears the moment its stage reports, not after.

### 6.4 Crisis state

When the safety gate fires, the conversation surface changes shape:

- Field forced to `balanced` (§2.2). No red room.
- A 20px-radius card, `1.5px solid rgba(255,105,65,.55)`, `--panel-strong`, warm shadow `0 20px 50px -24px rgba(255,105,65,.5)`.
- Mono eyebrow `LET'S PAUSE HERE` in `#d14a24`; Newsreader 19px line: *"This sounds heavy enough that a human should be with you right now. That's not a failure — it's the next right step."*
- Resource rows — 13px, region name left, number right in mono. **Real human resources appear above everything else.** Mockup uses Sri Lanka placeholders (Sumithrayo `011 269 6666`, National line `1926`, emergency `119 / 110`); production must resolve by locale and be verified.
- Footer note at 11.5px: *"This message was written by people, not generated. Mindlens makes no model calls during a crisis."*
- No intervention players, no reasoning trail, no message actions in a crisis turn.

### 6.5 Composer

24px-radius, `--panel-strong`, `blur(18px)`, hairline, plus the emotion focus ring and glow (§2.3). Auto-growing textarea, 14.5px, placeholder *"Say it however it comes out…"*. Toolbar row: attach + mic ghost buttons (30px), `Adaptive` chip (model-routing indicator), `Voice · soon` chip at `--faint`, mono `⏎ TO SEND` hint pushed right, then a 38px circular gradient send button (`linear-gradient(135deg, --e1, --e2)`, hover `scale(1.06)`).

**Two controls were removed rather than left disabled.** The paperclip is
gone: there is no upload endpoint and every agent is text-only, so an
attached file had nowhere to go. The mic now genuinely dictates via the
browser's Web Speech API — which ships audio to the browser vendor, so it
says so once before first use and is not rendered at all where the API is
missing.

**The starter suggestion chips are gone.** They were four canned openers
above an empty conversation, and there is no per-turn suggestion output to
replace them with. Structured follow-up options (§6.6) serve the real need.

**The disclaimer moved to the sidebar.** It is chrome, not something the
companion says, and it was also being appended into the reply text itself —
landing mid-sentence after the follow-up question on every turn. §4.1 still
holds: it is always on screen, never behind a disclosure. Below 780px, where
the sidebar is a drawer, the composer keeps a copy.

### 6.6 Structured options

When a reply ends on a question the turn may carry two to four short answers,
rendered as numbered rows beneath it, with the line *"Or say it your own way
below — these are just shortcuts."*

This is **not** the canned menu that was removed from the empathy prompt.
That was one fixed sentence recited verbatim every turn. These are generated
per turn from what was actually said, schema-validated rather than parsed out
of prose, and offered only when something was genuinely asked. Validation
fails closed — wrong shape, a duplicate, anything over 48 characters, fewer
than two or more than four, and no options are shown at all. Only the newest
turn renders them.

**Scroll-to-bottom:** a 34px glass circle in its own reserved 42px band *below* the scroll container, rendered only when `scrollHeight - scrollTop - clientHeight ≥ 24`. It must never overlay message text.

---

## 7. Intervention players

Both are inline in the message flow, `auto-fit minmax(258px, 1fr)`, 22px radius, 16px padding. They read as *players*, not as buttons — transport controls, progress, and live readouts.

### 7.1 Breathe (4·7·8)

Full-bleed emotion ground: `linear-gradient(158deg, color-mix(in oklab, var(--e1) 52%, #120e0a), color-mix(in oklab, var(--e2) 40%, #120e0a))`.

> **Contrast law:** the ground must mix toward `#120e0a`, never toward white. Mixing toward white produces a light card under the near-white text for 8 of the 12 palettes (joyful, envious, hopeful, tender…). All text on this card is `rgba(255,253,248, .82–1)`; the bloom highlight is `--e2`-tinted, not white.

Anatomy top → bottom: glass chip `STRESS RELIEF` + live elapsed timer in mono · a 26-bar line visualizer, 46px tall, each bar animating `scaleY(.45 → 1)` on staggered 2.4–4.0s loops, `animation-play-state` bound to running/paused · phase label in Newsreader 23px/300 (`Breathe in` / `Hold` / `Breathe out`) · countdown strip in mono 14px `.18em` (`4 · 3 · 2 · 1`, capped at 5 with `…`) · Volume and Pace slider rows (52px mono label, 3px track, 9px white thumb, mono value) · transport cluster: 32px slower, 48px white play/pause with dark glyph, 32px faster · cycle note (`2 rounds done`).

Timing is authoritative: **inhale 4s, hold 7s, exhale 8s**, driven by a 1s interval, cycle counter increments on return to phase 0. The circle/ring variant scales to `1` on inhale/hold and `0.62` on exhale over the phase duration.

### 7.2 Music

`--panel-strong` card, hairline. 70px album tile with the emotion gradient and a soft bloom · plain music-note glyph in `--e1` (no third-party branding — tracks come from iTunes search, not a connected account) + mono `BECAUSE YOU'RE {STATE}` · title in Newsreader 21px/300 · 42-bar waveform (decorative), played bars `--e1`, remaining `color-mix(in oklab, var(--ink) 16%, transparent)` · transport: 44px gradient play/pause, real playback of the track's 30s preview when one exists, "Open on Apple Music" when it doesn't, an honest "No preview available" when neither does.

Playlists are chosen by emotion state, and the reason is stated. Never "Recommended for you".

---

## 8. Nimbus

Nimbus is MindLens's companion presence. Not a mascot, not an avatar, not a logo — **a soft presence that wears the feeling.**

### 8.1 Construction

- A morphing blob: `animation: nimbusMorph 9s ease-in-out infinite` cycling three organic `border-radius` sets (`48% 52% 55% 45%/52% 48% 52% 48%` → `55% 45% 48% 52%/45% 55% 45% 55%` → `45% 55% 52% 48%/55% 45% 55% 45%`). **Never a plain circle.**
- Fill `radial-gradient(circle at 34% 26%, color-mix(in oklab, var(--e2) 82%, white), var(--e1) 74%)`, an emotion glow, and an inset bottom shade for volume.
- Float: `nimbusFloat` ±5px over 5s (3s while streaming — he's working).
- Hero only (112px stage): a pulsing halo ring (`halo` 4.5s, scale 1→1.14, opacity .5→.18) and two sparkles (`sparkle` 3.2s / 3.8s offset).

### 8.2 Face

Two 9px eyes with a `blink` keyframe (`scaleY(1) → 0.1` at 96% of a 6s loop, right eye offset 0.12s), a mouth built from a single bordered box (bottom border only = smile, top border only = frown, `border-radius: 0` + 2px height = flat line), and two blurred white blush highlights. All transitions on the face run 600ms.

The face is **driven by the emotion state**, per this table (`top`/`height`/`width` values as in the mockup's `EXPRESSIONS` map):

| State | Eyes | Mouth |
|---|---|---|
| calm | narrow (3px), low lids | gentle smile |
| hopeful | open (9px) | clear smile |
| joyful | squinting crescents (4px) | wide smile (26px) |
| tender | soft crescents | small smile |
| balanced | neutral (8px) | small smile |
| anxious | **wide (12px)**, raised | small tight mouth (11px) |
| low | half-lidded (6px), lowered | frown |
| grief | almost closed (3px), lowest | small frown |
| angry | narrowed (7px) | frown |
| envious | narrowed (6px) | small frown |
| ashamed | nearly shut, lowest | small frown, turned away |
| flat | thin lines (3px) | **flat line** (2px, no radius) |

**Rules:** Nimbus never speaks, never gestures, never has limbs, and never appears in the crisis card. At 30px (chat avatars) he keeps only morph + blinking eyes — no mouth, no sparkles. He is a presence in the room, not a character in the conversation.

### 8.3 Alternative directions (not implemented)

Documented for future exploration: (a) a small cloud with real weather — drizzle at `low`, sunbeams at `hopeful`; (b) a lens/aperture whose iris dilates with intensity. Either would be introduced as a switchable variant, never a replacement mid-session.

---

## 9. Marketing site

Audience: end users 16–30. Goal: publication. Not an academic poster.

Sections in order:

1. **Hero** — full viewport, ambient field on the `warm` resting palette + grain. Mono corner labels (`/// MINDLENS`, `PERSONAL WELLBEING COMPANION`). Headline `clamp(58px, 9.5vw, 148px)`/550/`-.045em`: *"See what ● you feel."* with an inline organic gradient chip pulsing on a 5s loop. Sub 17px/1.65, `max-width 560px`. Dual CTA (dark pill + glass pill). Mono trust line: `FREE · PRIVATE · NOT A REPLACEMENT FOR PROFESSIONAL CARE`. Bottom: an infinite marquee of the 12 state names with their gradient dots, edge-masked, 36s linear.
2. **Portrait band** — 30px-radius full-width image with an emotion-shadow, mono caption `THE ROOM IS LISTENING`. Needs a real warm portrait (currently a drop-zone).
3. **Philosophy** — centred Newsreader italic `clamp(30px, 4.4vw, 52px)`/300 pull quote (the "therapy gave me the tools" line), with the emotive phrase in `--e1`.
4. **How it works** — 5 cards, `auto-fit minmax(210px, 1fr)`: the gate, the read, the recall, the response, the record. Mono step numbers in `--e1`, Newsreader 22px titles, 13px `--muted` bodies. This is the SYSTEM.md pipeline in plain language.
5. **Models** — `--deep` band, `44px 44px 0 0` radius. Five cards for `mindlens-emotion`, `mindlens-mh`, `mindlens-crisis`, `mindlens-reranker`, `mindlens-distortion`: gradient dot, mono model id in `--e2`, 16.5px title, 12.5px body. Footnote on Groq routing (a fast model for simple turns, a larger one for emotional turns — see SYSTEM.md §9 for the current pair) and **zero LLM calls in crisis**.
6. **Emotion lab** — continues the `--deep` band, closes `0 0 44px 44px`. Left: 4×3 grid of 74px state tiles with visible names. Right: a large gradient preview card showing the active state name in Newsreader 46px, its sub-labels as outline chips, and its temperament in mono. Tapping a tile recolours **the entire page** over 1.6s. This section is the product thesis, demonstrated.
7. **Docs** — 3 cards linking `SYSTEM.md`, `API.md`, `DEPLOYMENT.md`, mono filename in `--e1`, hover border tints to the field colour.
8. **Safety & privacy** — two columns: a headline + framing paragraph + an amber-bordered emergency callout; and 5 numbered non-negotiables (template-only crisis answers, gate-first ordering, scoped queries + httpOnly JWT, visible memory, never a diagnosis).
9. **Footer** — logo, disclaimer paragraph, Product / Open-source link columns, and a mono credit line.

**Motion:** GSAP + ScrollTrigger. Every `[data-reveal]` block fades up 30px over 1s `power3.out` at `top 88%`. Hero copy children stagger 0.12s. Ambient blobs get a light `yPercent` parallax scrub. Nothing else animates on scroll — no counters, no pinned scenes, no horizontal hijack.

---

## 10. Mobile chat

390×844 reference. Same anatomy, condensed: 36px header row (menu / centred eyebrow + title / grade toggle + Nimbus), reasoning trail collapsed into a `<details>` with a 3-line summary, one intervention card at a time (52px control, no sliders), bubbles at `max-width: 82%` / 13.5px, and a horizontally scrolling row of **quick-feel chips** (colour dot + word, selected chip tinted with the field) above the composer. All hit targets ≥44px. No inspector; its content moves to a bottom sheet.

---

## 11. Accessibility & guardrails

- Body text ≥ 4.5:1 in both grades; mono meta ≥ 3:1 and never load-bearing on its own.
- **Colour is never the only signal.** Every emotion colour is accompanied by its name in text. A colourblind or screen-reader user loses nothing.
- All 12 state swatches carry `title` + `aria-label`; all icon-only buttons carry `aria-label`.
- Emotion state is announced via a polite live region when it changes, not just recoloured.
- `prefers-reduced-motion: reduce` → all `animation: none`; colour transitions retained.
- Focus visible on every interactive element; the composer's emotion ring is decorative and must not replace a focus outline.
- Full keyboard path: `⌘K` new conversation, `⏎` send, `⇧⏎` newline, arrow keys through the session list, `Esc` closes inspector/sheet.

## 12. Anti-patterns

Do not: introduce a brand colour outside the emotion field · use emoji as UI · put the emotion palette on a chart or dial · snap emotion colours · mix a player ground toward white · give Nimbus a mouth at 30px or a voice at any size · show a crisis turn with a reasoning trail, players, or a hot field · use Newsreader for controls or Geist Mono for prose · add gradient text · label a user with a condition · style anything as a clinical dashboard · let the scroll-to-bottom button overlay content · hardcode a neutral hex.

---

## 13. Open items

1. Hero portrait is an unfilled drop-zone — needs a real licensed image.
2. Crisis helpline numbers are unverified placeholders; resolve by locale before any public deploy.
3. Docs cards link to a GitHub profile, not the repo files.
4. ~~Inspector's field grid must be gated or converted~~ — **done**: the grid
   is deleted and the rail is a music panel (§5.3).
5. Mobile bottom sheet for the music panel is unspecified; below 980px the
   track is simply not shown.
6. `frontend/src/app/tokens.css` still holds the superseded dark-glass palette — migrate and delete.
