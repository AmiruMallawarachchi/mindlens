"use client";

/**
 * Day/night grade toggle — shared between Home and the app so the choice is
 * one setting, not two. Mirrors the mockups' own toggleGrade/readGrade
 * logic exactly: persisted to localStorage["ml-grade"], defaulting to day.
 */

import { useCallback, useEffect, useState } from "react";

export type Grade = "day" | "night";

const STORAGE_KEY = "ml-grade";

function readStoredGrade(): Grade {
  if (typeof window === "undefined") return "day";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "night" ? "night" : "day";
  } catch {
    return "day";
  }
}

export function useGrade() {
  // Starts at "day" during SSR/hydration, then syncs from storage — avoids
  // a hydration mismatch while still respecting a returning visitor's choice
  // within the same paint (no visible flash in practice at this app's size).
  const [grade, setGradeState] = useState<Grade>("day");

  useEffect(() => {
    setGradeState(readStoredGrade());
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-grade", grade);
  }, [grade]);

  const setGrade = useCallback((next: Grade) => {
    setGradeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage unavailable (private mode, quota) — grade still applies
      // for this session via state, just doesn't persist.
    }
  }, []);

  const toggleGrade = useCallback(() => {
    setGrade(grade === "night" ? "day" : "night");
  }, [grade, setGrade]);

  return { grade, setGrade, toggleGrade, isDay: grade === "day", isNight: grade === "night" };
}
