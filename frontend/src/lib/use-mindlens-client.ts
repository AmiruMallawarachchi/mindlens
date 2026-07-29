"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { resolveEmotion, RESTING_READING, type EmotionReading } from "./emotion";
import { buildReasoningTrail, type ReasoningStep } from "./reasoning";
import {
  PREVIEW_MESSAGES,
  PREVIEW_MODE,
  PREVIEW_SESSIONS,
  PREVIEW_USER,
} from "./preview";
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
 * One instance per mounted app — the chat screen is a pure render of this.
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
  const [liveMemory, setLiveMemory] = useState<string[]>([]);
  const [crisis, setCrisis] = useState<{
    text: string;
    resources: CrisisResource[];
  } | null>(null);

  const socketRef = useRef<MindLensSocket | null>(null);
  const streamingIdRef = useRef<string | null>(null);
  // Mirror of `messages` for callbacks that need to read without
  // subscribing (regenerate reads the last user turn at click time).
  const messagesRef = useRef<ChatMessage[]>([]);
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
      case "thinking_update": {
        setThinking(true);
        setActiveAgents(frame.agents_active ?? []);
        setLiveEos(frame.eos ?? null);
        setLiveMemory(frame.memory_recalled ?? []);
        // The read in a thinking_update is the read *of the message the user
        // just sent*, so it belongs to that bubble — that's what the emotion
        // read strip underneath it renders.
        setMessages((current) => {
          const lastUser = [...current].reverse().find((m) => m.role === "user");
          if (!lastUser) return current;
          return current.map((m) =>
            m.id === lastUser.id
              ? { ...m, eos: frame.eos, memoryRecalled: frame.memory_recalled ?? [] }
              : m,
          );
        });
        break;
      }

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
            music: frame.music ?? null,
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
    if (PREVIEW_MODE) {
      setUser(PREVIEW_USER);
      setMessages(PREVIEW_MESSAGES);
      setSessions(PREVIEW_SESSIONS);
      setActiveSessionId(PREVIEW_SESSIONS[0].session_id);
      setAuthStatus("ready");
      return;
    }

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
    if (!trimmed) return;
    setMessages((current) => [
      ...current,
      { id: makeId(), role: "user", text: trimmed },
    ]);
    if (!socketRef.current) return;
    setThinking(true);
    socketRef.current.sendMessage(trimmed);
  }, []);

  /** Resend the last user message for a fresh reply. The previous assistant
   * turn stays in the transcript — the backend has no regenerate endpoint,
   * so this is honest resubmission, not replacement. */
  const regenerate = useCallback(() => {
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!lastUser || !socketRef.current) return;
    setThinking(true);
    socketRef.current.sendMessage(lastUser.text);
  }, []);

  const startNewConversation = useCallback(() => {
    if (PREVIEW_MODE) {
      // The session effect is a no-op in preview, so clear the fixture here —
      // otherwise the empty room state is unreachable while styling it.
      setMessages([]);
      setCrisis(null);
      setActiveSessionId(null);
      return;
    }
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

  // --- Derived: the emotion read that drives the whole room ---------------
  // The most recent snapshot wins, live or settled, so the field keeps
  // tracking the conversation between turns instead of resetting.
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const latestEos = useMemo<EosSnapshot | null>(() => {
    if (liveEos) return liveEos;
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const eos = messages[i].eos;
      if (eos) return eos;
    }
    return null;
  }, [liveEos, messages]);

  const reading: EmotionReading = useMemo(
    () => (crisis ? RESTING_READING : resolveEmotion(latestEos)),
    [latestEos, crisis],
  );

  /** The trail shown while a reply is being composed. */
  const thinkingSteps: ReasoningStep[] = useMemo(() => {
    if (!thinking) return [];
    return buildReasoningTrail({
      eos: liveEos,
      reading: resolveEmotion(liveEos),
      agents: activeAgents,
      crisis: false,
      memoryRecalled: liveMemory,
      degraded: [],
    });
  }, [thinking, liveEos, activeAgents, liveMemory]);

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
    thinkingSteps,
    activeAgents,
    liveEos,
    reading,
    crisis,
    dismissCrisis: () => setCrisis(null),
    sendMessage,
    regenerate,
    sessions,
    activeSessionId,
    startNewConversation,
    openSession,
    previewMode: PREVIEW_MODE,
  };
}

export type MindLensClient = ReturnType<typeof useMindLensClient>;
