"use client";

/**
 * The message flow — ported from the approved mockup (Mindlens Chat.dc.html).
 *
 * User turns: right-aligned bubbles with an asymmetric 18/18/5/18 radius and
 * the emotion read strip beneath. Assistant turns: no bubble — the Nimbus
 * blob avatar, the reasoning trail, editorial text, then a compact actions
 * row (Copy / Regenerate / Read aloud–soon) and any inline cards in a
 * two-column grid.
 */

import { useCallback, useMemo, useState } from "react";
import { Check, Copy, RefreshCw, Volume2 } from "lucide-react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { EmotionRead } from "./emotion-read";
import { ReasoningTrail } from "./reasoning-trail";
import { BreatheCard } from "./breathe-card";
import { MusicCard } from "./music-card";
import { resolveEmotion } from "@/lib/emotion";
import { buildReasoningTrail } from "@/lib/reasoning";
import type { ChatMessage } from "@/lib/types";

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
}: {
  message: ChatMessage;
  isStreaming?: boolean;
  onRegenerate?: (() => void) | null;
  companionId?: string;
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
    });
  }, [message, reading]);

  // Inline cards appear only when the turn genuinely warrants them: the
  // breathe player when a breathing-adjacent agent ran, the music player
  // when the backend sent a real payload.
  const offersBreathing = useMemo(() => {
    const agents = (message.agentsUsed ?? []).map((a) => a.replace(/_agent$/, ""));
    return agents.includes("mindfulness") || agents.includes("dbt");
  }, [message.agentsUsed]);
  const music = message.music ?? null;
  const hasCards = offersBreathing || music !== null;

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
      <div className="w-[30px] shrink-0 pt-0.5">
        <CompanionAvatar companionId={companionId} size={30} mood={reading.state.id} activity={isStreaming ? "thinking" : "idle"} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-3.5 pb-2">
        {steps.length > 0 && <ReasoningTrail steps={steps} isStreaming={isStreaming} />}

        <p className="m-0 text-[14.5px] leading-[1.68]" style={{ color: "var(--ml-ink)", textWrap: "pretty" }}>
          {message.text}
          {isStreaming && (
            <span
              className="ml-0.5 inline-block h-[1em] w-[2px] align-text-bottom"
              style={{ background: "var(--e1)", animation: "mlCaret 1s step-end infinite" }}
            />
          )}
        </p>

        {!isStreaming && (
          <TurnActions text={message.text} onRegenerate={onRegenerate ?? null} />
        )}

        {hasCards && !isStreaming && (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(258px, 1fr))" }}>
            {offersBreathing && <BreatheCard />}
            {music && <MusicCard music={music} />}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Actions row from the mockup: Copy · Regenerate · Read aloud (soon).
 * Regenerate resends the previous user message — only offered on the last
 * assistant turn, where "try that again" has a well-defined meaning.
 * Read-aloud is explicitly labelled "soon" in the mockup; it's a visible
 * declared-future control there, so it renders disabled rather than hidden.
 */
function TurnActions({
  text,
  onRegenerate,
}: {
  text: string;
  onRegenerate: (() => void) | null;
}) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => setCopied(false));
  }, [text]);

  return (
    <div className="-my-1 flex gap-0.5">
      <ActionButton title={copied ? "Copied" : "Copy"} onClick={copy} active={copied}>
        {copied ? <Check size={13} strokeWidth={1.7} /> : <Copy size={13} strokeWidth={1.7} />}
      </ActionButton>
      {onRegenerate && (
        <ActionButton title="Regenerate" onClick={onRegenerate}>
          <RefreshCw size={13} strokeWidth={1.7} />
        </ActionButton>
      )}
      <ActionButton title="Read aloud — soon" disabled>
        <Volume2 size={13} strokeWidth={1.7} />
      </ActionButton>
    </div>
  );
}

function ActionButton({
  title,
  onClick,
  active = false,
  disabled = false,
  children,
}: {
  title: string;
  onClick?: () => void;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className="grid size-7 cursor-pointer place-items-center rounded-[9px] border-none bg-transparent transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)] disabled:cursor-default disabled:opacity-45 disabled:hover:bg-transparent"
      style={{ color: active ? "var(--e1)" : "var(--ml-faint)" }}
    >
      {children}
    </button>
  );
}
