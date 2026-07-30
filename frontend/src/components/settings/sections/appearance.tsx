"use client";

/**
 * Settings > Appearance — day/night, who your companion is, and how the room
 * gets its colour.
 *
 * The companion picker and the emotion swatches used to sit in the app
 * chrome (the Your Mindlens page and the chat inspector). They're
 * configuration, not conversation, so they live here now; the inspector
 * keeps only the live read.
 */

import { useState } from "react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { COMPANIONS, getCompanion, type CompanionId } from "@/lib/companions";
import { EMOTION_ORDER, EMOTION_STATES, type EmotionId } from "@/lib/emotion";
import type { MemoryPreferences } from "@/lib/types";
import { useGrade } from "@/lib/use-grade";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { Row, SaveBar, SettingsGroup, SettingsHeading, TextInput } from "../ui";
import { usePrefs } from "../use-prefs";

const KEYS: (keyof MemoryPreferences)[] = [
  "companion_id",
  "companion_name",
  "palette_mode",
  "manual_palette",
];

export function AppearanceSection({ client }: { client: MindLensClient }) {
  const { isDay, setGrade } = useGrade();
  const { draft, set, save, isDirty, loading, saving, justSaved, error } = usePrefs();
  const [nameTouched, setNameTouched] = useState(false);

  if (loading) {
    return <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>;
  }

  const companionId = (draft.companion_id ?? "nimbus") as CompanionId;
  const companionName = draft.companion_name ?? getCompanion(companionId).name;
  const paletteMode = draft.palette_mode ?? "auto";
  const manualPalette = draft.manual_palette ?? "calm";

  const pickCompanion = (id: CompanionId) => {
    // Only auto-rename while the name is still a cast default — once someone
    // has typed their own, switching shape must not overwrite it.
    if (!nameTouched && companionName === getCompanion(companionId).name) {
      set("companion_name", getCompanion(id).name);
    }
    set("companion_id", id);
  };

  const saveAll = async () => {
    await save(KEYS);
    client.applyCompanionPreference(companionId, companionName.trim() || getCompanion(companionId).name);
    client.applyPalettePreference(paletteMode, manualPalette as EmotionId);
  };

  return (
    <>
      <SettingsHeading>Appearance</SettingsHeading>

      <SettingsGroup title="Theme">
        <Row
          label="Day or night"
          description="Applies everywhere, including the marketing site."
          control={
            <div
              className="inline-flex rounded-[99px] p-1"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
            >
              {(["day", "night"] as const).map((mode) => {
                const active = (mode === "day") === isDay;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setGrade(mode)}
                    className="rounded-[99px] px-4 py-1.5 text-[12.5px] font-medium capitalize transition-colors"
                    style={{
                      background: active ? "var(--ml-ink)" : "transparent",
                      color: active ? "var(--ml-canvas)" : "var(--ml-muted)",
                    }}
                  >
                    {mode}
                  </button>
                );
              })}
            </div>
          }
        />
      </SettingsGroup>

      <SettingsGroup title="Companion">
        <Row
          label="Who's with you"
          description="Ten shapes, one job — the one you pick is who shows up in chat."
          stacked
          control={
            <div className="grid grid-cols-5 gap-2.5">
              {COMPANIONS.map((companion) => {
                const active = companion.id === companionId;
                return (
                  <button
                    key={companion.id}
                    type="button"
                    onClick={() => pickCompanion(companion.id)}
                    title={companion.tagline}
                    className="flex flex-col items-center gap-2 rounded-[var(--r-13)] p-3 text-center transition-colors"
                    style={{
                      border: active ? "1.5px solid var(--e1)" : "1px solid var(--ml-hairline)",
                      background: active
                        ? "color-mix(in oklab, var(--e1) 10%, transparent)"
                        : "var(--ml-panel)",
                    }}
                  >
                    <CompanionAvatar companionId={companion.id} size={34} />
                    <span className="text-[11.5px]" style={{ color: "var(--ml-ink)" }}>
                      {companion.name}
                    </span>
                  </button>
                );
              })}
            </div>
          }
        />
        <Row
          label="Their name"
          description={getCompanion(companionId).tagline}
          control={
            <TextInput
              ariaLabel="Companion name"
              value={companionName}
              maxLength={40}
              placeholder={getCompanion(companionId).name}
              onChange={(next) => {
                setNameTouched(true);
                set("companion_name", next);
              }}
            />
          }
        />
      </SettingsGroup>

      <SettingsGroup title="Colour">
        <Row
          label="How the room gets its colour"
          description={
            paletteMode === "auto"
              ? "Auto — the room recolours from what Mindlens reads in each message, crossfading over 1.6s."
              : "Manual — the room stays in the palette you pick, whatever the conversation is doing."
          }
          control={
            <div
              className="inline-flex rounded-[99px] p-1"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
            >
              {(["auto", "manual"] as const).map((mode) => {
                const active = paletteMode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => set("palette_mode", mode)}
                    className="rounded-[99px] px-4 py-1.5 text-[12.5px] font-medium capitalize transition-colors"
                    style={{
                      background: active ? "var(--ml-ink)" : "transparent",
                      color: active ? "var(--ml-canvas)" : "var(--ml-muted)",
                    }}
                  >
                    {mode}
                  </button>
                );
              })}
            </div>
          }
        />

        {paletteMode === "manual" && (
          <Row
            label="Your palette"
            description="Pinned. The emotion read still happens and still shows — it just stops driving the colour."
            stacked
            control={
              <div className="grid grid-cols-6 gap-2">
                {EMOTION_ORDER.map((id) => {
                  const state = EMOTION_STATES[id];
                  const active = manualPalette === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      title={state.name}
                      aria-label={state.name}
                      aria-pressed={active}
                      onClick={() => set("manual_palette", id)}
                      className="flex flex-col items-center gap-1.5"
                    >
                      <span
                        className="h-10 w-full rounded-[var(--r-11)] transition-transform"
                        style={{
                          background: `linear-gradient(140deg, ${state.c1}, ${state.c2})`,
                          border: active ? "2px solid var(--ml-ink)" : "1px solid var(--ml-hairline)",
                          transform: active ? "scale(1.04)" : undefined,
                          opacity: active ? 1 : 0.7,
                        }}
                      />
                      <span className="text-[10.5px]" style={{ color: "var(--ml-muted)" }}>
                        {state.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            }
          />
        )}
      </SettingsGroup>

      {error && (
        <p className="mb-3 text-[12.5px]" style={{ color: "#e08a8a" }}>
          {error}
        </p>
      )}

      <SaveBar onSave={saveAll} saving={saving} saved={justSaved} dirty={isDirty(KEYS)} />
    </>
  );
}
