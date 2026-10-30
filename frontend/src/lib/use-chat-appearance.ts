"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMemory } from "./api";
import { DEFAULT_COMPANION_ID, getCompanion, type CompanionId } from "./companions";
import { EMOTION_STATES, type EmotionId } from "./emotion";
import { PREVIEW_MODE } from "./preview";

type AuthStatus = "checking" | "anonymous" | "onboarding" | "ready";

export function useChatAppearance(authStatus: AuthStatus) {
  // The user's chosen companion (lib/companions.ts) — defaults to Ember
  // until (if) the real preference loads, so chat never waits on this fetch.
  const [companionId, setCompanionId] = useState<CompanionId>(DEFAULT_COMPANION_ID);
  const [companionName, setCompanionName] = useState<string>(getCompanion(DEFAULT_COMPANION_ID).name);
  // Settings > Appearance > Colour. "manual" pins the room's palette so it
  // stops tracking the conversation; the read itself is unaffected.
  const [paletteMode, setPaletteMode] = useState<"auto" | "manual">("auto");
  const [manualPalette, setManualPalette] = useState<EmotionId>("calm");
  // Settings > Appearance > Intensity — caps field opacity, glow radius,
  // companion amplitude and accent saturation together (design.md §2).
  const [intensityCap, setIntensityCap] = useState<number>(1);

  // --- Companion preference: fetched once, so chat renders the user's
  // actual chosen shape/name instead of always defaulting to Ember. -------
  useEffect(() => {
    if (authStatus !== "ready" || PREVIEW_MODE) return;
    let cancelled = false;
    fetchMemory()
      .then((doc) => {
        if (cancelled) return;
        const id = getCompanion(doc.preferences?.companion_id).id;
        setCompanionId(id);
        setCompanionName(doc.preferences?.companion_name || getCompanion(id).name);
        setPaletteMode(doc.preferences?.palette_mode === "manual" ? "manual" : "auto");
        if (doc.preferences?.manual_palette && doc.preferences.manual_palette in EMOTION_STATES) {
          setManualPalette(doc.preferences.manual_palette as EmotionId);
        }
        if (typeof doc.preferences?.intensity_cap === "number") {
          setIntensityCap(doc.preferences.intensity_cap);
        }
      })
      .catch(() => {
        // No memory doc yet, or the fetch failed — the Ember default stands.
      });
    return () => {
      cancelled = true;
    };
  }, [authStatus]);

  /** Settings calls this right after a successful save, so chat reflects the
   * new companion immediately instead of waiting on a refetch. */
  const applyCompanionPreference = useCallback((id: CompanionId, name: string) => {
    setCompanionId(id);
    setCompanionName(name);
  }, []);

  /** Same contract as applyCompanionPreference: settings saved it, so the
   * room must reflect it now rather than on the next mount. Without this the
   * preference persists correctly but the colour visibly doesn't change,
   * which reads as the control being broken. */
  const applyPalettePreference = useCallback((mode: "auto" | "manual", palette: EmotionId) => {
    setPaletteMode(mode);
    setManualPalette(palette);
  }, []);

  /** Same contract — applied immediately on save rather than waiting on a
   * refetch, so dragging the slider down visibly calms the room right away. */
  const applyIntensityCap = useCallback((cap: number) => {
    setIntensityCap(cap);
  }, []);

  return {
    companionId, companionName, paletteMode, manualPalette, intensityCap,
    applyCompanionPreference, applyPalettePreference, applyIntensityCap,
  };
}
