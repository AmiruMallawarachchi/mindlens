"use client";

/**
 * Day/night grade toggle — shared between Home and the app so the choice is
 * one setting, not two. Mirrors the mockups' own toggleGrade/readGrade
 * logic exactly: persisted to localStorage["ml-grade"], defaulting to day.
 */

import { useCallback, useEffect, useState } from "react";

export type Grade = "day" | "night";
/** What's stored/chosen: a real grade, or "auto" to follow the OS. */
export type GradeMode = Grade | "auto";

const STORAGE_KEY = "ml-grade";

function systemGrade(): Grade {
  if (typeof window === "undefined") return "day";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
}

function readStoredMode(): GradeMode {
  if (typeof window === "undefined") return "auto";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "night" || stored === "day" || stored === "auto" ? stored : "auto";
  } catch {
    return "auto";
  }
}

export function useGrade() {
  // Starts "auto"/system-day during SSR/hydration, then syncs from storage —
  // avoids a hydration mismatch while still respecting a returning visitor's
  // choice within the same paint (no visible flash in practice at this app's
  // size). board 6b: "Auto-switches with system time by default."
  const [mode, setModeState] = useState<GradeMode>("auto");
  const [grade, setGrade_] = useState<Grade>("day");

  useEffect(() => {
    setModeState(readStoredMode());
  }, []);

  useEffect(() => {
    const resolve = () => setGrade_(mode === "auto" ? systemGrade() : mode);
    resolve();
    if (mode !== "auto") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mql.addEventListener("change", resolve);
    return () => mql.removeEventListener("change", resolve);
  }, [mode]);

  useEffect(() => {
    document.documentElement.setAttribute("data-grade", grade);
  }, [grade]);

  const setMode = useCallback((next: GradeMode) => {
    setModeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage unavailable (private mode, quota) — mode still applies
      // for this session via state, just doesn't persist.
    }
  }, []);

  // Back-compat: callers that only want a real grade (not "auto") still get
  // one — setting it directly opts out of following the system.
  const setGrade = useCallback((next: Grade) => setMode(next), [setMode]);
  const toggleGrade = useCallback(() => {
    setMode(grade === "night" ? "day" : "night");
  }, [grade, setMode]);

  return {
    mode,
    setMode,
    grade,
    setGrade,
    toggleGrade,
    isDay: grade === "day",
    isNight: grade === "night",
  };
}
