"use client";

import { useCallback, useEffect, useState } from "react";
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

export function useJournalPage(client?: MindLensClient) {
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

  const load = useCallback(() => {
    Promise.all([fetchJournalPrompt(), listJournalEntries(30)])
      .then(([promptData, entryData]) => {
        setPrompt(promptData);
        setEntries(entryData);
      })
      .catch(() => setError("Couldn't load your journal right now."));
  }, []);

  useEffect(() => load(), [load]);

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


  return {
    prompt, entries, composerOpen, editingId, draftText, setDraftText,
    draftTitle, setDraftTitle, reflectionPrompt, saving, deleteArmed, setDeleteArmed, deleting,
    error, composerError, openNewEntry, openExistingEntry, closeComposer,
    save, confirmDelete,
  };
}
