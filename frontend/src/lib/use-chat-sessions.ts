"use client";

import { useCallback, useState } from "react";
import {
  deleteSession as apiDeleteSession,
  listSessions,
  pinSession as apiPinSession,
  renameSession as apiRenameSession,
} from "./api";
import { PREVIEW_MODE } from "./preview";
import type { SessionListItem } from "./types";

export function useChatSessions(clearForPreview: () => void) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [pendingJournalPrompt, setPendingJournalPrompt] = useState<string | null>(null);
  const [requestedSessionId, setRequestedSessionId] = useState<string | null>(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);

  const refreshSessions = useCallback(() => {
    listSessions()
      .then(setSessions)
      .catch((err) => console.error("Failed to list sessions", err));
  }, []);

  const startNewConversation = useCallback(() => {
    if (PREVIEW_MODE) {
      // The session effect is a no-op in preview, so clear the fixture here —
      // otherwise the empty room state is unreachable while styling it.
      clearForPreview();
      setActiveSessionId(null);
      return;
    }
    setRequestedSessionId(null);
    // Forces the effect to rerun even when it was already targeting "new"
    // (requestedSessionId unchanged) or reopening the session already active.
    setSessionEpoch((epoch) => epoch + 1);
  }, [clearForPreview]);

  const openSession = useCallback(
    (sessionId: string) => {
      if (sessionId === activeSessionId) return;
      setRequestedSessionId(sessionId);
    },
    [activeSessionId],
  );

  const pinSession = useCallback(async (sessionId: string, pinned: boolean) => {
    // Optimistic: reorder immediately rather than waiting on the round trip,
    // matching session.py's own pinned-first sort so the UI doesn't jump
    // again once refreshSessions() eventually runs.
    setSessions((current) =>
      [...current]
        .map((s) => (s.session_id === sessionId ? { ...s, pinned } : s))
        .sort(
          (a, b) =>
            Number(b.pinned) - Number(a.pinned) ||
            new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
        ),
    );
    try {
      await apiPinSession(sessionId, pinned);
    } catch (err) {
      console.error("Failed to pin session", err);
      refreshSessions();
    }
  }, [refreshSessions]);

  const renameSession = useCallback(
    async (sessionId: string, title: string) => {
      const clean = title.trim();
      if (!clean) return;
      // Optimistic, same as pin — but keep the previous title so a failed
      // rename can put the old one back rather than leaving the sidebar
      // showing a name the server never accepted.
      let previous: string | null = null;
      setSessions((current) =>
        current.map((s) => {
          if (s.session_id !== sessionId) return s;
          previous = s.title;
          return { ...s, title: clean };
        }),
      );
      try {
        await apiRenameSession(sessionId, clean);
      } catch (err) {
        console.error("Failed to rename session", err);
        setSessions((current) =>
          current.map((s) =>
            s.session_id === sessionId ? { ...s, title: previous } : s,
          ),
        );
      }
    },
    [],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      setSessions((current) => current.filter((s) => s.session_id !== sessionId));
      try {
        await apiDeleteSession(sessionId);
      } catch (err) {
        console.error("Failed to delete session", err);
        refreshSessions();
        return;
      }
      // The transcript of a session the user just deleted shouldn't stay on
      // screen — start fresh rather than leave it displayed but unreachable
      // from the sidebar.
      if (sessionId === activeSessionId) {
        startNewConversation();
      }
    },
    [activeSessionId, refreshSessions, startNewConversation],
  );

  const prepareJournalReflection = useCallback((sessionLabel: string) => {
    setPendingJournalPrompt(`Reflecting on "${sessionLabel}" — what's stayed with you since?`);
  }, []);

  const clearJournalPrompt = useCallback(() => setPendingJournalPrompt(null), []);

  const resetForLogout = useCallback(() => {
    setSessions([]);
    setActiveSessionId(null);
    setRequestedSessionId(null);
  }, []);

  return {
    activeSessionId, setActiveSessionId, sessions, setSessions, pendingJournalPrompt,
    requestedSessionId, setRequestedSessionId, sessionEpoch, setSessionEpoch,
    refreshSessions, startNewConversation, openSession, pinSession, renameSession,
    deleteSession, prepareJournalReflection, clearJournalPrompt, resetForLogout,
  };
}
