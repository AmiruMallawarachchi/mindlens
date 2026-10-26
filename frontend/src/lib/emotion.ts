import type { EosSnapshot } from "./types";
import { EMOTION_STATES, findBlend, stateForLabel } from "./emotion-catalog";
import type { Blend, EmotionState, Temperament } from "./emotion-catalog";
export * from "./emotion-catalog";

export interface EmotionReading {
  /** The state driving the field, companion and accents. */
  state: EmotionState;
  /** Present only when the core read differs and forms a named blend. */
  blend: Blend | null;
  /** The core state when it differs from the surface one, blend or not. */
  coreState: EmotionState | null;
  /** 0.1â€“1.0 â€” scales field opacity, glow radius, motion amplitude, accent
   * saturation. Â§2: at 0.2 the room is barely tinted; at 1.0 everything agrees. */
  intensity: number;
  /** Classifier confidence in the surface read, shown beside the name. */
  confidence: number | null;
  /** Sub-emotion chips for the emotion read strip. */
  subs: readonly string[];
  /** True when nothing has been read yet â€” render the resting state. */
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
 * Settings > Appearance's intensity cap (design.md Â§2: "users who want
 * stillness can cap it"). Returns a new reading with `intensity` clamped so
 * every consumer downstream â€” the field's wash opacity, this module's own
 * emotionCssVars â€” agrees, rather than only the CSS variable capping while
 * the field's own opacity math (which reads `reading.intensity` directly,
 * not the CSS var) ignores it.
 */
export function capIntensity(reading: EmotionReading, cap = 1): EmotionReading {
  if (cap >= 1) return reading;
  return { ...reading, intensity: Math.min(reading.intensity, cap) };
}

/**
 * The CSS custom properties the field, companion and accents all read from.
 * Applied to the app root; @property registration in tokens.css is what makes
 * these crossfade over 1.6s instead of snapping (Â§2, Â§6).
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

/** Field motion parameters per temperament â€” consumed by the ShaderGradient
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
