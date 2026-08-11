"use client";

/**
 * Settings > Memory. The memory manager already exists as a full page
 * (components/pages/memory-page.tsx) and is the same thing a user wants
 * here, so this reuses it rather than growing a second, drifting copy.
 *
 * Memory depth (design.md §4.2, board 5d) sits above it: backend already
 * honours all three levels (memory_recall.py) and the schema already accepts
 * them (routers/memory.py's PreferencesUpdate) — the control to actually set
 * it was the missing piece, so this is the one addition.
 */

import { Check } from "lucide-react";
import { MemoryPage } from "@/components/pages/memory-page";
import type { MemoryPreferences } from "@/lib/types";
import { Row, SaveBar, SettingsGroup, SettingsHeading } from "../ui";
import { usePrefs } from "../use-prefs";

const KEYS: (keyof MemoryPreferences)[] = ["memory_depth"];

const DEPTHS: { id: NonNullable<MemoryPreferences["memory_depth"]>; label: string; hint: string }[] = [
  { id: "everything", label: "Everything", hint: "Full continuity — people, patterns and past sessions all inform replies." },
  { id: "key_details", label: "Key details only", hint: "People you've mentioned come up; deeper emotional-pattern recall doesn't." },
  { id: "nothing", label: "Nothing", hint: "Start fresh each time. Your tone, personality and instructions still apply — this only turns off recall of past conversations." },
];

export function MemorySection() {
  const { draft, set, save, isDirty, loading, saving, justSaved, error } = usePrefs();
  const depth = draft.memory_depth ?? "everything";

  return (
    <>
      <SettingsHeading>Memory</SettingsHeading>

      <SettingsGroup title="Memory depth">
        <Row
          label="How much Mindlens draws on"
          description="Changes what this turn's reply is allowed to recall — not what's kept below, which you can always see and edit."
          stacked
          control={
            <div className="flex flex-col gap-2">
              {DEPTHS.map((option) => {
                const active = depth === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => set("memory_depth", option.id)}
                    aria-pressed={active}
                    className="flex items-start gap-3 rounded-[var(--r-13)] p-3 text-left transition-colors"
                    style={{
                      border: active ? "1.5px solid var(--e1)" : "1px solid var(--ml-hairline)",
                      background: active ? "color-mix(in oklab, var(--e1) 10%, transparent)" : "transparent",
                    }}
                  >
                    <span
                      className="mt-0.5 grid size-[15px] shrink-0 place-items-center rounded-full"
                      style={{ border: active ? "none" : "1px solid var(--ml-hairline-strong)", background: active ? "var(--e1)" : "transparent" }}
                    >
                      {active && <Check size={10} strokeWidth={3} className="text-white" />}
                    </span>
                    <span>
                      <span className="block text-[13px] font-medium" style={{ color: "var(--ml-ink)" }}>
                        {option.label}
                      </span>
                      <span className="mt-0.5 block text-[12px] leading-[1.5]" style={{ color: "var(--ml-muted)" }}>
                        {option.hint}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          }
        />

        {error && (
          <p className="mt-3 text-[12.5px]" style={{ color: "#e08a8a" }}>
            {error}
          </p>
        )}

        {!loading && <SaveBar onSave={() => save(KEYS)} saving={saving} saved={justSaved} dirty={isDirty(KEYS)} />}
      </SettingsGroup>

      <SettingsGroup title="What's kept">
        <p className="mb-6 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
          Everything Mindlens has kept about you, and the controls to change or
          remove any of it.
        </p>
        <MemoryPage />
      </SettingsGroup>
    </>
  );
}
