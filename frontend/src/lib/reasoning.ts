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
import type { EosSnapshot, SafetyVerdict, TurnTelemetry } from "./types";

export type ReasoningStepId = "safety" | "reading" | "memory" | "approach";

export interface ReasoningStep {
  id: ReasoningStepId;
  label: string;
  text: string;
  /** Renders the dot in the rail. "muted" marks a step that reports an
   * absence rather than a finding. */
  tone: "normal" | "alert" | "muted";
}

/** Agent names the backend reports, in the voice the trail speaks.
 *
 * These are the fourteen agents orchestrator._init_registry actually
 * registers. The previous table had six entries for things that are not
 * agents and never run — cbt, dbt, act, mi, narrative, planning — while
 * silently dropping seven that do, because humaniseAgents filtered out
 * anything it had no phrase for. The trail therefore under-reported real
 * work and implied modality-specific agents the codebase doesn't contain.
 *
 * Silent agents are mapped to null: they genuinely ran but did nothing the
 * user would recognise as part of the reply, so they are excluded from the
 * sentence rather than described. Anything absent from this map is reported
 * by name instead of dropped. */
const AGENT_PHRASES: Record<string, string | null> = {
  empathy: "sit with it first",
  mindfulness: "slow the moment down",
  crisis: "put your safety before the conversation",
  reflection: "say back what I'm hearing",
  challenge: "question the thought gently",
  distortion: "check the shape of the thinking",
  routine: "look for one small next step",
  journaling: "offer something to write about",
  music: "offer something to listen to",
  checkin: "come back to what you said last time",
  progress: "look at how this compares to before",
  // Bookkeeping. They run every turn and describing them would be noise.
  personality: null,
  checkin_scheduler: null,
  session_memory_save: null,
};

function humaniseAgents(agents: readonly string[]): string | null {
  const phrases: string[] = [];
  for (const raw of agents) {
    const name = raw.replace(/_agent$/, "");
    if (!(name in AGENT_PHRASES)) {
      // Unknown to this table but it really ran — name it rather than hide
      // it. Under-reporting is still misreporting.
      phrases.push(`run ${name}`);
      continue;
    }
    const phrase = AGENT_PHRASES[name];
    if (phrase) phrases.push(phrase);
  }
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
  /** What the pipeline actually did. Absent on older persisted messages. */
  telemetry?: TurnTelemetry | null;
  /** The gate's real verdict, rather than an assumed one. */
  safety?: SafetyVerdict | null;
}

export function buildReasoningTrail(input: ReasoningInput): ReasoningStep[] {
  const { eos, reading, agents, crisis, memoryRecalled, degraded, telemetry, safety } =
    input;
  const distress = typeof eos?.distress_level === "number" ? eos.distress_level : null;

  // --- 1. Safety gate ----------------------------------------------------
  // Labels come from the approved mockup's trail (Mindlens Chat.dc.html):
  // Safety gate / Emotion read / Memory / Approach.
  //
  // The gate is two layers: a keyword regex that always runs, and a crisis
  // classifier that can fail like any model call. The verdict object is now
  // sent (connection_manager's `safety` field); it used to be computed and
  // dropped, which is why this sentence was a hardcoded literal that claimed
  // both layers had cleared no matter what actually happened.
  const crisisModelDown = degraded.includes("model:crisis");
  const layer = safety?.layer_triggered ?? null;
  const safetyStep: ReasoningStep = crisis
    ? {
        id: "safety",
        label: "Safety gate",
        text: layer
          ? `This needs to come before everything else — the ${layer === "regex" ? "keyword" : "crisis"} layer flagged it. Everything pauses except your safety.`
          : "This needs to come before everything else. Everything pauses except your safety.",
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
              ? `Both layers clear, though distress is running high at ${distress.toFixed(2)}, so I'm staying close to it.`
              : "Both layers clear — no crisis signals. The door stays open, quietly.",
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
  //
  // Modality comes from telemetry, not from eos. Every turn carries a
  // modality field (CBT unless distress > 0.7) whether or not anything
  // consulted it, so reading it directly printed "Working from CBT." on
  // replies where no modality-driven agent had run at all. The backend now
  // sends null in that case and this states nothing rather than guessing.
  const modality = telemetry?.modality ?? null;
  const intent = humaniseAgents(agents);
  const approachParts: string[] = [];

  if (intent) approachParts.push(`I'm going to ${intent}.`);
  if (modality) approachParts.push(`Working from ${modality}.`);
  if (!intent && !modality) {
    approachParts.push("Staying with what you said and following where it goes.");
  }

  // Retrieval, reported rather than left silent. The UI never mentioned RAG
  // in any form, so a turn that searched the therapy corpus and one that
  // skipped it read identically.
  const rag = telemetry?.rag;
  if (rag) {
    if (rag.status === "ran" && rag.chunks > 0) {
      approachParts.push(
        `Pulled ${rag.chunks} passage${rag.chunks === 1 ? "" : "s"} from the therapy notes to check myself against.`,
      );
    } else if (rag.status === "ran") {
      approachParts.push("Searched the therapy notes and nothing matched closely enough to use.");
    } else if (rag.status === "skipped_trivial") {
      approachParts.push("No need to look anything up for this one.");
    } else if (rag.status === "failed") {
      approachParts.push("Couldn't reach the therapy notes this turn, so this is from the conversation alone.");
    }
  }

  // Three genuinely different failures, reported as three different things.
  // They used to share one bucket, so a cross-encoder fallback rendered as
  // "the language model fell back this turn" — which was simply untrue about
  // which component had broken.
  const modelDegraded = degraded.filter((d) => d.startsWith("model:"));
  const ragDegraded = degraded.filter((d) => d.startsWith("rag:"));
  const llmDegraded = degraded.filter(
    (d) => !d.startsWith("model:") && !d.startsWith("rag:"),
  );
  if (llmDegraded.length > 0) {
    approachParts.push(
      `Heads up — the language model fell back this turn (${llmDegraded.join(", ")}), so this reply is more generic than usual.`,
    );
  }
  if (ragDegraded.length > 0) {
    approachParts.push(
      "The passage re-ranker didn't respond, so anything I looked up was ordered less precisely than usual. The reply itself is unaffected.",
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
    tone:
      llmDegraded.length > 0 || otherModelsDown.length > 0 || ragDegraded.length > 0
        ? "alert"
        : "normal",
  };

  return crisis ? [safetyStep] : [safetyStep, readingStep, memory, approach];
}

/**
 * One line for the collapsed trail — what happened, at a glance.
 *
 * Built from the same facts as the steps, so it can never claim something
 * the expanded view contradicts.
 */
export function summariseTrail(input: ReasoningInput): string {
  const { agents, crisis, degraded, telemetry, memoryRecalled } = input;
  if (crisis) return "Safety first — everything else paused";

  const parts: string[] = [];

  const speaking = agents
    .map((a) => a.replace(/_agent$/, ""))
    .filter((a) => AGENT_PHRASES[a] !== null);
  parts.push(
    speaking.length === 0
      ? "no agents"
      : `${speaking.length} agent${speaking.length === 1 ? "" : "s"}`,
  );

  const rag = telemetry?.rag;
  if (rag?.status === "ran" && rag.chunks > 0) parts.push(`${rag.chunks} passages`);
  else if (rag) parts.push("no retrieval");

  if (telemetry?.modality) parts.push(telemetry.modality);
  if (memoryRecalled.length > 0) parts.push("memory recalled");
  if (degraded.length > 0) parts.push("degraded");

  return `safety clear · ${parts.join(" · ")}`;
}
