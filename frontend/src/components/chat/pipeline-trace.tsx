"use client";

/**
 * The mechanical view of a turn: which stage ran, with what, and what came
 * back — rendered with AI Elements' Task/Tool primitives, the same shape
 * Claude uses to show a tool call.
 *
 * This sits *underneath* the prose reasoning trail rather than replacing it.
 * The two answer different questions and both are worth keeping: the prose
 * says "I'm going to sit with it first" in the companion's voice, this says
 * `empathy · Completed`. Collapsing them into one would either make the
 * companion sound like a debugger or hide the pipeline behind metaphor.
 *
 * Every row is built from telemetry the backend actually sent. Nothing here
 * is inferred, and a stage with no data is omitted rather than shown in an
 * invented state — a "Completed" badge on a stage that never ran would be
 * exactly the kind of confident-looking fiction this panel exists to
 * prevent.
 */

import { Task, TaskContent, TaskTrigger } from "@/components/ai-elements/task";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import type { ChatMessage } from "@/lib/types";

/** Human-readable names for the agents the registry actually registers. */
const AGENT_TITLES: Record<string, string> = {
  empathy: "empathy",
  mindfulness: "mindfulness",
  crisis: "crisis",
  reflection: "reflection",
  challenge: "challenge",
  distortion: "distortion",
  routine: "routine",
  journaling: "journaling",
  music: "music",
  checkin: "checkin",
  progress: "progress",
  personality: "personality",
  checkin_scheduler: "checkin_scheduler",
  session_memory_save: "session_memory_save",
};

export function PipelineTrace({ message }: { message: ChatMessage }) {
  const telemetry = message.telemetry;
  const safety = message.safety;
  const agents = (message.agentsUsed ?? []).map((a) => a.replace(/_agent$/, ""));
  const degraded = message.degraded ?? [];
  const rag = telemetry?.rag;

  if (agents.length === 0 && !telemetry && !safety) return null;

  const stageCount =
    1 + (message.eos ? 1 : 0) + (rag ? 1 : 0) + 1 + agents.length;

  return (
    <Task
      defaultOpen={false}
      className="rounded-[var(--r-13)] border px-3 py-2.5"
      style={{
        borderColor: "var(--ml-hairline)",
        background: "color-mix(in oklab, var(--ml-ink) 2.5%, transparent)",
      }}
    >
      <TaskTrigger title={`Pipeline · ${stageCount} stages`} />
      <TaskContent>
        {/* 1. Safety gate — the one stage that runs on literally every turn. */}
        <PipelineTool
          name="safety_gate"
          state={safety?.is_crisis ? "output-error" : "output-available"}
          input={{ layers: ["regex", "mindlens-crisis"] }}
          output={
            safety?.is_crisis
              ? `CRISIS — ${safety.layer_triggered ?? "unknown"} layer triggered${
                  typeof safety.confidence === "number"
                    ? ` at ${safety.confidence.toFixed(2)}`
                    : ""
                }`
              : degraded.includes("model:crisis")
                ? "Regex layer clear. Classifier unavailable this turn."
                : "Both layers clear."
          }
        />

        {/* 2. The emotion read, straight off the EOS the backend sent. */}
        {message.eos && (
          <PipelineTool
            name="emotion_classifier"
            state="output-available"
            input={{ model: "roberta-base-go_emotions", classes: 28 }}
            output={[
              message.eos.surface_emotion &&
                `surface: ${message.eos.surface_emotion}${
                  typeof message.eos.surface_confidence === "number"
                    ? ` (${message.eos.surface_confidence.toFixed(2)})`
                    : ""
                }`,
              message.eos.core_emotion && `core: ${message.eos.core_emotion}`,
              message.eos.suppressed_emotion &&
                `suppressed: ${message.eos.suppressed_emotion}`,
              typeof message.eos.distress_level === "number" &&
                `distress: ${message.eos.distress_level.toFixed(2)}`,
            ]
              .filter(Boolean)
              .join("\n")}
          />
        )}

        {/* 3. Retrieval — only when the backend reported a status for it. */}
        {rag && (
          <PipelineTool
            name="therapy_retrieval"
            state={
              rag.status === "failed"
                ? "output-error"
                : rag.status === "ran"
                  ? "output-available"
                  : "output-denied"
            }
            input={{
              store: "chromadb",
              reranker: rag.model ?? "disabled",
            }}
            output={
              rag.status === "ran"
                ? `${rag.chunks} passage${rag.chunks === 1 ? "" : "s"} retrieved${
                    rag.model ? `, reranked by ${rag.model}` : ""
                  }`
                : rag.status === "skipped_trivial"
                  ? "Skipped — turn too brief to retrieve for."
                  : rag.status === "skipped_crisis"
                    ? "Skipped — crisis turns never retrieve."
                    : rag.status === "failed"
                      ? "Retrieval failed; replied from the conversation alone."
                      : "Chunks supplied by the caller."
            }
          />
        )}

        {/* 4. Memory. An empty recall is a real result, not a missing one. */}
        <PipelineTool
          name="memory_recall"
          state="output-available"
          input={{ scope: "user_memory" }}
          output={
            (message.memoryRecalled ?? []).length > 0
              ? (message.memoryRecalled ?? []).join("\n")
              : "Nothing on file matched this turn."
          }
        />

        {/* 5. Every agent the orchestrator actually ran. */}
        {agents.map((agent) => (
          <PipelineTool
            key={agent}
            name={AGENT_TITLES[agent] ?? agent}
            state="output-available"
            input={{
              agent,
              modality: telemetry?.modality ?? null,
            }}
            output={
              AGENT_TITLES[agent]
                ? "Ran."
                : "Ran — no description registered for this agent."
            }
          />
        ))}
      </TaskContent>
    </Task>
  );
}

function PipelineTool({
  name,
  state,
  input,
  output,
}: {
  name: string;
  state: "output-available" | "output-error" | "output-denied";
  input: Record<string, unknown>;
  output: string;
}) {
  return (
    <Tool className="group border-none bg-transparent">
      <ToolHeader
        type="dynamic-tool"
        toolName={name}
        state={state}
        className="px-0 py-1.5"
      />
      <ToolContent>
        <ToolInput input={input} />
        <ToolOutput output={output} errorText={undefined} />
      </ToolContent>
    </Tool>
  );
}
