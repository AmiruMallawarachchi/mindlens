"use client";

/**
 * Loads the user's preferences once per settings section and tracks a local
 * draft against the saved copy, so "Save changes" can be disabled until
 * something actually changed and the user gets told what state they're in.
 *
 * Each section only ever sends its own fields; the backend now merges via
 * dotted paths, so this can't clobber preferences another section owns.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchMemory, updateMemoryPreferences } from "@/lib/api";
import type { MemoryPreferences } from "@/lib/types";

export function usePrefs() {
  const [saved, setSaved] = useState<MemoryPreferences | null>(null);
  const [draft, setDraft] = useState<MemoryPreferences>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMemory()
      .then((doc) => {
        if (cancelled) return;
        setSaved(doc.preferences ?? {});
        setDraft(doc.preferences ?? {});
      })
      .catch(() => {
        // No memory doc yet (pre-onboarding). Controls still work; there's
        // just nothing to prefill from.
        if (!cancelled) setSaved({});
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const set = useCallback(<K extends keyof MemoryPreferences>(key: K, value: MemoryPreferences[K]) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setJustSaved(false);
  }, []);

  /** Persist only the named keys — never the whole draft, so a section can't
   * write fields it doesn't own. */
  const save = useCallback(
    async (keys: (keyof MemoryPreferences)[]) => {
      setSaving(true);
      setError(null);
      try {
        const payload: MemoryPreferences = {};
        for (const key of keys) {
          if (draft[key] !== undefined) {
            (payload as Record<string, unknown>)[key as string] = draft[key];
          }
        }
        await updateMemoryPreferences(payload);
        setSaved((s) => ({ ...(s ?? {}), ...payload }));
        setJustSaved(true);
      } catch {
        setError("Couldn't save that. Check your connection and try again.");
      } finally {
        setSaving(false);
      }
    },
    [draft],
  );

  /** True when any of the named keys differs from what's on the server. */
  const isDirty = useCallback(
    (keys: (keyof MemoryPreferences)[]) =>
      keys.some((key) => (draft[key] ?? "") !== ((saved ?? {})[key] ?? "")),
    [draft, saved],
  );

  return { draft, set, save, isDirty, loading, saving, justSaved, error };
}
