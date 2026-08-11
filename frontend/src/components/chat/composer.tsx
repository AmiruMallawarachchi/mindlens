"use client";

/**
 * The composer — ported from "Mindlens Design System.html" (design project
 * "Mindlens: Emotional AI Companion"), which supersedes the older board this
 * was first built from. The differences that mattered, all now matched: a
 * plain 22px panel rather than glass with a 4px emotion halo, no rule between
 * the text row and the toolbar, paperclip + mic + send and nothing else, and
 * a solid-ink 36px send button rather than an e1 → e2 gradient.
 *
 * Built on AI Elements' <PromptInput>, which supplies Enter-to-send,
 * Shift+Enter for a newline and the form plumbing.
 *
 * Attach and mic are rendered disabled, same reasoning as message-flow.tsx's
 * "Read aloud" action: there's no file-upload or speech-to-text backend
 * behind either yet, and a live-looking button that does nothing is the thing
 * this codebase explicitly guards against. They're declared-future controls,
 * so they stay visible and disabled rather than hidden.
 *
 * The disclaimer below it is not optional chrome — §4.1 requires it under the
 * composer on every turn, alongside a way to reach a human.
 */

import { ArrowUp, Mic, Paperclip } from "lucide-react";
import {
  PromptInput,
  PromptInputBody,
  PromptInputTextarea,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import type { ConnectionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Starter suggestions from the mockup — shown only on an empty
 * conversation, where "what do I even say" is a real barrier. Once turns
 * exist they disappear; the backend has no per-turn suggestion output yet. */
const STARTER_SUGGESTIONS = [
  "I just want to vent for a minute",
  "Help me untangle something",
  "Why do I keep freezing like this?",
  "What did we work on last time?",
];

export function Composer({
  onSend,
  onTypingChange,
  connectionStatus,
  disabled = false,
  preview = false,
  showSuggestions = false,
}: {
  onSend: (text: string) => void;
  onTypingChange?: (typing: boolean) => void;
  connectionStatus: ConnectionStatus;
  disabled?: boolean;
  /** Preview mode has no backend at all, so "reconnecting" would be a lie. */
  preview?: boolean;
  showSuggestions?: boolean;
}) {
  const offline = connectionStatus !== "open";
  const blocked = disabled || offline;

  const placeholder = preview
    ? "Preview mode — start the backend to talk to Mindlens"
    : offline
      ? "Reconnecting to Mindlens…"
      : "Say it however it comes out…";

  const handleSubmit = (message: PromptInputMessage) => {
    const text = message.text?.trim();
    if (!text || blocked) return;
    onSend(text);
    onTypingChange?.(false);
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="mx-auto w-full max-w-[760px]">
        {showSuggestions && !blocked && (
          <div
            className="flex gap-2 overflow-x-auto px-0.5 pb-2.5"
            style={{
              maskImage: "linear-gradient(90deg, #000 88%, transparent)",
              WebkitMaskImage: "linear-gradient(90deg, #000 88%, transparent)",
            }}
          >
            {STARTER_SUGGESTIONS.map((text) => (
              <button
                key={text}
                type="button"
                onClick={() => onSend(text)}
                className="shrink-0 cursor-pointer whitespace-nowrap rounded-[99px] border px-[14px] py-2 text-[12px] transition-colors hover:border-[var(--ml-ink)]"
                style={{
                  borderColor: "var(--ml-hairline-strong)",
                  background: "var(--ml-panel)",
                  color: "var(--ml-ink)",
                }}
              >
                {text}
              </button>
            ))}
          </div>
        )}
        <PromptInput
          onSubmit={handleSubmit}
          className={cn("overflow-hidden rounded-[var(--r-22)] border", blocked && "opacity-70")}
          style={{
            borderColor: "var(--ml-hairline-strong)",
            background: "var(--ml-panel-legible)",
            boxShadow: blocked ? "none" : "var(--ml-shadow-neutral)",
          }}
        >
          <PromptInputBody>
            <PromptInputTextarea
              placeholder={placeholder}
              onChange={(event) =>
                onTypingChange?.(event.currentTarget.value.length > 0)
              }
              className="min-h-[46px] bg-transparent px-[18px] pb-1 pt-[15px] text-[14px] leading-[1.55] placeholder:opacity-45"
              style={{ color: "var(--ml-ink)" }}
            />
          </PromptInputBody>

          {/* `data-align="block-end"` is load-bearing, not decoration: the
            * underlying <InputGroup> is `flex items-center` (a row) and only
            * switches to `flex-col` via its own
            * `has-[>[data-align=block-end]]:flex-col` selector. Without this
            * attribute the textarea and this toolbar sit side by side in one
            * squashed row instead of stacking, which is exactly how it
            * rendered before. `w-full` is needed for the same reason — the
            * parent's `items-center` centres (not stretches) children once
            * it's a column. */}
          <div data-align="block-end" className="flex w-full items-center gap-2 px-3 pb-3 pt-2">
            <ComposerIconButton title="Attach a file — soon" disabled>
              <Paperclip size={16} strokeWidth={1.7} />
            </ComposerIconButton>
            <ComposerIconButton title="Voice input — soon" disabled>
              <Mic size={16} strokeWidth={1.7} />
            </ComposerIconButton>

            <button
              type="submit"
              disabled={blocked}
              aria-label="Send message"
              className="ml-auto inline-flex size-9 shrink-0 items-center justify-center rounded-[12px] transition-transform hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
              style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
            >
              <ArrowUp size={16} strokeWidth={2.2} />
            </button>
          </div>
        </PromptInput>

        {/* Typing is never blocked (see PromptInputTextarea above), only
          * sending is — so the reason has to live here, next to the greyed
          * send button, not in the placeholder alone. */}
        {blocked && (
          <p
            className="mt-2 text-center text-[11px] leading-[1.5]"
            style={{ color: "var(--ml-faint)" }}
          >
            {preview
              ? "Preview mode has no backend — nothing you type here can send."
              : "Not connected — keep typing, it'll send once Mindlens is back."}
          </p>
        )}

        {/* §4.1 — always present, never behind a disclosure. */}
        <p
          className="mt-3 text-center text-[11px] leading-[1.6]"
          style={{ color: "var(--ml-faint)" }}
        >
          Mindlens is a wellbeing companion — not emergency or medical care.{" "}
          <a
            href="https://findahelpline.com"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2 transition-colors hover:text-[var(--ml-muted)]"
          >
            Reach a human
          </a>
        </p>
      </div>
    </div>
  );
}

function ComposerIconButton({
  title,
  disabled,
  children,
}: {
  title: string;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      className="grid size-8 shrink-0 place-items-center rounded-[10px] transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)] disabled:cursor-default disabled:opacity-45 disabled:hover:bg-transparent"
      style={{ color: "var(--ml-muted)" }}
    >
      {children}
    </button>
  );
}
