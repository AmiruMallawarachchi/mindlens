"use client";

/**
 * The message flow — ported from the approved mockup (Mindlens Chat.dc.html).
 *
 * User turns: right-aligned bubbles with an asymmetric 18/18/5/18 radius and
 * the emotion read strip beneath. Assistant turns: no bubble — the companion
 * blob avatar, the reasoning trail, editorial text, then a compact actions
 * row (Copy / Regenerate / Read aloud–soon) and any inline cards in a
 * two-column grid.
 */

import { useCallback, useMemo, useState } from "react";
import { BookOpen, Check, Copy, RefreshCw, Square, Volume2 } from "lucide-react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { EmotionRead } from "./emotion-read";
import { ReasoningTrail } from "./reasoning-trail";
import { PipelineTrace } from "./pipeline-trace";
import { BreatheCard } from "./breathe-card";
import { createJournalEntry } from "@/lib/api";
import { resolveEmotion } from "@/lib/emotion";
import { buildReasoningTrail, summariseTrail } from "@/lib/reasoning";
import { useReadAloud } from "@/lib/use-read-aloud";
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
  // breathe player when a breathing-adjacent agent ran, the music player
  // when the backend sent a real payload.
  const offersBreathing = useMemo(() => {
    const agents = (message.agentsUsed ?? []).map((a) => a.replace(/_agent$/, ""));
    return agents.includes("mindfulness") || agents.includes("dbt");
  }, [message.agentsUsed]);
  // Music is not rendered inline any more — the right rail is the music
  // panel and holds the newest track. Rendering it in both places showed the
  // same card twice on the turn that produced it.
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
          <ReasoningTrail steps={steps} summary={summary} isStreaming={isStreaming} />
        )}

        {/* The mechanical counterpart to the prose trail above — collapsed
          * by default, so the default reading experience is unchanged. */}
        {!isStreaming && steps.length > 0 && <PipelineTrace message={message} />}

        <p className="ml-display m-0 text-[19.5px] leading-[1.6]" style={{ color: "var(--ml-ink)", textWrap: "pretty" }}>
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

/**
 * Actions row from the mockup: Copy · save-to-journal · Regenerate · Read
 * aloud. Regenerate resends the previous user message — only offered on the
 * last assistant turn, where "try that again" has a well-defined meaning.
 * Save-to-journal uses the same journal CRUD the Journal page already calls
 * (lib/api.ts's createJournalEntry) — this was the one action §4.1 lists
 * that had no button anywhere.
 *
 * Read aloud was the mockup's declared-future control and rendered disabled
 * for exactly as long as there was nothing behind it. It now really speaks,
 * via SpeechSynthesis (see use-read-aloud.ts for why this needs no privacy
 * disclosure where the mic did), and is not rendered at all in a browser
 * without the API rather than rendered dead.
 */
function TurnActions({
  text,
  onRegenerate,
}: {
  text: string;
  onRegenerate: (() => void) | null;
}) {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState<"idle" | "saving" | "done" | "error">("idle");
  const { supported: canSpeak, speaking, toggle: toggleSpeech } = useReadAloud(text);

  const copy = useCallback(() => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => setCopied(false));
  }, [text]);

  const saveToJournal = useCallback(() => {
    if (saved === "saving" || saved === "done") return;
    setSaved("saving");
    createJournalEntry({ text })
      .then(() => setSaved("done"))
      .catch(() => {
        setSaved("error");
        setTimeout(() => setSaved("idle"), 2200);
      });
  }, [text, saved]);

  const journalTitle =
    saved === "done" ? "Saved to journal" : saved === "error" ? "Couldn't save — try again" : "Save to journal";

  return (
    <div className="-my-1 flex gap-0.5">
      <ActionButton title={copied ? "Copied" : "Copy"} onClick={copy} active={copied}>
        {copied ? <Check size={13} strokeWidth={1.7} /> : <Copy size={13} strokeWidth={1.7} />}
      </ActionButton>
      <ActionButton title={journalTitle} onClick={saveToJournal} active={saved === "done"} disabled={saved === "saving"}>
        {saved === "done" ? <Check size={13} strokeWidth={1.7} /> : <BookOpen size={13} strokeWidth={1.7} />}
      </ActionButton>
      {onRegenerate && (
        <ActionButton title="Regenerate" onClick={onRegenerate}>
          <RefreshCw size={13} strokeWidth={1.7} />
        </ActionButton>
      )}
      {canSpeak && (
        <ActionButton
          title={speaking ? "Stop reading" : "Read aloud"}
          onClick={toggleSpeech}
          active={speaking}
        >
          {speaking ? (
            <Square size={12} strokeWidth={2.2} fill="currentColor" />
          ) : (
            <Volume2 size={13} strokeWidth={1.7} />
          )}
        </ActionButton>
      )}
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

/**
 * Tappable answers under a reply that asked something.
 *
 * They are a shortcut for typing, never a constraint on what may be said —
 * so the free-text escape is always present and the composer stays fully
 * usable while they are on screen. Choosing one sends it as an ordinary
 * message, which is also the only inbound frame the backend accepts.
 */
function OptionChoices({
  payload,
  onChoose,
}: {
  payload: NonNullable<ChatMessage["options"]>;
  onChoose: (text: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5" role="group" aria-label="Suggested answers">
      {payload.options.map((option, index) => (
        <button
          key={option}
          type="button"
          onClick={() => onChoose(option)}
          className="flex w-full items-center gap-2.5 rounded-[var(--r-11)] border px-3 py-2 text-left text-[13px] transition-colors hover:border-[var(--ml-ink)]"
          style={{
            borderColor: "var(--ml-hairline-strong)",
            background: "var(--ml-panel)",
            color: "var(--ml-ink)",
          }}
        >
          <span
            aria-hidden="true"
            className="ml-eyebrow shrink-0 tabular-nums"
            style={{ opacity: 0.5 }}
          >
            {index + 1}
          </span>
          {option}
        </button>
      ))}
      {payload.allow_other && (
        <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--ml-faint)" }}>
          Or say it your own way below — these are just shortcuts.
        </p>
      )}
    </div>
  );
}
