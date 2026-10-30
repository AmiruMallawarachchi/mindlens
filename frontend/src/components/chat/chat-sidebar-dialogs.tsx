"use client";

import { useRef, useState } from "react";
import type { SessionListItem } from "@/lib/types";
import { sessionLabel } from "./chat-sidebar-utils";

/**
 * In-place rename field for one session row.
 *
 * Uncontrolled on purpose: the value only matters at commit, and letting the
 * parent own it would re-render the whole session list on every keystroke.
 * Enter and blur commit, Escape abandons — and the Escape path sets a flag
 * the blur handler checks, because cancelling also blurs and would otherwise
 * immediately re-commit the text the user just rejected.
 */
export function SessionTitleInput({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string;
  onCommit: (title: string) => void;
  onCancel: () => void;
}) {
  const cancelled = useRef(false);

  return (
    <input
      autoFocus
      defaultValue={initial}
      maxLength={200}
      aria-label="Rename conversation"
      onFocus={(event) => event.currentTarget.select()}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onCommit(event.currentTarget.value.trim());
        } else if (event.key === "Escape") {
          event.preventDefault();
          cancelled.current = true;
          onCancel();
        }
      }}
      onBlur={(event) => {
        if (cancelled.current) return;
        onCommit(event.currentTarget.value.trim());
      }}
      className="w-full rounded-[var(--r-11)] border px-3 py-2 text-[12.5px] outline-none"
      style={{
        background: "var(--ml-panel-legible)",
        borderColor: "var(--e1)",
        color: "var(--ml-ink)",
      }}
    />
  );
}

/**
 * Typed confirmation for deleting a conversation.
 *
 * Delete used to set a status flag and keep everything, so a second click
 * was proportionate friction. It is a real hard delete now — the transcript,
 * the emotion reads and the crisis records are all removed and cannot be
 * recovered — and UI rule 4 asks for a typed confirmation at that point.
 *
 * The escape is as easy to reach as the confirm: Cancel is focused first,
 * Escape closes, and the confirm stays disabled until the word matches.
 */
export function DeleteSessionDialog({
  session,
  onCancel,
  onConfirm,
}: {
  session: SessionListItem;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const armed = typed.trim().toLowerCase() === "delete";

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-session-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
      }}
    >
      <button
        type="button"
        aria-label="Cancel deleting this conversation"
        onClick={onCancel}
        className="absolute inset-0 cursor-default border-none bg-black/45"
      />
      <div
        className="relative w-full max-w-[380px] rounded-[var(--r-18)] border p-5"
        style={{
          background: "var(--ml-panel-legible)",
          borderColor: "var(--ml-hairline-strong)",
        }}
      >
        <p
          id="delete-session-title"
          className="ml-display m-0 text-[17px] leading-[1.45]"
          style={{ color: "var(--ml-ink)" }}
        >
          Delete &ldquo;{sessionLabel(session)}&rdquo;?
        </p>
        <p className="mt-2 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
          This removes the whole conversation, the emotion reads taken during
          it, and any safety records from it. It cannot be undone and there is
          no copy kept.
        </p>
        <label
          className="mt-3.5 block text-[11.5px]"
          style={{ color: "var(--ml-faint)" }}
          htmlFor="delete-confirm-input"
        >
          Type <strong style={{ color: "var(--ml-ink)" }}>delete</strong> to confirm
        </label>
        <input
          id="delete-confirm-input"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && armed) onConfirm();
          }}
          autoComplete="off"
          className="mt-1.5 w-full rounded-[var(--r-11)] border px-3 py-2 text-[13px] outline-none"
          style={{
            background: "var(--ml-panel)",
            borderColor: "var(--ml-hairline-strong)",
            color: "var(--ml-ink)",
          }}
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            autoFocus
            onClick={onCancel}
            className="rounded-[10px] border px-3.5 py-2 text-[12.5px] transition-colors hover:border-[var(--ml-ink)]"
            style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          >
            Keep it
          </button>
          <button
            type="button"
            disabled={!armed}
            onClick={onConfirm}
            className="rounded-[10px] px-3.5 py-2 text-[12.5px] text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: "#c2453c" }}
          >
            Delete for good
          </button>
        </div>
      </div>
    </div>
  );
}
