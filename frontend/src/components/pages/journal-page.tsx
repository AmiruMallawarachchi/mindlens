"use client";

/**
 * Journal — design.md §4.2: prompt hero ("A prompt for today" + Start
 * writing), recent-entries grid, new entry composer. Backed by the real
 * journal CRUD + daily-prompt endpoints.
 *
 * Entries are openable, editable and deletable — updateJournalEntry and
 * deleteJournalEntry already existed in lib/api.ts with nothing in the UI
 * calling them, which meant a user's own writing could go in but never come
 * back out. The composer now serves both "new" and "edit" through the same
 * form, keyed on `editingId`.
 *
 * `client.pendingJournalPrompt` arrives from the chat sidebar's "Save to
 * Journal" action — a reflection prompt referencing that conversation, not
 * the transcript itself. The user still writes their own words; this just
 * opens the composer already pointed at what to reflect on.
 */

import { useEffect, useState } from "react";
import { BookOpenText, PenLine, Trash2, X } from "lucide-react";
import {
  createJournalEntry,
  deleteJournalEntry,
  fetchJournalPrompt,
  getJournalEntry,
  listJournalEntries,
  updateJournalEntry,
} from "@/lib/api";
import type { JournalEntrySummary, JournalPrompt } from "@/lib/types";
import type { MindLensClient } from "@/lib/use-mindlens-client";

export function JournalPage({ client }: { client?: MindLensClient }) {
  const [prompt, setPrompt] = useState<JournalPrompt | null>(null);
  const [entries, setEntries] = useState<JournalEntrySummary[] | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [reflectionPrompt, setReflectionPrompt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composerError, setComposerError] = useState<string | null>(null);

  const load = () => {
    Promise.all([fetchJournalPrompt(), listJournalEntries(30)])
      .then(([promptData, entryData]) => {
        setPrompt(promptData);
        setEntries(entryData);
      })
      .catch(() => setError("Couldn't load your journal right now."));
  };

  useEffect(load, []);

  const openNewEntry = (overridePrompt?: string) => {
    setEditingId(null);
    setDraftText("");
    setDraftTitle("");
    setReflectionPrompt(overridePrompt ?? null);
    setDeleteArmed(false);
    setComposerError(null);
    setComposerOpen(true);
  };

  // Opens the composer the moment the sidebar sets a pending prompt, then
  // clears it — a one-shot trigger, not something that reopens on its own
  // if the user navigates back to Journal later.
  useEffect(() => {
    if (!client?.pendingJournalPrompt) return;
    openNewEntry(client.pendingJournalPrompt);
    client.clearJournalPrompt();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client?.pendingJournalPrompt]);

  const openExistingEntry = async (entryId: string) => {
    setEditingId(entryId);
    setDraftText("");
    setDraftTitle("");
    setReflectionPrompt(null);
    setDeleteArmed(false);
    setComposerError(null);
    setComposerOpen(true);
    try {
      const full = await getJournalEntry(entryId);
      setDraftTitle(full.title ?? "");
      setDraftText(full.text);
    } catch {
      setComposerError("Couldn't load that entry.");
    }
  };

  const closeComposer = () => {
    setComposerOpen(false);
    setDeleteArmed(false);
  };

  const save = async () => {
    const text = draftText.trim();
    if (!text) return;
    setSaving(true);
    setComposerError(null);
    try {
      if (editingId) {
        await updateJournalEntry(editingId, { title: draftTitle.trim() || null, text });
      } else {
        await createJournalEntry({
          title: draftTitle.trim() || undefined,
          text,
          prompt_used: reflectionPrompt ?? prompt?.prompt,
        });
      }
      closeComposer();
      load();
    } catch {
      setComposerError("Couldn't save that entry — try again.");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!editingId) return;
    if (!deleteArmed) {
      setDeleteArmed(true);
      return;
    }
    setDeleting(true);
    setComposerError(null);
    try {
      await deleteJournalEntry(editingId);
      closeComposer();
      load();
    } catch {
      setComposerError("Couldn't delete that entry — try again.");
    } finally {
      setDeleting(false);
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
        <div
          className="mb-3.5 grid size-[46px] place-items-center rounded-[14px]"
          style={{ background: "color-mix(in oklab, var(--e1) 18%, transparent)", color: "var(--e1)" }}
        >
          <BookOpenText size={20} strokeWidth={1.7} />
        </div>
        <p className="ml-eyebrow mb-2">A prompt for today</p>
        <p className="ml-display mb-2 text-[22px] leading-[1.5]" style={{ color: "var(--ml-ink)", textWrap: "pretty" }}>
          {prompt?.prompt ?? "…"}
        </p>
        <p className="mb-5 text-[12.5px]" style={{ color: "var(--ml-muted)" }}>
          Take two minutes. You don&rsquo;t need to make it sound good.
        </p>
        <button
          type="button"
          onClick={() => openNewEntry()}
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
            onClick={() => openNewEntry()}
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
              <button
                key={entry.entry_id}
                type="button"
                onClick={() => openExistingEntry(entry.entry_id)}
                className="flex flex-col gap-2 rounded-[var(--r-16)] p-4 text-left transition-colors hover:border-[var(--ml-hairline-strong)]"
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
              </button>
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
              <p className="ml-eyebrow">{editingId ? "Edit entry" : "New entry"}</p>
              <button type="button" onClick={closeComposer} aria-label="Close" style={{ color: "var(--ml-faint)" }}>
                <X size={16} strokeWidth={1.8} />
              </button>
            </div>
            {reflectionPrompt && (
              <p
                className="mb-3 rounded-[var(--r-11)] px-3 py-2 text-[12.5px] leading-[1.5]"
                style={{ background: "color-mix(in oklab, var(--e1) 10%, transparent)", color: "var(--ml-muted)" }}
              >
                {reflectionPrompt}
              </p>
            )}
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
              placeholder={reflectionPrompt ?? prompt?.prompt ?? "Write whatever comes out…"}
              rows={8}
              autoFocus
              className="w-full resize-none bg-transparent text-[14.5px] leading-[1.6] outline-none"
              style={{ color: "var(--ml-ink)" }}
            />
            {composerError && (
              <p className="mt-2 text-[12px]" style={{ color: "#e08a8a" }}>{composerError}</p>
            )}
            <div className="mt-4 flex items-center justify-between gap-2">
              {editingId ? (
                <button
                  type="button"
                  onClick={confirmDelete}
                  onBlur={() => setDeleteArmed(false)}
                  disabled={deleting}
                  className="inline-flex items-center gap-1.5 rounded-[99px] px-3 py-2 text-[12px] font-medium disabled:opacity-50"
                  style={{
                    color: "#e08a8a",
                    border: deleteArmed ? "1px solid #e08a8a" : "1px solid transparent",
                  }}
                >
                  <Trash2 size={13} strokeWidth={1.8} />
                  {deleteArmed ? "Click to confirm delete" : "Delete entry"}
                </button>
              ) : (
                <span />
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={closeComposer}
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
        </div>
      )}
    </div>
  );
}
