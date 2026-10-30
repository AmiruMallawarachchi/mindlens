"use client";

/**
 * Memory — design.md §4.2: "You decide what MindLens remembers". Category
 * cards backed by the real memory document, each with Forget (delete) —
 * and for people, an inline Edit. Empty states are honest: a category with
 * nothing in it says so, rather than showing placeholder content.
 */

import { Heart, MessageSquareWarning, ShieldCheck, Sparkles, StickyNote, Trash2 } from "lucide-react";
import { MemoryCategory, ChipList } from "./memory-page-components";
import { useMemoryPage } from "./use-memory-page";

export function MemoryPage() {
  const {
    memory, noteDraft, setNoteDraft, savingNote, editingPerson, setEditingPerson,
    editRole, setEditRole, editContext, setEditContext, armedKey, setArmedKey,
    error, people, triggerTopics, effectiveCoping, notes, forgetPerson,
    savePersonEdit, removeListItem, addNote, forgetNote, introvertScore,
    forgetSocialRead,
  } = useMemoryPage();

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


  return (
    <div className="flex flex-col gap-9">
      <div
        className="flex items-start gap-3 rounded-[var(--r-16)] p-4"
        style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
      >
        <ShieldCheck size={16} strokeWidth={1.8} className="mt-0.5 shrink-0" style={{ color: "var(--e1)" }} />
        <p className="text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
          Everything here is visible and editable. Anything MindLens
          &lsquo;learns&rsquo; about you lands on this page first, where you can
          change or delete it &mdash; your conversations themselves are kept
          separately so it can pick up where you left off. This is not a
          diagnosis; it&rsquo;s just what you&rsquo;ve told MindLens.
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
              shapes whether MindLens suggests solo or social activities. Reads{" "}
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
            placeholder="Add a note MindLens should remember…"
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
