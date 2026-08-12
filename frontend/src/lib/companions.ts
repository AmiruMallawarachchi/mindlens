/**
 * The companion cast — design project "Mindlens: Emotional AI Companion",
 * file "Companion Expressions": "The five companions — LOCKED. No new
 * characters. No renames. [...] Eyes only." Ember is the default; the other
 * four are alternate companions a user can pick in Your Mindlens, then
 * rename to whatever they like.
 *
 * Every companion's colour is bound to --e1/--e2/--e3 from the active
 * emotion. The personality words aren't decorative — the same doc: "they
 * feed the system prompt to set voice and pacing, and they set each
 * character's spring config" (spring config below, system-prompt wiring not
 * yet built).
 */

export type CompanionId = "ember" | "lens" | "flit" | "tide" | "fern";

/** The six states a companion's `<CompanionAvatar activity>` can render.
 * "idle" and "listening" run longest, so they carry the most animation
 * budget; "asking"/"sending"/"celebrating" are brief, event-driven poses. */
export type CompanionActivity =
  | "idle"
  | "listening"
  | "sending"
  | "thinking"
  | "asking"
  | "celebrating";

/** stiffness/damping/mass for the state-pose spring — Flit twitchy, Tide
 * liquid, Ember combustive, Fern slow and woody, Lens smooth and inertial. */
export interface SpringFeel {
  stiffness: number;
  damping: number;
  mass: number;
}

export interface CompanionDef {
  id: CompanionId;
  name: string;
  tagline: string;
  words: string;
  spring: SpringFeel;
}

export const COMPANIONS: CompanionDef[] = [
  {
    id: "ember",
    name: "Ember",
    tagline: "Warm, unafraid of heat. Burns alongside you, then settles.",
    words: "energetic · chill · passion",
    spring: { stiffness: 210, damping: 18, mass: 1 },
  },
  {
    id: "lens",
    name: "The Lens",
    tagline: "Faceless — no eyes. A mirror, not a friend. Adult, precise.",
    words: "clarity · perspective · restraint",
    spring: { stiffness: 90, damping: 26, mass: 1.6 },
  },
  {
    id: "flit",
    name: "Flit",
    tagline: "A firefly. Quick, bright, always one more question.",
    words: "freedom · expression · curiosity",
    spring: { stiffness: 460, damping: 12, mass: 0.5 },
  },
  {
    id: "tide",
    name: "Tide",
    tagline: "Level rises as you build, drains as you breathe.",
    words: "honesty · release · rhythm",
    spring: { stiffness: 120, damping: 14, mass: 1.3 },
  },
  {
    id: "fern",
    name: "Fern",
    tagline: "Thinks in seasons. A bad week doesn't undo it.",
    words: "patience · growth · resilience",
    spring: { stiffness: 70, damping: 24, mass: 1.4 },
  },
];

export const DEFAULT_COMPANION_ID: CompanionId = "ember";

export function getCompanion(id: string | null | undefined): CompanionDef {
  return COMPANIONS.find((c) => c.id === id) ?? COMPANIONS[0];
}
