"use client";

/**
 * Sidebar collapse (full 262px vs icon-only rail) — persisted the same way
 * as useGrade, so the choice survives navigation between Chat and the
 * Progress/Journal/Memory/Your Mindlens pages instead of resetting per view.
 */

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ml-sidebar-collapsed";

function readStored(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function useSidebarCollapsed() {
  const [collapsed, setCollapsedState] = useState(false);

  useEffect(() => {
    setCollapsedState(readStored());
  }, []);

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // Private mode / quota — still applies for this session via state.
    }
  }, []);

  const toggle = useCallback(() => {
    setCollapsed(!collapsed);
  }, [collapsed, setCollapsed]);

  return { collapsed, setCollapsed, toggle };
}
