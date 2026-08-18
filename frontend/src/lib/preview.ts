/**
 * Dev-only preview mode.
 *
 * The chat screen only exists behind a successful login, and login needs a
 * backend. When the backend isn't reachable — which is most of the time while
 * the design is being built — this lets the UI render against a fixture so
 * the layout can be worked on.
 *
 * Gated on NEXT_PUBLIC_PREVIEW_AUTH, which lives in .env.local (gitignored).
 * It is off unless someone deliberately turns it on, the screen carries a
 * visible PREVIEW badge whenever it's active, and nothing here is reachable
 * from a normal build. This replaces the temporary hard-coded bypass that was
 * sitting in use-mindlens-client.ts.
 */

import type { ChatMessage, SessionListItem, UserProfile } from "./types";

export const PREVIEW_MODE = process.env.NEXT_PUBLIC_PREVIEW_AUTH === "1";

export const PREVIEW_USER: UserProfile = {
  id: "preview",
  email: "preview@mindlens.app",
  name: "Amiru",
  nickname: "Amiru",
  age: 22,
  age_group: "adult",
  role: "user",
  onboarding_complete: true,
  created_at: new Date().toISOString(),
};

/**
 * A short fixture exchange so every piece of message chrome — the emotion
 * read strip, the reasoning trail, the actions row — is visible while
 * styling. Deliberately mundane content; it is a layout fixture, not a
 * sample of what Mindlens should sound like.
 */
export const PREVIEW_MESSAGES: ChatMessage[] = [
  {
    id: "preview-1",
    role: "user",
    text: "I keep telling myself I'll start the dissertation tomorrow and then tomorrow turns up and I do nothing. It's been three weeks of this.",
    eos: {
      surface_emotion: "nervousness",
      surface_confidence: 0.82,
      core_emotion: "embarrassment",
      distress_level: 0.61,
      mental_fatigue: 0.55,
      modality: "ACT",
      trust_level: 0.42,
    },
  },
  {
    id: "preview-2",
    role: "assistant",
    text: "Three weeks of planning to start and not starting is exhausting in a way that doing the work never is, Amiru. Something about opening that document is costing you more than the writing itself would — and I'd rather understand that than hand you a schedule. When tomorrow arrives and you don't begin, what's the first thing that goes through your head? We could look at what's underneath it, or if you'd rather move than talk, we could just get the first paragraph out badly on purpose.",
    eos: {
      surface_emotion: "nervousness",
      surface_confidence: 0.82,
      core_emotion: "embarrassment",
      distress_level: 0.61,
      mental_fatigue: 0.55,
      modality: "ACT",
      trust_level: 0.42,
    },
    agentsUsed: ["empathy", "act", "planning"],
    memoryRecalled: [],
    degraded: [],
  },
];

export const PREVIEW_SESSIONS: SessionListItem[] = [
  {
    session_id: "preview-session",
    title: "Starting the dissertation",
    started_at: new Date().toISOString(),
    ended_at: null,
    status: "active",
    turn_count: 2,
    primary_modality: "ACT",
    pinned: false,
  },
  {
    session_id: "preview-session-2",
    title: "The argument with Dad",
    started_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
    ended_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
    status: "ended",
    turn_count: 11,
    primary_modality: "Narrative",
    pinned: false,
  },
];
