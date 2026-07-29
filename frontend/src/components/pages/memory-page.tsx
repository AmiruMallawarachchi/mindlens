"use client";

/**
 * Memory — design.md §4.2: "You decide what Mindlens remembers". Category
 * cards backed by the real memory document, each with Forget (delete) —
 * and for people, an inline Edit. Empty states are honest: a category with
 * nothing in it says so, rather than showing placeholder content.
 */

import { useEffect, useState } from "react";
import { ShieldCheck, Trash2, X } from "lucide-react";
import {
  addMemoryNote,
  deleteMemoryEntry,
  deleteMemoryNote,
  fetchMemory,
  updateMemoryPeople,
} from "@/lib/api";
import type { MemoryDoc } from "@/lib/types";

export function MemoryPage() {
  const [memory, setMemory] = useState<MemoryDoc | null | "missing">(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [editingPerson, setEditingPerson] = useState<string | null>(null);
  const [editRole, setEditRole] = useState("");
  const [editContext, setEditContext] = useState("");

  const load = () => {
    fetchMemory()
      .then(setMemory)
      .catch(() => setMemory("missing"));
  };

  useEffect(load, []);

  if (memory === null) {
    return <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>;
  }
  if (memory === "missing") {
    return (
      <div className="rounded-[var(--r-18)] p-6" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
        <p className="text-[13.5px]" style={{ color: "var(--ml-muted)" }}>
          Your memory hasn&rsquo;t been created yet — it&rsquo;s set up automatically once you finish onboarding.
        </p>
      </div>
    );
  }

  const people = Object.entries(memory.people ?? {});
  const triggerTopics = memory.emotional_patterns?.trigger_topics ?? [];
  const effectiveCoping = memory.emotional_patterns?.effective_coping ?? [];
  const notes = memory.raw_notes ?? [];

  const forgetPerson = async (name: string) => {
    await deleteMemoryEntry("people", name);
    load();
  };

  const savePersonEdit = async (name: string) => {
    const current = memory.people[name];
    const updated = {
      ...memory.people,
      [name]: { role: editRole, context: editContext, sentiment: current?.sentiment ?? "positive" },
    };
    await updateMemoryPeople(updated);
    setEditingPerson(null);
    load();
  };

  const removeListItem = async (
    section: "trigger_topics" | "effective_coping",
    value: string,
  ) => {
    await deleteMemoryEntry(section, value);
    load();
  };

  const addNote = async () => {
    const text = noteDraft.trim();
    if (!text) return;
    setSavingNote(true);
    try {
      await addMemoryNote(text);
      setNoteDraft("");
      load();
    } finally {
      setSavingNote(false);
    }
  };

  const forgetNote = async (noteId: string) => {
    await deleteMemoryNote(noteId);
    load();
  };

  return (
    <div className="flex flex-col gap-9">
      <div>
        <p className="ml-eyebrow mb-3">You decide what Mindlens remembers</p>
        <div
          className="flex items-start gap-3 rounded-[var(--r-16)] p-4"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          <ShieldCheck size={16} strokeWidth={1.8} className="mt-0.5 shrink-0" style={{ color: "var(--e1)" }} />
          <p className="text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
            Everything here is visible and editable — nothing is remembered without appearing on this page first. This is not a diagnosis; it&rsquo;s just what you&rsquo;ve told Mindlens.
          </p>
        </div>
      </div>

      <MemoryCategory title="Important people" empty={people.length === 0} emptyText="No one on file yet.">
        {people.map(([name, info]) => (
          <div key={name} className="flex flex-col gap-2 rounded-[var(--r-13)] p-3" style={{ border: "1px solid var(--ml-hairline)" }}>
            {editingPerson === name ? (
              <div className="flex flex-col gap-2">
                <input
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  placeholder="Role"
                  className="w-full bg-transparent text-[13px] outline-none"
                  style={{ color: "var(--ml-ink)", borderBottom: "1px solid var(--ml-hairline)", paddingBottom: 4 }}
                />
                <input
                  value={editContext}
                  onChange={(e) => setEditContext(e.target.value)}
                  placeholder="Context"
                  className="w-full bg-transparent text-[13px] outline-none"
                  style={{ color: "var(--ml-ink)", borderBottom: "1px solid var(--ml-hairline)", paddingBottom: 4 }}
                />
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setEditingPerson(null)} className="text-[11.5px]" style={{ color: "var(--ml-faint)" }}>Cancel</button>
                  <button type="button" onClick={() => savePersonEdit(name)} className="text-[11.5px] font-medium" style={{ color: "var(--e1)" }}>Save</button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[13.5px] font-medium" style={{ color: "var(--ml-ink)" }}>{name}</p>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingPerson(name);
                        setEditRole(info.role);
                        setEditContext(info.context);
                      }}
                      className="text-[11.5px]"
                      style={{ color: "var(--ml-muted)" }}
                    >
                      Edit
                    </button>
                    <button type="button" onClick={() => forgetPerson(name)} className="text-[11.5px]" style={{ color: "#ff6b6b" }}>
                      Forget
                    </button>
                  </div>
                </div>
                <p className="text-[12px]" style={{ color: "var(--ml-muted)" }}>{info.role}{info.context ? ` · ${info.context}` : ""}</p>
              </>
            )}
          </div>
        ))}
      </MemoryCategory>

      <MemoryCategory title="What's been hard" empty={triggerTopics.length === 0} emptyText="Nothing flagged as a hard topic.">
        <ChipList items={triggerTopics} onRemove={(v) => removeListItem("trigger_topics", v)} />
      </MemoryCategory>

      <MemoryCategory title="What's helped" empty={effectiveCoping.length === 0} emptyText="No coping strategies on file yet.">
        <ChipList items={effectiveCoping} onRemove={(v) => removeListItem("effective_coping", v)} />
      </MemoryCategory>

      <MemoryCategory title="Your notes" empty={notes.length === 0} emptyText="No notes yet.">
        {notes.map((note) => (
          <div key={note.note_id} className="flex items-start justify-between gap-3 rounded-[var(--r-13)] p-3" style={{ border: "1px solid var(--ml-hairline)" }}>
            <p className="text-[13px] leading-[1.55]" style={{ color: "var(--ml-ink)" }}>{note.text}</p>
            <button type="button" onClick={() => forgetNote(note.note_id)} aria-label="Delete note" style={{ color: "var(--ml-faint)" }}>
              <Trash2 size={13} strokeWidth={1.8} />
            </button>
          </div>
        ))}
        <div className="mt-1 flex gap-2">
          <input
            value={noteDraft}
            onChange={(e) => setNoteDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addNote()}
            placeholder="Add a note Mindlens should remember…"
            className="min-w-0 flex-1 rounded-[99px] px-4 py-2 text-[13px] outline-none"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          />
          <button
            type="button"
            onClick={addNote}
            disabled={savingNote || !noteDraft.trim()}
            className="shrink-0 rounded-[99px] px-4 py-2 text-[12.5px] font-medium disabled:opacity-50"
            style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
          >
            Add
          </button>
        </div>
      </MemoryCategory>
    </div>
  );
}

function MemoryCategory({
  title,
  empty,
  emptyText,
  children,
}: {
  title: string;
  empty: boolean;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="ml-eyebrow mb-3">{title}</p>
      {empty ? (
        <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{emptyText}</p>
      ) : (
        <div className="flex flex-col gap-2">{children}</div>
      )}
    </section>
  );
}

function ChipList({ items, onRemove }: { items: string[]; onRemove: (value: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="inline-flex items-center gap-1.5 rounded-[99px] py-1.5 pl-3 pr-2 text-[12.5px]"
          style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {item}
          <button type="button" onClick={() => onRemove(item)} aria-label={`Forget ${item}`} style={{ color: "var(--ml-faint)" }}>
            <X size={12} strokeWidth={2} />
          </button>
        </span>
      ))}
    </div>
  );
}
