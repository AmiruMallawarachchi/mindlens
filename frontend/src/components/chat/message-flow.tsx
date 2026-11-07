"use client";

/**
 * The message flow — ported from the approved mockup (MindLens Chat.dc.html).
 *
 * User turns: right-aligned bubbles with an asymmetric 18/18/5/18 radius and
 * the emotion read strip beneath. Assistant turns: no bubble — the companion
 * blob avatar, the reasoning trail, reply text in the UI face (Newsreader is
 * kept for titles and the opening room, where it is not read at length),
 * then a compact actions row (Copy / Regenerate / Read aloud) and any inline
 * cards in a two-column grid.
 */

import { useMemo } from "react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { EmotionRead } from "./emotion-read";
import { ReasoningTrail } from "./reasoning-trail";
import { PipelineTrace } from "./pipeline-trace";
import { BreatheCard } from "./breathe-card";
import { resolveEmotion } from "@/lib/emotion";
import { buildReasoningTrail, summariseTrail } from "@/lib/reasoning";
import type { ChatMessage } from "@/lib/types";
import { OptionChoices, TurnActions } from "./message-flow-actions";

/** One entry per paragraph; an empty reply still yields one so the streaming
 * caret has somewhere to sit. */
function replyParagraphs(text: string): string[] {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
  return paragraphs.length > 0 ? paragraphs : [""];
}

export function UserTurn({ message }: { message: ChatMessage }) {
  const reading = useMemo(() => resolveEmotion(message.eos), [message.eos]);

  return (
    <div className="flex flex-col items-end gap-2">
      <div
        className="max-w-[540px] border px-[17px] py-[13px] text-[14.5px] leading-[1.6]"
        style={{
          borderRadius: "18px 18px 5px 18px",
          background: "var(--ml-panel-legible)",
          borderColor: "var(--ml-hairline-strong)",
          color: "var(--ml-ink)",
          boxShadow: "0 10px 26px -18px rgba(0,0,0,.35)",
        }}
      >
        {message.text}
      </div>
      <EmotionRead reading={reading} className="max-w-[78%]" />
    </div>
  );
}

export function AssistantTurn({
  message,
  isStreaming = false,
  onRegenerate,
  companionId,
  onChooseOption,
  showOptions = false,
}: {
  message: ChatMessage;
  isStreaming?: boolean;
  onRegenerate?: (() => void) | null;
  companionId?: string;
  /** Sends the chosen answer as an ordinary message. */
  onChooseOption?: (text: string) => void;
  /** Only the newest turn offers its options — buttons on a turn three
   * messages back answer a question that has already moved on. */
  showOptions?: boolean;
}) {
  const reading = useMemo(() => resolveEmotion(message.eos), [message.eos]);

  const steps = useMemo(() => {
    // Only turns that actually carry telemetry get a trail. A hydrated turn
    // from session history has no agents recorded, so it gets none rather
    // than a trail reconstructed out of nothing.
    if (!message.eos || !message.agentsUsed) return [];
    return buildReasoningTrail({
      eos: message.eos,
      reading,
      agents: message.agentsUsed,
      crisis: Boolean(message.crisis),
      memoryRecalled: message.memoryRecalled ?? [],
      degraded: message.degraded ?? [],
      telemetry: message.telemetry,
      safety: message.safety,
    });
  }, [message, reading]);

  // Same inputs as the steps, so the collapsed line can never claim
  // something the expanded trail contradicts.
  const summary = useMemo(() => {
    if (!message.eos || !message.agentsUsed) return undefined;
    return summariseTrail({
      eos: message.eos,
      reading,
      agents: message.agentsUsed,
      crisis: Boolean(message.crisis),
      memoryRecalled: message.memoryRecalled ?? [],
      degraded: message.degraded ?? [],
      telemetry: message.telemetry,
      safety: message.safety,
    });
  }, [message, reading]);

  // Inline cards appear only when the turn genuinely warrants them: the
  // breathe player when a breathing-adjacent agent ran.
  const offersBreathing = useMemo(() => {
    const agents = (message.agentsUsed ?? []).map((a) => a.replace(/_agent$/, ""));
    return agents.includes("mindfulness") || agents.includes("dbt");
  }, [message.agentsUsed]);
  const hasCards = offersBreathing;

  // The "asking" state — the companion tilts and a "?" blooms. Only once the
  // reply is complete; mid-stream a trailing "?" isn't yet the final shape.
  const endsInQuestion = !isStreaming && message.text.trimEnd().endsWith("?");

  if (message.kind === "error") {
    return (
      <div
        className="ml-glass mx-auto w-full rounded-[var(--r-16)] px-4 py-3 text-[13px] italic"
        style={{ color: "var(--ml-faint)" }}
      >
        {message.text}
      </div>
    );
  }

  return (
    <div className="flex w-full gap-3">
      {/* 44px, matching the thinking row in chat-screen.tsx — the two sit in
        * the same transcript gutter and must stay the same width. */}
      <div className="w-[44px] shrink-0 pt-0.5">
        {/* Crisis: the companion holds completely still — "safety kills the
          * spectacle". `frozen` gates every animation, ambient and per-state. */}
        <CompanionAvatar
          companionId={companionId}
          size={44}
          mood={reading.state.id}
          activity={isStreaming ? "thinking" : endsInQuestion ? "asking" : "idle"}
          frozen={!!message.crisis}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-3.5 pb-2">
        {steps.length > 0 && (
          <ReasoningTrail steps={steps} summary={summary} isStreaming={isStreaming} duration={message.thinkingDurationS} />
        )}

        {/* The mechanical counterpart to the prose trail above — collapsed
          * by default, so the default reading experience is unchanged. */}
        {!isStreaming && steps.length > 0 && <PipelineTrace message={message} />}

        {/* One paragraph per blank line, whitespace-pre-line inside each, so
          * a guided exercise's one-step-per-line survives. The assembler joins
          * empathy and the specialist with "\n\n"; rendered as a single block
          * at this size that read as one wall with no breathing room. Only
          * newlines are honoured, so message text still cannot inject layout. */}
        <div
          className="flex flex-col gap-[0.85em] text-[15.5px] leading-[1.62]"
          style={{ color: "var(--ml-ink)", textWrap: "pretty" }}
        >
          {replyParagraphs(message.text).map((paragraph, index, all) => (
            <p key={index} className="m-0 whitespace-pre-line">
              {paragraph}
              {isStreaming && index === all.length - 1 && (
                <span
                  className="ml-0.5 inline-block h-[1em] w-[2px] align-text-bottom"
                  style={{ background: "var(--e1)", animation: "mlCaret 1s step-end infinite" }}
                />
              )}
            </p>
          ))}
        </div>

        {!isStreaming && (
          <TurnActions text={message.text} onRegenerate={onRegenerate ?? null} />
        )}

        {showOptions && !isStreaming && message.options && onChooseOption && (
          <OptionChoices payload={message.options} onChoose={onChooseOption} />
        )}

        {hasCards && !isStreaming && (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(258px, 1fr))" }}>
            {offersBreathing && <BreatheCard />}
          </div>
        )}
      </div>
    </div>
  );
}
