/**
 * The reasoning trail — design.md §4.1.
 *
 * Four steps, first person, with a coloured dot rail: Safety first / What I'm
 * reading / What I remember / So I'll try this. The therapy approach is named
 * here and *only* here — §4.1 forbids it in the conversation header.
 *
 * Every line below is derived from a field the backend actually sends. Where
 * a capability isn't wired up yet, the step says so plainly rather than
 * implying work that didn't happen — a wellbeing product that narrates
 * reasoning it didn't do is worse than one that stays quiet.
 */

import { EMOTION_STATES, stateForLabel, type EmotionReading } from "./emotion";
import type { EosSnapshot } from "./types";

export type ReasoningStepId = "safety" | "reading" | "memory" | "approach";

export interface ReasoningStep {
  id: ReasoningStepId;
  label: string;
  text: string;
  /** Renders the dot in the rail. "muted" marks a step that reports an
   * absence rather than a finding. */
  tone: "normal" | "alert" | "muted";
}

/** Agent names the backend reports, in the voice the trail speaks. */
const AGENT_PHRASES: Record<string, string> = {
  empathy: "sit with it first",
  cbt: "look at the thought behind it",
  dbt: "steady the intensity before anything else",
  act: "make room for it rather than argue with it",
  mindfulness: "slow the moment down",
  mi: "find what you actually want here",
  narrative: "retell this with you at the centre",
  crisis: "put your safety before the conversation",
  music: "offer something to listen to",
  memory: "hold on to what matters",
  progress: "look at how this compares to before",
  planning: "turn this into a next step",
  distortion: "check the shape of the thinking",
  checkin: "come back to what you said last time",
};

function humaniseAgents(agents: readonly string[]): string | null {
  const phrases = agents
    .map((a) => AGENT_PHRASES[a.replace(/_agent$/, "")])
    .filter((p): p is string => Boolean(p));
  if (phrases.length === 0) return null;
  if (phrases.length === 1) return phrases[0];
  if (phrases.length === 2) return `${phrases[0]}, then ${phrases[1]}`;
  return `${phrases.slice(0, -1).join(", ")}, then ${phrases[phrases.length - 1]}`;
}

export interface ReasoningInput {
  eos: EosSnapshot | null | undefined;
  reading: EmotionReading;
  agents: readonly string[];
  crisis: boolean;
  memoryRecalled: readonly string[];
  /** Reasons this turn fell back to canned text, from the `degraded` field. */
  degraded: readonly string[];
}

export function buildReasoningTrail(input: ReasoningInput): ReasoningStep[] {
  const { eos, reading, agents, crisis, memoryRecalled, degraded } = input;
  const distress = typeof eos?.distress_level === "number" ? eos.distress_level : null;

  // --- 1. Safety gate ----------------------------------------------------
  // Labels come from the approved mockup's trail (Mindlens Chat.dc.html):
  // Safety gate / Emotion read / Memory / Approach.
  //
  // The gate is two layers (safety_gate.py): a keyword regex that always
  // runs, and a crisis classifier that can fail like any model call. The
  // regex layer alone still catches everything unsafe — recall isn't zero —
  // but "Clear — no crisis signals" is a claim that *both* layers ran, and
  // orchestrator.py records `model:crisis` on the turn's degradation set
  // specifically for the case where that wasn't true. Reporting "Clear" in
  // that case overstates how much was actually checked.
  const crisisModelDown = degraded.includes("model:crisis");
  const safety: ReasoningStep = crisis
    ? {
        id: "safety",
        label: "Safety gate",
        text: "This needs to come before everything else. Everything pauses except your safety.",
        tone: "alert",
      }
    : crisisModelDown
      ? {
          id: "safety",
          label: "Safety gate",
          text: "Screened by the keyword gate only — the second-layer crisis model isn't responding right now. If anything here is urgent, please reach a human.",
          tone: "alert",
        }
      : {
          id: "safety",
          label: "Safety gate",
          text:
            distress !== null && distress >= 0.65
              ? `Clear — no crisis signals, though distress is running high at ${distress.toFixed(2)}, so I'm staying close to it.`
              : "Clear — no crisis signals. The door stays open, quietly.",
          tone: "normal",
        };

  // --- 2. What I'm reading ----------------------------------------------
  const surfaceName = reading.state.name.toLowerCase();
  const coreLabel = eos?.core_emotion;
  const coreState = stateForLabel(coreLabel);
  const readingParts: string[] = [];

  if (reading.resting) {
    readingParts.push("I haven't got a read on you yet — this is the first thing you've said.");
  } else {
    readingParts.push(
      reading.confidence !== null
        ? `On the surface I'm reading ${surfaceName}, at ${reading.confidence.toFixed(2)} confidence.`
        : `On the surface I'm reading ${surfaceName}.`,
    );
    if (coreState && coreState !== reading.state.id) {
      readingParts.push(
        `Underneath it feels closer to ${EMOTION_STATES[coreState].name.toLowerCase()}.`,
      );
    }
    if (reading.blend) {
      readingParts.push(`Both at once — that's ${reading.blend.name.toLowerCase()}.`);
    }
    if (eos?.suppressed_emotion) {
      readingParts.push(`There may be some ${eos.suppressed_emotion} you're holding back.`);
    }
    if (eos?.distortion_label) {
      // Hedged on purpose. This comes from the weakest model in the set
      // (0.17 macro-F1 over ten classes, trained on ~690 weakly-labelled
      // examples), and a flat "the thinking has X shape to it" states a
      // near-chance argmax as a finding about the person reading it.
      readingParts.push(
        `This might have a ${eos.distortion_label.replace(/_/g, " ")} shape to it — that read is the least reliable thing here.`,
      );
    }
  }

  const readingStep: ReasoningStep = {
    id: "reading",
    label: "Emotion read",
    text: readingParts.join(" "),
    tone: reading.resting ? "muted" : "normal",
  };

  // --- 3. What I remember -----------------------------------------------
  // memory_recalled is a real lookup (backend/app/core/memory_recall.py):
  // empty means nothing on file was relevant to *this* turn, not that
  // recall is unimplemented — most turns won't match anything, and that's
  // meant to read as normal, not as a gap.
  const memory: ReasoningStep =
    memoryRecalled.length > 0
      ? {
          id: "memory",
          label: "Memory",
          text: memoryRecalled.join(" · "),
          tone: "normal",
        }
      : {
          id: "memory",
          label: "Memory",
          text: "Nothing from before applies here — just working from this conversation.",
          tone: "muted",
        };

  // --- 4. So I'll try this ----------------------------------------------
  // §4.1: the approach is named here and nowhere else in the UI.
  const modality = typeof eos?.modality === "string" ? eos.modality : null;
  const intent = humaniseAgents(agents);
  const approachParts: string[] = [];

  if (intent) approachParts.push(`I'm going to ${intent}.`);
  if (modality) approachParts.push(`Working from ${modality}.`);
  if (!intent && !modality) {
    approachParts.push("Staying with what you said and following where it goes.");
  }
  // model:* entries are a classifier that didn't respond (already disclosed,
  // for crisis, in the safety step above) — a different failure from an LLM
  // fallback, and "this reply is more generic" is the wrong description for
  // it, so the two are reported separately rather than pooled.
  const modelDegraded = degraded.filter((d) => d.startsWith("model:"));
  const llmDegraded = degraded.filter((d) => !d.startsWith("model:"));
  if (llmDegraded.length > 0) {
    approachParts.push(
      `Heads up — the language model fell back this turn (${llmDegraded.join(", ")}), so this reply is more generic than usual.`,
    );
  }
  const otherModelsDown = modelDegraded.filter((d) => d !== "model:crisis");
  if (otherModelsDown.length > 0) {
    approachParts.push(
      `One of the reads behind this reply didn't come back (${otherModelsDown.join(", ")}) — the rest of the pipeline still ran normally.`,
    );
  }

  const approach: ReasoningStep = {
    id: "approach",
    label: "Approach",
    text: approachParts.join(" "),
    tone: llmDegraded.length > 0 || otherModelsDown.length > 0 ? "alert" : "normal",
  };

  return crisis ? [safety] : [safety, readingStep, memory, approach];
}
