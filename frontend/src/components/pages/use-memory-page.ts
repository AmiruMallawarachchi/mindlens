"use client";

import { useCallback, useEffect, useState } from "react";
import {
  addMemoryNote,
  deleteMemoryEntry,
  deleteMemoryNote,
  fetchMemory,
  updateMemoryPeople,
  updateMemoryPreferences,
} from "@/lib/api";
import type { MemoryDoc } from "@/lib/types";

export function useMemoryPage() {
  const [memory, setMemory] = useState<MemoryDoc | null | "missing">(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [editingPerson, setEditingPerson] = useState<string | null>(null);
  const [editRole, setEditRole] = useState("");
  const [editContext, setEditContext] = useState("");
  const [armedKey, setArmedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchMemory().then(setMemory).catch(() => setMemory("missing"));
  }, []);
  useEffect(() => load(), [load]);

  const activeMemory = memory && memory !== "missing" ? memory : null;
  const people = Object.entries(activeMemory?.people ?? {});
  const triggerTopics = activeMemory?.emotional_patterns?.trigger_topics ?? [];
  const effectiveCoping = activeMemory?.emotional_patterns?.effective_coping ?? [];
  const notes = activeMemory?.raw_notes ?? [];

  const confirmThenRun = async (key: string, action: () => Promise<unknown>) => {
    if (armedKey !== key) {
      setArmedKey(key);
      return;
    }
    setArmedKey(null);
    setError(null);
    try {
      await action();
      load();
    } catch {
      setError("Couldn't forget that ? try again.");
    }
  };

  const forgetPerson = (name: string) =>
    confirmThenRun(`people:${name}`, () => deleteMemoryEntry("people", name));

  const savePersonEdit = async (name: string) => {
    if (!activeMemory) return;
    const current = activeMemory.people[name];
    const updated = {
      ...activeMemory.people,
      [name]: { role: editRole, context: editContext, sentiment: current?.sentiment ?? "positive" },
    };
    setError(null);
    try {
      await updateMemoryPeople(updated);
      setEditingPerson(null);
      load();
    } catch {
      setError("Couldn't save that ? try again.");
    }
  };

  const removeListItem = (
    section: "trigger_topics" | "effective_coping",
    value: string,
  ) => confirmThenRun(`${section}:${value}`, () => deleteMemoryEntry(section, value));

  const addNote = async () => {
    const text = noteDraft.trim();
    if (!text) return;
    setSavingNote(true);
    setError(null);
    try {
      await addMemoryNote(text);
      setNoteDraft("");
      load();
    } catch {
      setError("Couldn't save that note ? try again.");
    } finally {
      setSavingNote(false);
    }
  };

  const forgetNote = (noteId: string) =>
    confirmThenRun(`notes:${noteId}`, () => deleteMemoryNote(noteId));
  const introvertScore = activeMemory?.preferences?.introvert_score;
  const forgetSocialRead = () =>
    confirmThenRun("introvert_score", () => updateMemoryPreferences({ introvert_score: null }));

  return {
    memory, noteDraft, setNoteDraft, savingNote, editingPerson, setEditingPerson,
    editRole, setEditRole, editContext, setEditContext, armedKey, setArmedKey,
    error, people, triggerTopics, effectiveCoping, notes, forgetPerson,
    savePersonEdit, removeListItem, addNote, forgetNote, introvertScore,
    forgetSocialRead,
  };
}
