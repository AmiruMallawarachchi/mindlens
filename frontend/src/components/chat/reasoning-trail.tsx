"use client";

/**
 * The reasoning trail — design.md §4.1.
 *
 * Built on AI Elements' <Reasoning>, which supplies the collapsible shell,
 * the streaming/duration tracking, and — this is the part that matters —
 * the trigger's default phrasing: "Thought for 4 seconds", muted, sans
 * serif, a small chevron. That is the exact register a chat product uses;
 * it was previously overridden with a custom mono-caps, pipe-delimited
 * stats line ("SAFETY CLEAR · 2 AGENTS · 5 PASSAGES · CBT") that sat above
 * every reply looking like a system status readout rather than part of a
 * conversation. The trigger below goes back to the primitive's own
 * children, with one honest clause appended when there's something worth
 * mentioning (see summariseTrail) — the way "used web_search" reads next
 * to a normal tool-call summary, not a metrics dump.
 *
 * The body is a custom four-step dot rail rather than <ReasoningContent>,
 * because that primitive takes a markdown string and this is structured
 * content with a coloured rail per step.
 *
 * Collapsed by default, always — defaultOpen={false} disables the
 * primitive's own auto-open-while-streaming behaviour (see the prop below).
 * It used to open automatically and show four dense blocks on every turn,
 * including "Hi", which buried the reply itself.
 */

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { motion } from "motion/react";
import { CollapsibleContent } from "@/components/ui/collapsible";
import { Reasoning, ReasoningTrigger, useReasoning } from "@/components/ai-elements/reasoning";
import type { ReasoningStep } from "@/lib/reasoning";
import { cn } from "@/lib/utils";

const DOT_COLOR: Record<ReasoningStep["tone"], string> = {
  normal: "var(--e1)",
  alert: "#ffb15f",
  muted: "var(--ml-faint)",
};

export function ReasoningTrail({
  steps,
  summary,
  isStreaming = false,
  duration,
  className,
}: {
  steps: ReasoningStep[];
  /** One honest clause, or null when there's nothing worth flagging — see
   * summariseTrail. Appended after the primitive's own "Thought for Ns". */
  summary?: string | null;
  isStreaming?: boolean;
  /** Real measured seconds (use-mindlens-client's thinkingStartRef), for the
   * persisted trail. Omit on the live trail — that instance genuinely
   * observes its own streaming transition and can compute this itself. */
  duration?: number;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  if (steps.length === 0) return null;

  return (
    <Reasoning
      className={cn("w-full", className)}
      isStreaming={isStreaming}
      duration={duration}
      open={open}
      onOpenChange={setOpen}
      // Load-bearing. The underlying primitive auto-opens itself whenever
      // isStreaming is true unless defaultOpen is explicitly false. Without
      // this, every turn force-expanded four blocks of machine narration
      // above the reply — so "Hi" produced four paragraphs about safety
      // layers and memory lookups before a one-line answer. The trail is
      // opt-in, always.
      defaultOpen={false}
    >
      <ReasoningTrigger className="w-fit gap-1.5 text-[12.5px]">
        <TriggerLabel summary={summary} />
      </ReasoningTrigger>

      <CollapsibleContent className="mt-3">
        <ol className="relative flex flex-col gap-3 pl-4">
          {/* The rail itself. */}
          <span
            aria-hidden="true"
            className="absolute left-[3px] top-1.5 bottom-1.5 w-px"
            style={{
              background:
                "linear-gradient(to bottom, color-mix(in oklab, var(--e1) 55%, transparent), transparent)",
            }}
          />
          {steps.map((step, index) => {
            const isLast = index === steps.length - 1;
            return (
              <motion.li
                key={step.id}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.08, duration: 0.4 }}
                className="relative"
              >
                <span
                  aria-hidden="true"
                  className="absolute -left-4 top-[6px] size-[7px] rounded-full"
                  style={{
                    background: DOT_COLOR[step.tone],
                    boxShadow:
                      step.tone === "normal"
                        ? "0 0 8px color-mix(in oklab, var(--e1) 70%, transparent)"
                        : undefined,
                  }}
                />
                <p
                  className="ml-eyebrow mb-1"
                  style={{ color: "var(--ml-faint)" }}
                >
                  {step.label}
                </p>
                <p
                  className="text-[13px] leading-[1.55]"
                  style={{
                    color: step.tone === "muted" ? "var(--ml-faint)" : "var(--ml-muted)",
                    textWrap: "pretty",
                  }}
                >
                  {step.text}
                  {/* Streaming caret on the last line (§4.1). */}
                  {isStreaming && isLast && (
                    <span
                      className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse align-text-bottom"
                      style={{ background: "var(--e1)" }}
                    />
                  )}
                </p>
              </motion.li>
            );
          })}
        </ol>
      </CollapsibleContent>
    </Reasoning>
  );
}

/**
 * The trigger's content — one leading dot, "Thought for Ns" (real, from the
 * primitive's own duration tracking), one honest clause, one chevron. No
 * BrainIcon: <ReasoningTrigger> without a `children` prop renders its own
 * icon + chevron composition, which would double up against this dot.
 * Supplying children here takes full control instead.
 */
function TriggerLabel({ summary }: { summary?: string | null }) {
  const { isStreaming, isOpen, duration } = useReasoning();

  return (
    <span className="flex items-center gap-1.5">
      <span
        className="size-[5px] shrink-0 rounded-full"
        style={{
          background: "var(--e1)",
          animation: isStreaming ? "mlPulse 1.4s ease-in-out infinite" : undefined,
        }}
      />
      <span style={{ color: "var(--ml-faint)" }}>
        {isStreaming
          ? "Thinking"
          : duration
            ? `Thought for ${duration}s`
            : "A quick thought"}
      </span>
      {!isStreaming && summary && (
        <span style={{ color: "var(--ml-muted)" }}>&middot; {summary}</span>
      )}
      <ChevronDown
        size={13}
        strokeWidth={1.8}
        className={cn("transition-transform", isOpen ? "rotate-180" : "rotate-0")}
        style={{ color: "var(--ml-faint)" }}
      />
    </span>
  );
}
