"use client";

/**
 * Your Mindlens — design.md §4.2: a full studio page, not a modal.
 * Tone (Gentle<->Direct), memory depth, appearance, and companion naming —
 * all backed by real preference fields (memory_recall.py already reads
 * tone_preference and memory_depth back into every turn; this is what lets
 * the user set them). Motion/sound/emotion-palette controls from the
 * original mockup text spec are deliberately left out here: there's no
 * ambient audio system and no per-user colour-override backend, and this
 * project's rule is not to ship a control that doesn't actually do
 * anything.
 */

import { useEffect, useState } from "react";
import { fetchMemory, updateMemoryPreferences } from "@/lib/api";
import { useGrade } from "@/lib/use-grade";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { COMPANIONS, getCompanion, type CompanionId } from "@/lib/companions";
import type { MemoryDoc, MemoryPreferences } from "@/lib/types";
import type { MindLensClient } from "@/lib/use-mindlens-client";

const TONE_OPTIONS: { id: NonNullable<MemoryPreferences["tone_preference"]>; label: string }[] = [
  { id: "gentle", label: "Gentle" },
  { id: "balanced", label: "Balanced" },
  { id: "direct", label: "Direct" },
];

const DEPTH_OPTIONS: { id: NonNullable<MemoryPreferences["memory_depth"]>; label: string; description: string }[] = [
  { id: "everything", label: "Everything", description: "Full recall — people, patterns, what's helped before." },
  { id: "key_details", label: "Key details", description: "Just names and context, not deeper pattern-matching." },
  { id: "nothing", label: "Nothing", description: "Every conversation starts fresh." },
];

export function YourMindlensPage({
  client,
  onLogout,
}: {
  client: MindLensClient;
  onLogout: () => void;
}) {
  const { isDay, setGrade } = useGrade();
  const [memory, setMemory] = useState<MemoryDoc | null>(null);
  const [tone, setTone] = useState<MemoryPreferences["tone_preference"]>("balanced");
  const [depth, setDepth] = useState<MemoryPreferences["memory_depth"]>("everything");
  const [companionId, setCompanionId] = useState<CompanionId>("nimbus");
  const [companionName, setCompanionName] = useState("Nimbus");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchMemory()
      .then((doc) => {
        setMemory(doc);
        setTone(doc.preferences?.tone_preference ?? "balanced");
        setDepth(doc.preferences?.memory_depth ?? "everything");
        const id = getCompanion(doc.preferences?.companion_id).id;
        setCompanionId(id);
        setCompanionName(doc.preferences?.companion_name || getCompanion(id).name);
      })
      .catch(() => {
        // No memory doc yet (pre-onboarding) — the controls still work,
        // they just won't have anything to prefill from.
      });
  }, []);

  const pickCompanion = (id: CompanionId) => {
    // Only auto-rename if the name still matches the previous companion's
    // default — once someone types their own name, picking a different
    // shape shouldn't silently overwrite it.
    setCompanionName((current) =>
      current === getCompanion(companionId).name ? getCompanion(id).name : current,
    );
    setCompanionId(id);
  };

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const finalName = companionName.trim() || getCompanion(companionId).name;
      await updateMemoryPreferences({
        tone_preference: tone,
        memory_depth: depth,
        companion_id: companionId,
        companion_name: finalName,
      });
      client.applyCompanionPreference(companionId, finalName);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-7">
      <SettingsSection title="Companion" description="Pick who's with you in the room, then name them.">
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
          {COMPANIONS.map((companion) => {
            const active = companion.id === companionId;
            return (
              <button
                key={companion.id}
                type="button"
                onClick={() => pickCompanion(companion.id)}
                title={companion.tagline}
                className="flex flex-col items-center gap-2 rounded-[var(--r-16)] p-3.5 text-center transition-colors"
                style={{
                  border: active ? "1.5px solid var(--e1)" : "1px solid var(--ml-hairline)",
                  background: active ? "color-mix(in oklab, var(--e1) 10%, transparent)" : "var(--ml-panel)",
                }}
              >
                <CompanionAvatar companionId={companion.id} size={40} />
                <span className="text-[12px] font-medium" style={{ color: "var(--ml-ink)" }}>
                  {companion.name}
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-3 text-[11.5px] leading-[1.5]" style={{ color: "var(--ml-faint)" }}>
          {getCompanion(companionId).tagline}
        </p>
        <div className="mt-3.5 flex items-center gap-3">
          <CompanionAvatar companionId={companionId} size={36} />
          <input
            value={companionName}
            onChange={(e) => setCompanionName(e.target.value)}
            maxLength={40}
            placeholder={getCompanion(companionId).name}
            className="min-w-0 flex-1 rounded-[99px] px-4 py-2.5 text-[14px] outline-none"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          />
        </div>
      </SettingsSection>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="flex flex-col gap-5">
          <SettingsSection title="Personality" description="How direct Mindlens should be with you.">
            <div className="inline-flex rounded-[99px] p-1" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
              {TONE_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setTone(opt.id)}
                  className="rounded-[99px] px-4 py-2 text-[12.5px] font-medium transition-colors"
                  style={{
                    background: tone === opt.id ? "linear-gradient(135deg, var(--e1), var(--e2))" : "transparent",
                    color: tone === opt.id ? "#fffdf8" : "var(--ml-muted)",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </SettingsSection>
        </div>

        <div className="flex flex-col gap-5">
          <SettingsSection title="Appearance" description="Light or dark — synced with the toggle in the header.">
            <div className="inline-flex rounded-[99px] p-1" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
              <button
                type="button"
                onClick={() => setGrade("day")}
                className="rounded-[99px] px-4 py-2 text-[12.5px] font-medium"
                style={{ background: isDay ? "var(--ml-ink)" : "transparent", color: isDay ? "var(--ml-canvas)" : "var(--ml-muted)" }}
              >
                Day
              </button>
              <button
                type="button"
                onClick={() => setGrade("night")}
                className="rounded-[99px] px-4 py-2 text-[12.5px] font-medium"
                style={{ background: !isDay ? "var(--ml-ink)" : "transparent", color: !isDay ? "var(--ml-canvas)" : "var(--ml-muted)" }}
              >
                Night
              </button>
            </div>
          </SettingsSection>

          <SettingsSection title="Memory depth" description="How much Mindlens draws on from before.">
            <div className="flex flex-col gap-2">
              {DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setDepth(opt.id)}
                  className="flex flex-col items-start gap-0.5 rounded-[var(--r-13)] p-3.5 text-left transition-colors"
                  style={{
                    border: depth === opt.id ? "1.5px solid var(--e1)" : "1px solid var(--ml-hairline)",
                    background: depth === opt.id ? "color-mix(in oklab, var(--e1) 8%, transparent)" : "transparent",
                  }}
                >
                  <span className="text-[13.5px] font-medium" style={{ color: "var(--ml-ink)" }}>{opt.label}</span>
                  <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>{opt.description}</span>
                </button>
              ))}
            </div>
          </SettingsSection>
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-[99px] px-5 py-2.5 text-[13px] font-medium disabled:opacity-60"
          style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
        >
          {saving ? "Saving…" : "Save preferences"}
        </button>
        {saved && <span className="text-[12.5px]" style={{ color: "var(--e1)" }}>Saved.</span>}
        {!memory && (
          <span className="text-[11.5px]" style={{ color: "var(--ml-faint)" }}>
            (No memory profile yet — preferences will apply once one exists.)
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-col gap-4 pt-6" style={{ borderTop: "1px solid var(--ml-hairline)" }}>
        <p className="text-[11px]" style={{ color: "var(--ml-faint)" }}>
          Crisis support always uses a stable, high-clarity view — none of these preferences change how a crisis is handled.
        </p>
        <button
          type="button"
          onClick={onLogout}
          className="self-start rounded-[99px] px-4 py-2 text-[12.5px]"
          style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-muted)" }}
        >
          Log out
        </button>
      </div>
    </div>
  );
}

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <p className="text-[14px] font-medium" style={{ color: "var(--ml-ink)" }}>{title}</p>
        <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--ml-faint)" }}>{description}</p>
      </div>
      {children}
    </section>
  );
}
