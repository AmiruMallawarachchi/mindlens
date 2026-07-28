"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createSession,
  fetchMe,
  getAccessToken,
  getSession,
  listSessions,
  login as apiLogin,
  logoutLocal,
  register as apiRegister,
  type RegisterInput,
} from "./api";
import { MindLensSocket } from "./websocket";
import type {
  ChatMessage,
  ConnectionStatus,
  CrisisResource,
  EosSnapshot,
  ServerFrame,
  SessionListItem,
  SessionTurn,
  UserProfile,
} from "./types";

export type AuthStatus = "checking" | "anonymous" | "ready";

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Turns a stored session_id's turns (chat.py::_save_turn's shape) into the
 * same ChatMessage[] shape a live conversation builds up. */
function hydrateMessages(turns: SessionTurn[]): ChatMessage[] {
  return turns.map((turn, index) => ({
    id: `${turn.timestamp}-${index}`,
    role: turn.role,
    text: turn.text,
    eos: turn.eos_snapshot,
    agentsUsed: turn.agents_used,
    crisis: turn.crisis_flag,
  }));
}

/**
 * Owns the whole client-side lifecycle: bootstrap auth from a stored token,
 * open a backend session, connect the WebSocket, and expose chat state.
 * One instance per mounted app — ChatView etc. are pure render of this.
 */
export function useMindLensClient() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [liveEos, setLiveEos] = useState<EosSnapshot | null>(null);
  const [crisis, setCrisis] = useState<{
    text: string;
    resources: CrisisResource[];
  } | null>(null);

  const socketRef = useRef<MindLensSocket | null>(null);
  const streamingIdRef = useRef<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  // null = create a fresh session; a string = open that existing one.
  // Re-requesting the session already open (same id, or null while already on
  // a fresh one) wouldn't change this value, so sessionEpoch exists purely to
  // force "New conversation" to actually create a new session in that case.
  const [requestedSessionId, setRequestedSessionId] = useState<string | null>(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);

  const refreshSessions = useCallback(() => {
    listSessions()
      .then(setSessions)
      .catch((err) => console.error("Failed to list sessions", err));
  }, []);

  const handleFrame = useCallback((frame: ServerFrame) => {
    switch (frame.type) {
      case "thinking_update":
        setThinking(true);
        setActiveAgents(frame.agents_active ?? []);
        setLiveEos(frame.eos ?? null);
        break;

      case "stream_chunk": {
        // Backend streaming.py sends chunks purely for a typing effect, then
        // re-sends the complete verified text in "response". Chunks build a
        // provisional bubble; "response" below replaces it with the
        // authoritative text rather than trusting the reassembly.
        if (!streamingIdRef.current) {
          const id = makeId();
          streamingIdRef.current = id;
          setMessages((current) => [
            ...current,
            { id, role: "assistant", text: frame.chunk, pending: true },
          ]);
        } else {
          const id = streamingIdRef.current;
          setMessages((current) =>
            current.map((m) =>
              m.id === id ? { ...m, text: m.text + frame.chunk } : m,
            ),
          );
        }
        break;
      }

      case "response": {
        const id = streamingIdRef.current ?? makeId();
        streamingIdRef.current = null;
        setMessages((current) => {
          const finalized: ChatMessage = {
            id,
            role: "assistant",
            text: frame.text,
            eos: frame.eos_snapshot,
            agentsUsed: frame.agents_used,
            degraded: frame.degraded,
            pending: false,
          };
          const exists = current.some((m) => m.id === id);
          return exists
            ? current.map((m) => (m.id === id ? finalized : m))
            : [...current, finalized];
        });
        setThinking(false);
        setActiveAgents([]);
        break;
      }

      case "crisis_response":
        streamingIdRef.current = null;
        setMessages((current) => [
          ...current,
          { id: makeId(), role: "assistant", text: frame.text, crisis: true },
        ]);
        setCrisis({ text: frame.text, resources: frame.resources });
        setThinking(false);
        setActiveAgents([]);
        break;

      case "checkin":
        setMessages((current) => [
          ...current,
          { id: makeId(), role: "assistant", text: frame.text },
        ]);
        break;

      case "error":
        setThinking(false);
        setMessages((current) => [
          ...current,
          { id: makeId(), role: "assistant", text: frame.detail, kind: "error" },
        ]);
        break;

      case "stream_end":
      case "pong":
        break;
    }
  }, []);

  // --- Auth bootstrap: verify a stored token before showing the app -------
  useEffect(() => {
    let cancelled = false;
    const token = getAccessToken();
    if (!token) {
      setAuthStatus("anonymous");
      return;
    }
    fetchMe()
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setAuthStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        logoutLocal();
        setAuthStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // --- Session + socket lifecycle ------------------------------------------
  useEffect(() => {
    if (authStatus !== "ready") return;
    let cancelled = false;

    setMessages([]);
    setCrisis(null);
    setThinking(false);
    setActiveAgents([]);
    setLiveEos(null);
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
        const created = await createSession();
        if (cancelled) return;
        targetId = created.session_id;
      }

      setActiveSessionId(targetId);
      refreshSessions();

      const token = getAccessToken();
      if (!token) return;
      const socket = new MindLensSocket(targetId, token, {
        onFrame: handleFrame,
        onStatusChange: setConnectionStatus,
      });
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
  }, [authStatus, sessionEpoch, requestedSessionId, handleFrame, refreshSessions]);

  const sendMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !socketRef.current) return;
    setMessages((current) => [
      ...current,
      { id: makeId(), role: "user", text: trimmed },
    ]);
    setThinking(true);
    socketRef.current.sendMessage(trimmed);
  }, []);

  const startNewConversation = useCallback(() => {
    setRequestedSessionId(null);
    // Forces the effect to rerun even when it was already targeting "new"
    // (requestedSessionId unchanged) or reopening the session already active.
    setSessionEpoch((epoch) => epoch + 1);
  }, []);

  const openSession = useCallback(
    (sessionId: string) => {
      if (sessionId === activeSessionId) return;
      setRequestedSessionId(sessionId);
    },
    [activeSessionId],
  );

  const login = useCallback(async (email: string, password: string) => {
    setAuthBusy(true);
    setAuthError(null);
    try {
      await apiLogin({ email, password });
      const profile = await fetchMe();
      setUser(profile);
      setAuthStatus("ready");
    } catch (err) {
      setAuthError(err instanceof ApiError ? err.message : "Could not sign in.");
    } finally {
      setAuthBusy(false);
    }
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    setAuthBusy(true);
    setAuthError(null);
    try {
      await apiRegister(input);
      const profile = await fetchMe();
      setUser(profile);
      setAuthStatus("ready");
    } catch (err) {
      setAuthError(
        err instanceof ApiError ? err.message : "Could not create your account.",
      );
    } finally {
      setAuthBusy(false);
    }
  }, []);

  const logout = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    logoutLocal();
    setUser(null);
    setMessages([]);
    setCrisis(null);
    setConnectionStatus("idle");
    setAuthStatus("anonymous");
    setSessions([]);
    setActiveSessionId(null);
    setRequestedSessionId(null);
  }, []);

  return {
    authStatus,
    user,
    authError,
    authBusy,
    login,
    register,
    logout,
    connectionStatus,
    messages,
    thinking,
    activeAgents,
    liveEos,
    crisis,
    dismissCrisis: () => setCrisis(null),
    sendMessage,
    sessions,
    activeSessionId,
    startNewConversation,
    openSession,
  };
}

export type MindLensClient = ReturnType<typeof useMindLensClient>;
