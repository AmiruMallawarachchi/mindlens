"use client";

import { useCallback, useState } from "react";
import { BookOpen, Check, Copy, RefreshCw, Square, Volume2 } from "lucide-react";
import { createJournalEntry } from "@/lib/api";
import { useReadAloud } from "@/lib/use-read-aloud";
import type { ChatMessage } from "@/lib/types";
/**
 * Actions row from the mockup: Copy Â· save-to-journal Â· Regenerate Â· Read
 * aloud. Regenerate resends the previous user message â€” only offered on the
 * last assistant turn, where "try that again" has a well-defined meaning.
 * Save-to-journal uses the same journal CRUD the Journal page already calls
 * (lib/api.ts's createJournalEntry) â€” this was the one action Â§4.1 lists
 * that had no button anywhere.
 *
 * Read aloud was the mockup's declared-future control and rendered disabled
 * for exactly as long as there was nothing behind it. It now really speaks,
 * via SpeechSynthesis (see use-read-aloud.ts for why this needs no privacy
 * disclosure where the mic did), and is not rendered at all in a browser
 * without the API rather than rendered dead.
 */
export function TurnActions({
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
    saved === "done" ? "Saved to journal" : saved === "error" ? "Couldn't save â€” try again" : "Save to journal";

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
 * They are a shortcut for typing, never a constraint on what may be said â€”
 * so the free-text escape is always present and the composer stays fully
 * usable while they are on screen. Choosing one sends it as an ordinary
 * message, which is also the only inbound frame the backend accepts.
 */
export function OptionChoices({
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
          Or say it your own way below â€” these are just shortcuts.
        </p>
      )}
    </div>
  );
}

