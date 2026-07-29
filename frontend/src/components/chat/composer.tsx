"use client";

/**
 * The composer — design.md §4.1.
 *
 * Built on AI Elements' <PromptInput>, which supplies Enter-to-send,
 * Shift+Enter for a newline and the form plumbing. Restyled onto the emotion
 * tokens: glass, a 4px halo ring, and a send button that runs e1 → e2.
 *
 * The disclaimer below it is not optional chrome — §4.1 requires it under the
 * composer on every turn, alongside a way to reach a human.
 */

import { ArrowUp } from "lucide-react";
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
                className="shrink-0 cursor-pointer whitespace-nowrap rounded-[99px] border px-[15px] py-2 text-[12px] transition-colors hover:text-[var(--ml-ink)]"
                style={{
                  borderColor: "var(--ml-hairline-strong)",
                  background: "var(--ml-panel)",
                  color: "var(--ml-muted)",
                }}
              >
                {text}
              </button>
            ))}
          </div>
        )}
        <PromptInput
          onSubmit={handleSubmit}
          className={cn(
            "ml-glass overflow-hidden rounded-[var(--r-24)] transition-shadow duration-700",
            blocked && "opacity-70",
          )}
          style={{
            // The 4px emotion halo.
            boxShadow: blocked
              ? "none"
              : "0 0 0 4px color-mix(in oklab, var(--e1) 16%, transparent), var(--ml-shadow-soft)",
          }}
        >
          <PromptInputBody>
            <PromptInputTextarea
              placeholder={placeholder}
              disabled={blocked}
              onChange={(event) =>
                onTypingChange?.(event.currentTarget.value.length > 0)
              }
              className="min-h-[58px] bg-transparent px-5 pt-4 text-[15px] leading-[1.55] placeholder:opacity-45"
              style={{ color: "var(--ml-ink)" }}
            />
          </PromptInputBody>

          <div className="flex items-center gap-2 px-3 pb-3 pt-1">
            {/* Mindlens chooses the approach per turn rather than exposing a
             * picker — this chip states that, it isn't a disabled menu. */}
            <span
              className="rounded-[var(--r-pill)] border px-2.5 py-1 text-[11px]"
              style={{
                borderColor: "var(--ml-hairline)",
                color: "var(--ml-muted)",
              }}
            >
              Adaptive
            </span>
            <span
              className="rounded-[var(--r-pill)] border px-2.5 py-1 text-[11px]"
              style={{
                borderColor: "var(--ml-hairline)",
                color: "var(--ml-faint)",
              }}
            >
              Voice · soon
            </span>

            <span className="ml-auto ml-eyebrow hidden sm:inline">
              ⏎ to send
            </span>

            <button
              type="submit"
              disabled={blocked}
              aria-label="Send message"
              className="inline-flex size-10 items-center justify-center rounded-full transition-transform hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
              style={{
                background: "linear-gradient(135deg, var(--e1), var(--e2))",
                color: "#0a0b11",
                boxShadow: blocked ? "none" : "var(--ml-shadow-soft)",
              }}
            >
              <ArrowUp size={18} strokeWidth={2} />
            </button>
          </div>
        </PromptInput>

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
