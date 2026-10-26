export type EmotionId =
  | "calm"
  | "hopeful"
  | "joyful"
  | "tender"
  | "balanced"
  | "anxious"
  | "low"
  | "grief"
  | "angry"
  | "envious"
  | "ashamed"
  | "flat";

/** Drives field motion: maps to ShaderGradient uSpeed/uStrength and to the
 * companion's spring amplitude. */
export type Temperament =
  | "slow drift"
  | "lifting"
  | "bright pulse"
  | "warm bloom"
  | "even"
  | "quick tremor"
  | "heavy sink"
  | "still"
  | "ember flare"
  | "sharp edge"
  | "shrink"
  | "low hum";

export interface EmotionState {
  id: EmotionId;
  /** Plain-language name. Always shown next to any score â€” Â§8: the emotion
   * read is informational, never a diagnosis label, never a bare number. */
  name: string;
  c1: string;
  c2: string;
  c3: string;
  subs: readonly [string, string, string] | readonly [string, string];
  temperament: Temperament;
  /** "hard" states let distress drive intensity; "soft" states use confidence. */
  valence: "soft" | "hard";
}

export const EMOTION_STATES: Record<EmotionId, EmotionState> = {
  calm: {
    id: "calm",
    name: "Calm",
    c1: "#3fd0c9",
    c2: "#4a86ff",
    c3: "#0d2233",
    subs: ["settled", "relieved", "content"],
    temperament: "slow drift",
    valence: "soft",
  },
  hopeful: {
    id: "hopeful",
    name: "Hopeful",
    c1: "#52d6bb",
    c2: "#ffb45c",
    c3: "#123330",
    subs: ["optimistic", "curious", "motivated"],
    temperament: "lifting",
    valence: "soft",
  },
  joyful: {
    id: "joyful",
    name: "Joyful",
    c1: "#ffc75c",
    c2: "#ff8a5c",
    c3: "#3a1f1a",
    subs: ["amused", "excited", "proud"],
    temperament: "bright pulse",
    valence: "soft",
  },
  tender: {
    id: "tender",
    name: "Tender",
    c1: "#ff9bb8",
    c2: "#ffc27a",
    c3: "#2e1524",
    subs: ["loved", "grateful", "caring"],
    temperament: "warm bloom",
    valence: "soft",
  },
  balanced: {
    id: "balanced",
    name: "Balanced",
    c1: "#8f86ff",
    c2: "#65d7dd",
    c3: "#1b1a3a",
    subs: ["clear", "focused", "steady"],
    temperament: "even",
    valence: "soft",
  },
  anxious: {
    id: "anxious",
    name: "Anxious",
    c1: "#a693ff",
    c2: "#69bed7",
    c3: "#241f4d",
    subs: ["nervous", "dread", "overwhelmed"],
    temperament: "quick tremor",
    valence: "hard",
  },
  low: {
    id: "low",
    name: "Low",
    c1: "#7f7fd6",
    c2: "#cf7089",
    c3: "#171a3a",
    subs: ["sad", "lonely", "disappointed"],
    temperament: "heavy sink",
    valence: "hard",
  },
  grief: {
    id: "grief",
    name: "Grieving",
    c1: "#6b74b8",
    c2: "#9a6fa8",
    c3: "#12142e",
    subs: ["loss", "numb", "aching"],
    temperament: "still",
    valence: "hard",
  },
  angry: {
    id: "angry",
    name: "Angry",
    c1: "#ff6941",
    c2: "#ffb15f",
    c3: "#33130e",
    subs: ["frustrated", "resentful", "fed up"],
    temperament: "ember flare",
    valence: "hard",
  },
  envious: {
    id: "envious",
    name: "Envious",
    c1: "#9fd85e",
    c2: "#3fbfa0",
    c3: "#152a1c",
    subs: ["comparing", "left behind"],
    temperament: "sharp edge",
    valence: "hard",
  },
  ashamed: {
    id: "ashamed",
    name: "Ashamed",
    c1: "#f28ba8",
    c2: "#b07ad6",
    c3: "#2a1428",
    subs: ["embarrassed", "exposed", "small"],
    temperament: "shrink",
    valence: "hard",
  },
  flat: {
    id: "flat",
    name: "Flat",
    c1: "#8d9bb0",
    c2: "#6f7d94",
    c3: "#171b22",
    subs: ["bored", "numb", "ennui"],
    temperament: "low hum",
    valence: "hard",
  },
};

export const EMOTION_ORDER: readonly EmotionId[] = [
  "calm",
  "hopeful",
  "joyful",
  "tender",
  "balanced",
  "anxious",
  "low",
  "grief",
  "angry",
  "envious",
  "ashamed",
  "flat",
];

/**
 * go-emotions' 28 classes folded onto the 12 UI states.
 *
 * Two states are deliberately absent from this table:
 *  - `envious` â€” go-emotions has no envy class, and nothing else in it is a
 *    faithful stand-in. It stays reachable through the inspector's emotion
 *    picker (the user naming their own feeling) rather than being guessed at.
 *  - `flat`    â€” not a classifier output but a *combination*; see
 *    resolveEmotion(), where neutral + high mental fatigue resolves to it.
 */
const SURFACE_TO_STATE: Record<string, EmotionId> = {
  admiration: "tender",
  amusement: "joyful",
  anger: "angry",
  annoyance: "angry",
  approval: "calm",
  caring: "tender",
  confusion: "anxious",
  curiosity: "hopeful",
  desire: "hopeful",
  disappointment: "low",
  disapproval: "angry",
  disgust: "angry",
  embarrassment: "ashamed",
  excitement: "joyful",
  fear: "anxious",
  gratitude: "tender",
  grief: "grief",
  joy: "joyful",
  love: "tender",
  nervousness: "anxious",
  optimism: "hopeful",
  pride: "joyful",
  realization: "balanced",
  relief: "calm",
  remorse: "ashamed",
  sadness: "low",
  surprise: "balanced",
  neutral: "balanced",
};

export function stateForLabel(label: string | undefined | null): EmotionId | null {
  if (!label) return null;
  return SURFACE_TO_STATE[label.toLowerCase().trim()] ?? null;
}

// ---------------------------------------------------------------------------
// Blends â€” two feelings at once
// ---------------------------------------------------------------------------

export interface Blend {
  name: string;
  color: string;
  pair: readonly [EmotionId, EmotionId];
}

const BLENDS: readonly Blend[] = [
  { name: "Anticipation", color: "#7fbfc9", pair: ["anxious", "hopeful"] },
  { name: "Bittersweet", color: "#c78bc4", pair: ["low", "tender"] },
  { name: "Hurt", color: "#c47a95", pair: ["angry", "low"] },
  { name: "Pressure", color: "#d18a89", pair: ["anxious", "angry"] },
  { name: "Comparison spiral", color: "#cbb383", pair: ["envious", "ashamed"] },
  { name: "Quiet relief", color: "#9ccf9a", pair: ["calm", "joyful"] },
];

/** A blend exists only when the surface and core reads genuinely differ and
 * that unordered pair is one the design names. Anything else is a single
 * feeling â€” we don't invent a second one to fill the chip. */
export function findBlend(a: EmotionId | null, b: EmotionId | null): Blend | null {
  if (!a || !b || a === b) return null;
  return (
    BLENDS.find(
      (blend) =>
        (blend.pair[0] === a && blend.pair[1] === b) ||
        (blend.pair[0] === b && blend.pair[1] === a),
    ) ?? null
  );
}

// ---------------------------------------------------------------------------
// Resolving an EOS snapshot into everything the UI needs
// ---------------------------------------------------------------------------


