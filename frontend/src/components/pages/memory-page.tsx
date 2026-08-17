"use client";

/**
 * Memory — design.md §4.2: "You decide what Mindlens remembers". Category
 * cards backed by the real memory document, each with Forget (delete) —
 * and for people, an inline Edit. Empty states are honest: a category with
 * nothing in it says so, rather than showing placeholder content.
 */

import { useEffect, useState } from "react";
import { Heart, MessageSquareWarning, ShieldCheck, Sparkles, StickyNote, Trash2, X } from "lucide-react";
import {
  addMemoryNote,
  deleteMemoryEntry,
  deleteMemoryNote,
  fetchMemory,
  updateMemoryPeople,
  updateMemoryPreferences,
} from "@/lib/api";
import type { MemoryDoc } from "@/lib/types";

export function MemoryPage() {
  const [memory, setMemory] = useState<MemoryDoc | null | "missing">(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [editingPerson, setEditingPerson] = useState<string | null>(null);
  const [editRole, setEditRole] = useState("");
  const [editContext, setEditContext] = useState("");
  // A "Forget" click arms that one item rather than deleting immediately —
  // the second click within the window confirms. Proportionate friction for
  // a single recoverable-ish item; the typed-password panel in Settings >
  // Privacy is reserved for the one truly irreversible action (the account).
  const [armedKey, setArmedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchMemory()
      .then(setMemory)
      .catch(() => setMemory("missing"));
  };

  useEffect(load, []);

  /** Arms `key` on first call, runs `action` and disarms on the second
   * (confirming) call. Surfaces a failure instead of leaving an unhandled
   * rejection and a button stuck mid-delete. */
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
      setError("Couldn't forget that — try again.");
    }
  };

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
  const threadCount = people.length + triggerTopics.length + effectiveCoping.length + notes.length;

  const forgetPerson = (name: string) =>
    confirmThenRun(`people:${name}`, () => deleteMemoryEntry("people", name));

  const savePersonEdit = async (name: string) => {
    const current = memory.people[name];
    const updated = {
      ...memory.people,
      [name]: { role: editRole, context: editContext, sentiment: current?.sentiment ?? "positive" },
    };
    setError(null);
    try {
      await updateMemoryPeople(updated);
      setEditingPerson(null);
      load();
    } catch {
      setError("Couldn't save that — try again.");
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
      setError("Couldn't save that note — try again.");
    } finally {
      setSavingNote(false);
    }
  };

  const forgetNote = (noteId: string) =>
    confirmThenRun(`notes:${noteId}`, () => deleteMemoryNote(noteId));

  // Inferred from conversation, not typed by the user — unlike everything
  // else on this page. Still has to appear here: it changes what Mindlens
  // suggests (RoutineAgent's solo-vs-social branch), so leaving it invisible
  // would make "anything Mindlens learns lands on this page" false for this
  // one field. `null` clears it; a plain PATCH omitting the key would not.
  const introvertScore = memory.preferences?.introvert_score;
  const forgetSocialRead = () =>
    confirmThenRun("introvert_score", () => updateMemoryPreferences({ introvert_score: null }));

  return (
    <div className="flex flex-col gap-9">
      <div
        className="flex items-start gap-3 rounded-[var(--r-16)] p-4"
        style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
      >
        <ShieldCheck size={16} strokeWidth={1.8} className="mt-0.5 shrink-0" style={{ color: "var(--e1)" }} />
        <p className="text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
          Everything here is visible and editable. Anything Mindlens
          &lsquo;learns&rsquo; about you lands on this page first, where you can
          change or delete it &mdash; your conversations themselves are kept
          separately so it can pick up where you left off. This is not a
          diagnosis; it&rsquo;s just what you&rsquo;ve told Mindlens.
        </p>
      </div>

      {typeof introvertScore === "number" && (
        <div
          className="flex items-center justify-between gap-3 rounded-[var(--r-16)] p-4"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          <div>
            <p className="ml-eyebrow mb-1">Social read</p>
            <p className="text-[12.5px] leading-[1.55]" style={{ color: "var(--ml-muted)" }}>
              Picked up from conversation, not something you told it directly —
              shapes whether Mindlens suggests solo or social activities. Reads{" "}
              {introvertScore < 0.4 ? "more introverted" : introvertScore > 0.6 ? "more extroverted" : "balanced"} right now.
            </p>
          </div>
          <button
            type="button"
            onClick={forgetSocialRead}
            onBlur={() => setArmedKey((k) => (k === "introvert_score" ? null : k))}
            className="shrink-0 text-[11.5px] font-medium"
            style={{ color: "#e08a8a" }}
          >
            {armedKey === "introvert_score" ? "Click to confirm" : "Forget"}
          </button>
        </div>
      )}

      {error && (
        <p className="text-[12.5px]" style={{ color: "#e08a8a" }}>
          {error}
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_260px]">
        <MemoryCategory title="Important people" empty={people.length === 0} emptyText="No one on file yet.">
          <div className="grid gap-3 sm:grid-cols-2">
            {people.map(([name, info]) => (
              <div
                key={name}
                className="flex flex-col gap-2.5 rounded-[var(--r-16)] p-4"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
              >
                <Heart size={16} strokeWidth={1.7} style={{ color: "var(--e1)" }} />
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
                    <div>
                      <p className="ml-display text-[16px]" style={{ color: "var(--ml-ink)" }}>{name}</p>
                      <p className="mt-1 text-[12px]" style={{ color: "var(--ml-muted)" }}>{info.role}{info.context ? ` · ${info.context}` : ""}</p>
                    </div>
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
                      <button
                        type="button"
                        onClick={() => forgetPerson(name)}
                        onBlur={() => setArmedKey((k) => (k === `people:${name}` ? null : k))}
                        className="text-[11.5px] font-medium"
                        style={{ color: "#e08a8a" }}
                      >
                        {armedKey === `people:${name}` ? "Click to confirm" : "Forget"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </MemoryCategory>

        <TheLoom threadCount={threadCount} />
      </div>

      <MemoryCategory title="What's been hard" icon={<MessageSquareWarning size={14} strokeWidth={1.8} />} empty={triggerTopics.length === 0} emptyText="Nothing flagged as a hard topic.">
        <ChipList
          items={triggerTopics}
          onRemove={(v) => removeListItem("trigger_topics", v)}
          isArmed={(v) => armedKey === `trigger_topics:${v}`}
        />
      </MemoryCategory>

      <MemoryCategory title="What's helped" icon={<Sparkles size={14} strokeWidth={1.8} />} empty={effectiveCoping.length === 0} emptyText="No coping strategies on file yet.">
        <ChipList
          items={effectiveCoping}
          onRemove={(v) => removeListItem("effective_coping", v)}
          isArmed={(v) => armedKey === `effective_coping:${v}`}
        />
      </MemoryCategory>

      <MemoryCategory title="Your notes" icon={<StickyNote size={14} strokeWidth={1.8} />} empty={notes.length === 0} emptyText="No notes yet.">
        {notes.map((note) => {
          const key = `notes:${note.note_id}`;
          return (
            <div key={note.note_id} className="flex items-start justify-between gap-3 rounded-[var(--r-13)] p-3" style={{ border: "1px solid var(--ml-hairline)" }}>
              <p className="text-[13px] leading-[1.55]" style={{ color: "var(--ml-ink)" }}>{note.text}</p>
              <button
                type="button"
                onClick={() => forgetNote(note.note_id)}
                onBlur={() => setArmedKey((k) => (k === key ? null : k))}
                aria-label={armedKey === key ? `Click to confirm forgetting this note` : "Delete note"}
                className="shrink-0"
                style={{ color: armedKey === key ? "#e08a8a" : "var(--ml-faint)" }}
              >
                {armedKey === key ? <span className="text-[11px] font-medium">Confirm</span> : <Trash2 size={13} strokeWidth={1.8} />}
              </button>
            </div>
          );
        })}
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
  icon,
  empty,
  emptyText,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  empty: boolean;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="ml-eyebrow mb-3 inline-flex items-center gap-1.5" style={{ color: icon ? "var(--ml-muted)" : undefined }}>
        {icon}
        {title}
      </p>
      {empty ? (
        <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{emptyText}</p>
      ) : (
        <div className="flex flex-col gap-2">{children}</div>
      )}
    </section>
  );
}

/** A purely decorative, real-count-driven visualization — every person,
 * topic, coping strategy and note is a "thread". No fabricated data: the
 * count is threadCount from the actual memory doc. */
function TheLoom({ threadCount }: { threadCount: number }) {
  const strands = [
    { left: "14%", rotate: -6, delay: 0 },
    { left: "38%", rotate: 4, delay: 0.15 },
    { left: "62%", rotate: -4, delay: 0.3 },
    { left: "86%", rotate: 6, delay: 0.45 },
  ];
  return (
    <div
      className="flex flex-col items-center gap-3.5 rounded-[var(--r-18)] p-5 text-center"
      style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
    >
      <p className="ml-eyebrow self-start">The Loom</p>
      <div className="relative h-[120px] w-full max-w-[180px]">
        {strands.map((s, i) => (
          <span
            key={i}
            aria-hidden="true"
            className="absolute top-0 w-px"
            style={{
              left: s.left,
              height: "88px",
              background: `linear-gradient(180deg, ${i % 2 === 0 ? "var(--e1)" : "var(--e2)"}, transparent)`,
              transform: `rotate(${s.rotate}deg)`,
            }}
          />
        ))}
        {strands.map((s, i) => (
          <span
            key={`dot-${i}`}
            aria-hidden="true"
            className="absolute size-[8px] rounded-full"
            style={{
              left: s.left,
              top: `${34 + (i % 3) * 18}px`,
              background: i % 2 === 0 ? "var(--e1)" : "var(--e2)",
              boxShadow: `0 0 8px ${i % 2 === 0 ? "var(--e1)" : "var(--e2)"}`,
            }}
          />
        ))}
      </div>
      <p className="text-[11.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
        {threadCount > 0
          ? `${threadCount} thread${threadCount === 1 ? "" : "s"} so far. A person, a hard topic, or something that helped can turn into one as you talk — or add one yourself below.`
          : "Nothing on file yet. Mention someone or something that helped as you talk, or add one yourself below."}
      </p>
    </div>
  );
}

function ChipList({
  items,
  onRemove,
  isArmed,
}: {
  items: string[];
  onRemove: (value: string) => void;
  isArmed: (value: string) => boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const armed = isArmed(item);
        return (
        <span
          key={item}
          className="inline-flex items-center gap-1.5 rounded-[99px] py-1.5 pl-3 pr-2 text-[12.5px]"
          style={{ border: armed ? "1px solid #e08a8a" : "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {item}
          <button
            type="button"
            onClick={() => onRemove(item)}
            aria-label={armed ? `Click to confirm forgetting ${item}` : `Forget ${item}`}
            style={{ color: armed ? "#e08a8a" : "var(--ml-faint)" }}
          >
            {armed ? <span className="text-[10.5px] font-medium">Confirm</span> : <X size={12} strokeWidth={2} />}
          </button>
        </span>
        );
      })}
    </div>
  );
}
