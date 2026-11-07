"use client";

/**
 * The composer — one compact bar: your words, a mic, a send button.
 *
 * Built on AI Elements' <PromptInput>, which supplies Enter-to-send,
 * Shift+Enter for a newline and the form plumbing. The textarea is controlled
 * here rather than left to the form, because dictation has to append into it;
 * <PromptInput> calls form.reset() after submit, so handleSubmit clears the
 * draft to keep DOM and state agreeing.
 *
 * Two controls were removed rather than left sitting there disabled:
 *
 * - The paperclip. There is no upload endpoint and every agent is text-only,
 *   so an attached file had nowhere to go and nothing to read it. A control
 *   that cannot work is worse than an absent one (CLAUDE.md rule 1).
 * - The mic's "soon" state. It now genuinely dictates, via the browser's
 *   Web Speech API — but that ships audio to the browser vendor's servers
 *   (Google, in Chrome), which sits badly against "everything here stays
 *   yours". So it says so, once, before the first use, and the button is not
 *   rendered at all where the API is missing rather than rendered dead.
 */

import { ArrowUp, Mic, Square } from "lucide-react";
import {
  PromptInput,
  PromptInputBody,
  PromptInputTextarea,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import type { ConnectionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useComposerDictation } from "./use-composer-dictation";

export function Composer({
  onSend,
  onTypingChange,
  connectionStatus,
  disabled = false,
  preview = false,
}: {
  onSend: (text: string) => void;
  onTypingChange?: (typing: boolean) => void;
  connectionStatus: ConnectionStatus;
  disabled?: boolean;
  /** Preview mode has no backend at all, so "reconnecting" would be a lie. */
  preview?: boolean;
}) {
  const offline = connectionStatus !== "open";
  const blocked = disabled || offline;

  const {
    draft,
    setDraft,
    listening,
    voiceSupported,
    showVoiceNotice,
    setShowVoiceNotice,
    voiceError,
    handleMicClick,
    acceptVoiceNotice,
    stopDictation,
  } = useComposerDictation(onTypingChange);

  const placeholder = preview
    ? "Preview mode — start the backend to talk to MindLens"
    : offline
      ? "Reconnecting to MindLens…"
      : listening
        ? "Listening…"
        : "Say it however it comes out…";

  const handleSubmit = (message: PromptInputMessage) => {
    const text = (message.text ?? draft).trim();
    if (!text || blocked) return;
    if (listening) stopDictation();
    onSend(text);
    setDraft("");
    onTypingChange?.(false);
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="mx-auto w-full max-w-[680px]">
        {showVoiceNotice && (
          <div
            className="mb-2.5 rounded-[var(--r-14)] border p-3.5"
            style={{
              borderColor: "var(--ml-hairline-strong)",
              background: "var(--ml-panel)",
            }}
          >
            <p className="m-0 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-ink)" }}>
              Dictation is done by your browser, not by MindLens — which means
              your voice is sent to your browser&rsquo;s speech provider
              (Google, in Chrome) to be turned into text. The words that come
              back are treated like anything else you type. If a thought is one
              you&rsquo;d rather not send anywhere, type it instead.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={acceptVoiceNotice}
                className="rounded-[10px] px-3 py-1.5 text-[12px] transition-opacity hover:opacity-85"
                style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
              >
                Start dictating
              </button>
              <button
                type="button"
                onClick={() => setShowVoiceNotice(false)}
                className="rounded-[10px] border px-3 py-1.5 text-[12px] transition-colors hover:border-[var(--ml-ink)]"
                style={{
                  borderColor: "var(--ml-hairline-strong)",
                  color: "var(--ml-muted)",
                }}
              >
                Not now
              </button>
            </div>
          </div>
        )}

        <PromptInput
          onSubmit={handleSubmit}
          className={cn("rounded-[16px] border", blocked && "opacity-70")}
          style={{
            borderColor: "var(--ml-hairline-strong)",
            background: "var(--ml-panel-legible)",
            boxShadow: blocked
              ? "none"
              : "0 1px 2px rgba(10,11,17,.04), 0 16px 32px -24px rgba(10,11,17,.4)",
          }}
        >
          <PromptInputBody>
            <PromptInputTextarea
              value={draft}
              placeholder={placeholder}
              onChange={(event) => {
                setDraft(event.currentTarget.value);
                onTypingChange?.(event.currentTarget.value.length > 0);
              }}
              className="min-h-[44px] max-h-[160px] bg-transparent py-[11px] pl-4 pr-1 text-[14.5px] leading-[1.5] placeholder:opacity-45"
              style={{ color: "var(--ml-ink)" }}
            />
          </PromptInputBody>

          {/* A direct child of the input group, which is `flex items-center`
            * until an addon claims `data-align="block-end"`. Staying in the
            * row — `order-last` plus `self-end` — is what keeps this one bar
            * instead of a textarea with a separate toolbar strip beneath it,
            * and pins the two buttons to the bottom edge as the textarea
            * grows. */}
          <div
            data-align="inline-end"
            className="order-last flex shrink-0 items-center gap-1 self-end px-2 pb-2"
          >
            {/* Rendered only where the API exists — a browser without it gets
              * no button rather than a dead one. */}
            {voiceSupported && (
              <ComposerIconButton
                title={listening ? "Stop dictating" : "Dictate a message"}
                onClick={handleMicClick}
                active={listening}
              >
                {listening ? (
                  <Square size={13} strokeWidth={2.2} fill="currentColor" />
                ) : (
                  <Mic size={15} strokeWidth={1.7} />
                )}
              </ComposerIconButton>
            )}

            <button
              type="submit"
              disabled={blocked}
              aria-label="Send message"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-full transition-transform hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:scale-100"
              style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
            >
              <ArrowUp size={15} strokeWidth={2.4} />
            </button>
          </div>
        </PromptInput>

        {voiceError && (
          <p
            className="mt-2 text-center text-[11px] leading-[1.5]"
            style={{ color: "var(--ml-faint)" }}
            role="status"
          >
            {voiceError}
          </p>
        )}

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
              : "Not connected — keep typing, it'll send once MindLens is back."}
          </p>
        )}

        {/* §4.1 requires this to be always present, never behind a
          * disclosure. Its home is now the sidebar — but below 780px the
          * sidebar is a drawer behind a hamburger, so at those widths it
          * would be exactly the disclosure §4.1 forbids. Hence this copy,
          * shown only where the sidebar isn't. */}
        <p
          className="mt-3 text-center text-[11px] leading-[1.6] min-[780px]:hidden"
          style={{ color: "var(--ml-faint)" }}
        >
          MindLens is a wellbeing companion — not emergency or medical care.{" "}
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
  onClick,
  active = false,
  children,
}: {
  title: string;
  disabled?: boolean;
  onClick?: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className="grid size-8 shrink-0 place-items-center rounded-[10px] transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)] disabled:cursor-default disabled:opacity-45 disabled:hover:bg-transparent"
      style={{
        color: active ? "var(--ml-canvas)" : "var(--ml-muted)",
        background: active ? "var(--e1)" : undefined,
      }}
    >
      {children}
    </button>
  );
}
