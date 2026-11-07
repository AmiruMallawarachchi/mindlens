"use client";

/**
 * Day/night grade toggle — shared between Home, the app shell, the secondary
 * pages and Settings > Appearance, so the choice is one setting, not four.
 *
 * The store is module-level on purpose. When each caller held its own
 * `useState`, every mounted consumer wrote `data-grade` from its own stale
 * copy: toggling from the chat header flipped the room, then moving any other
 * control in the Appearance panel re-applied that panel's copy and snapped the
 * grade back. One writer, one source of truth, subscribers re-render.
 */

import { useSyncExternalStore } from "react";

export type Grade = "day" | "night";
/** What's stored/chosen: a real grade, or "auto" to follow the OS. */
export type GradeMode = Grade | "auto";

const STORAGE_KEY = "ml-grade";
// During SSR/hydration the grade reads as this, then syncs from storage on the
// first client effect — same trick the per-instance version used, so no
// hydration mismatch and no visible flash at this app's size.
const SERVER_MODE: GradeMode = "auto";
const SERVER_GRADE: Grade = "day";

function systemGrade(): Grade {
  if (typeof window === "undefined") return SERVER_GRADE;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
}

function readStoredMode(): GradeMode {
  if (typeof window === "undefined") return SERVER_MODE;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "night" || stored === "day" || stored === "auto" ? stored : "auto";
  } catch {
    // Storage unavailable (private mode, quota) — the session default stands.
    return "auto";
  }
}

let mode: GradeMode = SERVER_MODE;
let grade: Grade = SERVER_GRADE;
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

// Stable identity: an inline subscribe would change every render and make
// React detach and reattach the listener on each one.
function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

function applyGrade(next: Grade) {
  grade = next;
  document.documentElement.setAttribute("data-grade", next);
  notify();
}

function resolve() {
  applyGrade(mode === "auto" ? systemGrade() : mode);
}

function setMode(next: GradeMode) {
  mode = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Still applies for this session through the store, just doesn't persist.
  }
  resolve();
}

if (typeof window !== "undefined") {
  mode = readStoredMode();
  resolve();

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (mode === "auto") resolve();
  });

  // Another tab changed the setting.
  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    mode = readStoredMode();
    resolve();
  });
}

export function useGrade() {
  const currentMode = useSyncExternalStore(subscribe, () => mode, () => SERVER_MODE);
  const currentGrade = useSyncExternalStore(subscribe, () => grade, () => SERVER_GRADE);

  return {
    mode: currentMode,
    setMode,
    toggleGrade: () => setMode(currentGrade === "night" ? "day" : "night"),
    isDay: currentGrade === "day",
  };
}
