"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createSession,
  fetchMe,
  getAccessToken,
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
  UserProfile,
} from "./types";

export type AuthStatus = "checking" | "anonymous" | "ready";

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
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
  // Bumping this tears down and re-runs the session+socket effect below.
  const [sessionEpoch, setSessionEpoch] = useState(0);

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

    createSession()
      .then((session) => {
        if (cancelled) return;
        const token = getAccessToken();
        if (!token) return;
        const socket = new MindLensSocket(session.session_id, token, {
          onFrame: handleFrame,
          onStatusChange: setConnectionStatus,
        });
        socketRef.current = socket;
        socket.connect();
      })
      .catch((err) => {
        console.error("Failed to start a session", err);
      });

    return () => {
      cancelled = true;
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [authStatus, sessionEpoch, handleFrame]);

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
    setMessages([]);
    setCrisis(null);
    setThinking(false);
    setActiveAgents([]);
    setLiveEos(null);
    streamingIdRef.current = null;
    setSessionEpoch((epoch) => epoch + 1);
  }, []);

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
    startNewConversation,
  };
}

export type MindLensClient = ReturnType<typeof useMindLensClient>;
