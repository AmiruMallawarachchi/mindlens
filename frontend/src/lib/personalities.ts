/**
 * How the user describes themselves, set in Settings > General.
 *
 * This is not a cosmetic label: the id is written into the empathy agent's
 * system prompt, so it genuinely changes how replies are worded. Each entry
 * therefore carries the guidance the backend should act on, not just a name —
 * keeping the "what it means" next to the option it belongs to, so the two
 * can't drift apart.
 */

export interface PersonalityDef {
  id: string;
  label: string;
  hint: string;
}

export const PERSONALITIES: PersonalityDef[] = [
  { id: "overthinker", label: "Overthinker", hint: "Loops on decisions. Wants the spiral named, not fed." },
  { id: "anxious_achiever", label: "Anxious achiever", hint: "Driven, but by fear of falling short." },
  { id: "highly_sensitive", label: "Highly sensitive", hint: "Feels things strongly and early. Needs room, not volume." },
  { id: "quiet_observer", label: "Quiet observer", hint: "Processes inwardly. Takes time to say the real thing." },
  { id: "analytical", label: "Analytical", hint: "Trusts reasoning. Prefers the why before the comfort." },
  { id: "doer", label: "Doer", hint: "Action settles them faster than discussion does." },
  { id: "optimist", label: "Optimist", hint: "Looks for the upside — sometimes too early." },
  { id: "realist", label: "Realist", hint: "Wants it straight. Reassurance without substance lands badly." },
  { id: "people_person", label: "People person", hint: "Recharges around others. Isolation hits hard." },
  { id: "private", label: "Private", hint: "Shares slowly. Don't push for more than is offered." },
];

export function getPersonality(id: string | null | undefined): PersonalityDef | null {
  return PERSONALITIES.find((p) => p.id === id) ?? null;
}

/** How direct Mindlens should be, set in Settings > General and (optionally)
 * during onboarding. Single source so the two pickers can't drift. */
export interface ToneDef {
  id: "gentle" | "balanced" | "direct";
  label: string;
  hint: string;
}

export const TONES: ToneDef[] = [
  { id: "gentle", label: "Gentle", hint: "Softer landings. Warmth before the point." },
  { id: "balanced", label: "Balanced", hint: "Warm, but says the hard thing when it matters." },
  { id: "direct", label: "Direct", hint: "Straight to it. Kind, not cushioned." },
];
