"use client";

/**
 * Journal — design.md §4.2: prompt hero ("A prompt for today" + Start
 * writing), recent-entries grid, new entry composer. Backed by the real
 * journal CRUD + daily-prompt endpoints.
 */

import { useEffect, useState } from "react";
import { PenLine, X } from "lucide-react";
import {
  createJournalEntry,
  fetchJournalPrompt,
  listJournalEntries,
} from "@/lib/api";
import type { JournalEntrySummary, JournalPrompt } from "@/lib/types";

export function JournalPage() {
  const [prompt, setPrompt] = useState<JournalPrompt | null>(null);
  const [entries, setEntries] = useState<JournalEntrySummary[] | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    Promise.all([fetchJournalPrompt(), listJournalEntries(30)])
      .then(([promptData, entryData]) => {
        setPrompt(promptData);
        setEntries(entryData);
      })
      .catch(() => setError("Couldn't load your journal right now."));
  };

  useEffect(load, []);

  const openComposer = (usePrompt = false) => {
    setDraftText("");
    setDraftTitle("");
    setComposerOpen(true);
    if (usePrompt && prompt) setDraftTitle("");
  };

  const save = async () => {
    const text = draftText.trim();
    if (!text) return;
    setSaving(true);
    try {
      await createJournalEntry({
        title: draftTitle.trim() || undefined,
        text,
        prompt_used: prompt?.prompt,
      });
      setComposerOpen(false);
      load();
    } catch {
      setError("Couldn't save that entry — try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-9">
      <section
        className="rounded-[var(--r-22)] p-7"
        style={{
          background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 14%, transparent), transparent)",
          border: "1px solid var(--ml-hairline)",
        }}
      >
        <p className="ml-eyebrow mb-2">A prompt for today</p>
        <p className="ml-display mb-5 text-[22px] leading-[1.5]" style={{ color: "var(--ml-ink)", textWrap: "pretty" }}>
          {prompt?.prompt ?? "…"}
        </p>
        <button
          type="button"
          onClick={() => openComposer(true)}
          className="inline-flex items-center gap-2 rounded-[99px] px-5 py-2.5 text-[13px] font-medium"
          style={{
            background: "linear-gradient(135deg, var(--e1), var(--e2))",
            color: "#fffdf8",
            boxShadow: "var(--ml-shadow-soft)",
          }}
        >
          <PenLine size={14} strokeWidth={1.8} />
          Start writing
        </button>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <p className="ml-eyebrow">Recent entries</p>
          <button
            type="button"
            onClick={() => openComposer(false)}
            className="text-[12px] font-medium"
            style={{ color: "var(--e1)" }}
          >
            + New entry
          </button>
        </div>

        {error ? (
          <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{error}</p>
        ) : entries === null ? (
          <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
        ) : entries.length === 0 ? (
          <div
            className="rounded-[var(--r-18)] p-6 text-center"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <p className="text-[13.5px]" style={{ color: "var(--ml-muted)" }}>
              Nothing written yet — your first entry will appear here.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            {entries.map((entry) => (
              <div
                key={entry.entry_id}
                className="flex flex-col gap-2 rounded-[var(--r-16)] p-4"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
              >
                <span className="ml-num text-[10.5px]" style={{ color: "var(--ml-faint)" }}>
                  {new Date(entry.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </span>
                {entry.title && (
                  <p className="ml-display text-[16px]" style={{ color: "var(--ml-ink)" }}>{entry.title}</p>
                )}
                <p className="text-[12.5px] leading-[1.55]" style={{ color: "var(--ml-muted)" }}>
                  {entry.excerpt}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      {composerOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div
            className="ml-glass w-full max-w-[560px] rounded-[var(--r-22)] p-6"
            style={{ background: "var(--ml-panel-legible)" }}
          >
            <div className="mb-4 flex items-center justify-between">
              <p className="ml-eyebrow">New entry</p>
              <button type="button" onClick={() => setComposerOpen(false)} aria-label="Close" style={{ color: "var(--ml-faint)" }}>
                <X size={16} strokeWidth={1.8} />
              </button>
            </div>
            <input
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              placeholder="Title (optional)"
              className="mb-3 w-full bg-transparent text-[15px] outline-none"
              style={{ color: "var(--ml-ink)", borderBottom: "1px solid var(--ml-hairline)", paddingBottom: 8 }}
            />
            <textarea
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              placeholder={prompt?.prompt ?? "Write whatever comes out…"}
              rows={8}
              autoFocus
              className="w-full resize-none bg-transparent text-[14.5px] leading-[1.6] outline-none"
              style={{ color: "var(--ml-ink)" }}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setComposerOpen(false)}
                className="rounded-[99px] px-4 py-2 text-[12.5px]"
                style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-muted)" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={save}
                disabled={saving || !draftText.trim()}
                className="rounded-[99px] px-4 py-2 text-[12.5px] font-medium disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
              >
                {saving ? "Saving…" : "Save entry"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
