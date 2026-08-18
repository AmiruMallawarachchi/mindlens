"use client";

/**
 * The reasoning trail — design.md §4.1.
 *
 * Built on AI Elements' <Reasoning>, which supplies the collapsible shell and
 * the streaming/duration context. The body is a custom four-step dot rail
 * rather than <ReasoningContent>, because that primitive takes a markdown
 * string and this is structured content with a coloured rail per step.
 *
 * Collapsed by default. It used to open automatically and show four dense
 * blocks on every turn, which buried the reply itself. The trigger carries a
 * one-line summary built from the same facts as the steps, so the collapsed
 * state still says what happened and can never contradict the expansion.
 */

import { useState } from "react";
import { motion } from "motion/react";
import { CollapsibleContent } from "@/components/ui/collapsible";
import { Reasoning, ReasoningTrigger } from "@/components/ai-elements/reasoning";
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
  className,
}: {
  steps: ReasoningStep[];
  /** One line for the collapsed state — see summariseTrail. */
  summary?: string;
  isStreaming?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  if (steps.length === 0) return null;

  return (
    <Reasoning
      className={cn("w-full", className)}
      isStreaming={isStreaming}
      open={open}
      onOpenChange={setOpen}
    >
      <ReasoningTrigger
        className="ml-eyebrow gap-2 hover:opacity-80"
        getThinkingMessage={(streaming) => (
          <span className="ml-eyebrow">
            {streaming ? "Working it through" : "How I got here"}
          </span>
        )}
      >
        <span className="flex items-center gap-2">
          {/* Spinner ring while streaming (§4.1). */}
          {isStreaming ? (
            <span
              className="size-3 animate-spin rounded-full border-[1.5px] border-transparent"
              style={{ borderTopColor: "var(--e1)", borderRightColor: "var(--e1)" }}
            />
          ) : (
            <span
              className="size-1.5 rounded-full"
              style={{ background: "var(--e1)" }}
            />
          )}
          {/* Collapsed, this is the whole trail: what ran, what it looked up,
            * whether anything degraded. Expanding adds detail, never a
            * different story. */}
          <span className="ml-eyebrow">
            {isStreaming ? "Working it through" : (summary ?? "How I got here")}
          </span>
          <span className="ml-eyebrow" style={{ opacity: 0.55 }}>
            {open ? "hide" : "show"}
          </span>
        </span>
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
