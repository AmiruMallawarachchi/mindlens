/**
 * The Mindlens emotion system — design.md §2.
 *
 * The backend classifies into go-emotions' 28 classes (see
 * backend/app/core/emotion_labels.py). The UI names 12 states, each carrying
 * three field colours, sub-emotions and a motion temperament. This module is
 * the only place that translation happens.
 *
 * Everything here is derived from real EOS fields. Where the classifier
 * cannot reach a state (see ENVIOUS below), we say so rather than faking it.
 */

import type { EosSnapshot } from "./types";

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
  /** Plain-language name. Always shown next to any score — §8: the emotion
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
 *  - `envious` — go-emotions has no envy class, and nothing else in it is a
 *    faithful stand-in. It stays reachable through the inspector's emotion
 *    picker (the user naming their own feeling) rather than being guessed at.
 *  - `flat`    — not a classifier output but a *combination*; see
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
// Blends — two feelings at once
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
 * feeling — we don't invent a second one to fill the chip. */
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

export interface EmotionReading {
  /** The state driving the field, companion and accents. */
  state: EmotionState;
  /** Present only when the core read differs and forms a named blend. */
  blend: Blend | null;
  /** The core state when it differs from the surface one, blend or not. */
  coreState: EmotionState | null;
  /** 0.1–1.0 — scales field opacity, glow radius, motion amplitude, accent
   * saturation. §2: at 0.2 the room is barely tinted; at 1.0 everything agrees. */
  intensity: number;
  /** Classifier confidence in the surface read, shown beside the name. */
  confidence: number | null;
  /** Sub-emotion chips for the emotion read strip. */
  subs: readonly string[];
  /** True when nothing has been read yet — render the resting state. */
  resting: boolean;
}

export const RESTING_READING: EmotionReading = {
  state: EMOTION_STATES.balanced,
  blend: null,
  coreState: null,
  intensity: 0.28,
  confidence: null,
  subs: EMOTION_STATES.balanced.subs,
  resting: true,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function num(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/**
 * Turn a raw EOS snapshot into the reading the whole UI renders from.
 * Returns the resting reading when there is no snapshot yet, so callers never
 * have to branch on null.
 */
export function resolveEmotion(eos: EosSnapshot | null | undefined): EmotionReading {
  if (!eos) return RESTING_READING;

  const distress = clamp(num(eos.distress_level, 0.5), 0, 1);
  const confidence = clamp(num(eos.surface_confidence, 0.8), 0, 1);
  const fatigue = clamp(num(eos.mental_fatigue, 0.3), 0, 1);

  let surface = stateForLabel(eos.surface_emotion);
  const core = stateForLabel(eos.core_emotion);

  // `flat` is a compound read, not a label: the classifier saw nothing
  // distinct while the state tracker shows the user running on empty.
  if (surface === "balanced" && fatigue >= 0.6 && distress >= 0.45) {
    surface = "flat";
  }

  if (!surface) return RESTING_READING;

  const state = EMOTION_STATES[surface];
  const blend = findBlend(surface, core);

  // Hard feelings are as loud as the distress behind them; soft ones are as
  // loud as the model's confidence that they're really there.
  const weight = state.valence === "hard" ? Math.max(distress, confidence * 0.7) : confidence;

  return {
    state,
    blend,
    coreState: core && core !== surface ? EMOTION_STATES[core] : null,
    intensity: clamp(0.1 + 0.9 * weight, 0.1, 1),
    confidence,
    subs: state.subs,
    resting: false,
  };
}

/**
 * The CSS custom properties the field, companion and accents all read from.
 * Applied to the app root; @property registration in tokens.css is what makes
 * these crossfade over 1.6s instead of snapping (§2, §6).
 */
export function emotionCssVars(
  reading: EmotionReading,
  intensityCap = 1,
): Record<string, string> {
  const { state, blend } = reading;
  const intensity = Math.min(reading.intensity, intensityCap);
  return {
    "--e1": state.c1,
    "--e2": state.c2,
    "--e3": state.c3,
    "--e-blend": blend?.color ?? state.c2,
    "--intensity": intensity.toFixed(3),
  };
}

/** Field motion parameters per temperament — consumed by the ShaderGradient
 * field and by the companion's springs so they always agree. */
export const TEMPERAMENT_MOTION: Record<
  Temperament,
  { speed: number; strength: number; amplitude: number }
> = {
  "slow drift": { speed: 0.14, strength: 1.3, amplitude: 6 },
  lifting: { speed: 0.26, strength: 1.8, amplitude: 8 },
  "bright pulse": { speed: 0.42, strength: 2.4, amplitude: 10 },
  "warm bloom": { speed: 0.22, strength: 1.9, amplitude: 7 },
  even: { speed: 0.2, strength: 1.5, amplitude: 6 },
  "quick tremor": { speed: 0.62, strength: 2.1, amplitude: 4 },
  "heavy sink": { speed: 0.1, strength: 1.1, amplitude: 3 },
  still: { speed: 0.05, strength: 0.7, amplitude: 2 },
  "ember flare": { speed: 0.5, strength: 2.8, amplitude: 9 },
  "sharp edge": { speed: 0.38, strength: 2.2, amplitude: 5 },
  shrink: { speed: 0.16, strength: 1.2, amplitude: 3 },
  "low hum": { speed: 0.08, strength: 0.9, amplitude: 2 },
};
