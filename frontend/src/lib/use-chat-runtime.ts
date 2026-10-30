"use client";

import { useCallback, useEffect } from "react";
import {
  createSession,
  fetchMe,
  getAccessToken,
  getSession,
  listSessions,
  refreshAccessToken,
} from "./api";
import { MindLensSocket } from "./websocket";
import { PREVIEW_MODE, PREVIEW_MESSAGES, PREVIEW_SESSIONS } from "./preview";
import { hydrateMessages, makeId } from "./chat-client-utils";
import type { useChatFrames } from "./use-chat-frames";
import type { useChatSessions } from "./use-chat-sessions";

type AuthStatus = "checking" | "anonymous" | "onboarding" | "ready";
type ChatFrames = ReturnType<typeof useChatFrames>;
type ChatSessions = ReturnType<typeof useChatSessions>;

export function useChatRuntime(
  authStatus: AuthStatus,
  frames: ChatFrames,
  sessions: ChatSessions,
) {
  const {
    messagesRef, socketRef, thinkingStartRef, setMessages, setCrisis, setThinking,
    setActiveAgents, setLiveEos, setLiveMemory, setLiveStages,
    setConnectionStatus, handleFrame, streamingIdRef,
  } = frames;
  const {
    setActiveSessionId, setSessions, requestedSessionId, sessionEpoch, refreshSessions,
  } = sessions;

  useEffect(() => {
    if (authStatus !== "ready" || !PREVIEW_MODE) return;
    setMessages(PREVIEW_MESSAGES);
    setSessions(PREVIEW_SESSIONS);
    setActiveSessionId(PREVIEW_SESSIONS[0].session_id);
  }, [authStatus, setMessages, setSessions, setActiveSessionId]);

  useEffect(() => {
    if (authStatus !== "ready") return;
    // Preview mode has no backend to open a session against.
    if (PREVIEW_MODE) return;
    let cancelled = false;

    setMessages([]);
    setCrisis(null);
    setThinking(false);
    setActiveAgents([]);
    setLiveEos(null);
    setLiveMemory([]);
    streamingIdRef.current = null;

    (async () => {
      let targetId = requestedSessionId;
      if (targetId) {
        // Opening a past conversation: hydrate its transcript before the
        // socket connects, so the reconnect-on-mount doesn't show an empty
        // chat while the fetch is still in flight.
        const detail = await getSession(targetId);
        if (cancelled) return;
        setMessages(hydrateMessages(detail.turns));
      } else {
        // No specific session requested — either a fresh mount, or "New
        // conversation" while already on one. Either way, reuse the most
        // recent session if it's still empty rather than creating another:
        // otherwise every reload (and every "New conversation" click on an
        // already-empty chat) left one more untouched session behind,
        // inflating the sidebar and dashboard.py's session_count gate.
        const existing = await listSessions();
        if (cancelled) return;
        const reusable = existing[0]?.turn_count === 0 ? existing[0] : null;
        targetId = reusable ? reusable.session_id : (await createSession()).session_id;
        if (cancelled) return;
      }

      setActiveSessionId(targetId);
      refreshSessions();

      // The WebSocket auths once at handshake and is never re-checked (see
      // chat.py: token is verified on connect only), so unlike a REST call
      // it can't recover from an expired access token by itself. A cheap
      // authenticated call first guarantees `request()`'s 401-refresh path
      // (lib/api.ts) has run and localStorage holds a live token before the
      // socket reads it — otherwise reopening chat after >15 minutes idle
      // (a reload, or switching sessions) would hand the socket a token
      // that's already dead on arrival.
      try {
        await fetchMe();
      } catch {
        // Both tokens are gone — the mount-time auth check will already be
        // routing this user back to the login screen; nothing to connect to.
        return;
      }
      if (cancelled) return;

      if (!getAccessToken()) return;
      const socket = new MindLensSocket(
        targetId,
        getAccessToken,
        {
          onFrame: handleFrame,
          onStatusChange: setConnectionStatus,
        },
        refreshAccessToken,
      );
      socketRef.current = socket;
      socket.connect();
    })().catch((err) => {
      console.error("Failed to open session", err);
    });

    return () => {
      cancelled = true;
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [authStatus, sessionEpoch, requestedSessionId, handleFrame, refreshSessions, setMessages, setCrisis, setThinking, setActiveAgents, setLiveEos, setLiveMemory, setActiveSessionId, setConnectionStatus, socketRef, streamingIdRef]);

  const sendMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((current) => [
      ...current,
      { id: makeId(), role: "user", text: trimmed },
    ]);
    if (!socketRef.current) return;
    setThinking(true);
    setLiveStages([]);
    thinkingStartRef.current = Date.now();
    socketRef.current.sendMessage(trimmed);
  }, [setMessages, socketRef, setThinking, setLiveStages, thinkingStartRef]);

  /** Resend the last user message for a fresh reply. */
  const regenerate = useCallback(() => {
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!lastUser || !socketRef.current) return;
    setThinking(true);
    setLiveStages([]);
    thinkingStartRef.current = Date.now();
    socketRef.current.sendMessage(lastUser.text);
  }, [messagesRef, socketRef, setThinking, setLiveStages, thinkingStartRef]);

  return { sendMessage, regenerate };
}
