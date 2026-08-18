"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  completeOnboarding as apiCompleteOnboarding,
  createSession,
  deleteSession as apiDeleteSession,
  fetchMe,
  fetchMemory,
  getAccessToken,
  getSession,
  listSessions,
  login as apiLogin,
  logoutLocal,
  pinSession as apiPinSession,
  renameSession as apiRenameSession,
  register as apiRegister,
  updateMe,
  type RegisterInput,
} from "./api";
import { DEFAULT_COMPANION_ID, getCompanion, type CompanionId } from "./companions";
import { MindLensSocket } from "./websocket";
import {
  EMOTION_STATES,
  resolveEmotion,
  RESTING_READING,
  type EmotionId,
  type EmotionReading,
} from "./emotion";
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
  OnboardingInput,
  ServerFrame,
  SessionListItem,
  SessionTurn,
  UserProfile,
} from "./types";

export type AuthStatus = "checking" | "anonymous" | "onboarding" | "ready";

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

  // The user's chosen companion (lib/companions.ts) — defaults to Ember
  // until (if) the real preference loads, so chat never waits on this fetch.
  const [companionId, setCompanionId] = useState<CompanionId>(DEFAULT_COMPANION_ID);
  const [companionName, setCompanionName] = useState<string>(getCompanion(DEFAULT_COMPANION_ID).name);
  // Settings > Appearance > Colour. "manual" pins the room's palette so it
  // stops tracking the conversation; the read itself is unaffected.
  const [paletteMode, setPaletteMode] = useState<"auto" | "manual">("auto");
  const [manualPalette, setManualPalette] = useState<EmotionId>("calm");
  // Settings > Appearance > Intensity — caps field opacity, glow radius,
  // companion amplitude and accent saturation together (design.md §2).
  const [intensityCap, setIntensityCap] = useState<number>(1);

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
  // Set by the sidebar's "Save to Journal" action, read by JournalPage to
  // open its composer pre-filled — a reflection prompt referencing the
  // conversation, not the raw transcript (the user writes their own words).
  const [pendingJournalPrompt, setPendingJournalPrompt] = useState<string | null>(null);
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
            memoryRecalled: frame.memory_recalled ?? [],
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
        setAuthStatus(profile.onboarding_complete ? "ready" : "onboarding");
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

  // --- Companion preference: fetched once, so chat renders the user's
  // actual chosen shape/name instead of always defaulting to Ember. -------
  useEffect(() => {
    if (authStatus !== "ready" || PREVIEW_MODE) return;
    let cancelled = false;
    fetchMemory()
      .then((doc) => {
        if (cancelled) return;
        const id = getCompanion(doc.preferences?.companion_id).id;
        setCompanionId(id);
        setCompanionName(doc.preferences?.companion_name || getCompanion(id).name);
        setPaletteMode(doc.preferences?.palette_mode === "manual" ? "manual" : "auto");
        if (doc.preferences?.manual_palette && doc.preferences.manual_palette in EMOTION_STATES) {
          setManualPalette(doc.preferences.manual_palette as EmotionId);
        }
        if (typeof doc.preferences?.intensity_cap === "number") {
          setIntensityCap(doc.preferences.intensity_cap);
        }
      })
      .catch(() => {
        // No memory doc yet, or the fetch failed — the Ember default stands.
      });
    return () => {
      cancelled = true;
    };
  }, [authStatus]);

  /** Settings calls this right after a successful save, so chat reflects the
   * new companion immediately instead of waiting on a refetch. */
  const applyCompanionPreference = useCallback((id: CompanionId, name: string) => {
    setCompanionId(id);
    setCompanionName(name);
  }, []);

  /** Same contract as applyCompanionPreference: settings saved it, so the
   * room must reflect it now rather than on the next mount. Without this the
   * preference persists correctly but the colour visibly doesn't change,
   * which reads as the control being broken. */
  const applyPalettePreference = useCallback((mode: "auto" | "manual", palette: EmotionId) => {
    setPaletteMode(mode);
    setManualPalette(palette);
  }, []);

  /** Same contract — applied immediately on save rather than waiting on a
   * refetch, so dragging the slider down visibly calms the room right away. */
  const applyIntensityCap = useCallback((cap: number) => {
    setIntensityCap(cap);
  }, []);

  /** Rename yourself. Updates the user record and refreshes local state so
   * the sidebar and greeting change without a reload. */
  const saveNickname = useCallback(async (nickname: string) => {
    const profile = await updateMe({ nickname });
    setUser(profile);
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

  const login = useCallback(async (email: string, password: string) => {
    setAuthBusy(true);
    setAuthError(null);
    try {
      await apiLogin({ email, password });
      const profile = await fetchMe();
      setUser(profile);
      setAuthStatus(profile.onboarding_complete ? "ready" : "onboarding");
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
      // register() always creates the account with onboarding_complete:
      // false — the onboarding wizard is what creates the user_memory
      // document personalization depends on, so every new account passes
      // through it once before reaching chat.
      setAuthStatus(profile.onboarding_complete ? "ready" : "onboarding");
    } catch (err) {
      setAuthError(
        err instanceof ApiError ? err.message : "Could not create your account.",
      );
    } finally {
      setAuthBusy(false);
    }
  }, []);

  const completeOnboarding = useCallback(async (input: OnboardingInput) => {
    setAuthBusy(true);
    setAuthError(null);
    try {
      const profile = await apiCompleteOnboarding(input);
      setUser(profile);
      setAuthStatus("ready");
    } catch (err) {
      setAuthError(
        err instanceof ApiError ? err.message : "Could not finish setting up your space.",
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

  /** What the room is *coloured* from — deliberately separate from `reading`,
   * which is what the UI *says* it read. In manual mode the classifier still
   * runs and the read strip still shows its verdict; only the colour is
   * pinned. Crisis always wins and freezes the field to neutral. */
  const paletteReading: EmotionReading = useMemo(() => {
    if (crisis || paletteMode !== "manual") return reading;
    const state = EMOTION_STATES[manualPalette];
    return { ...reading, state, blend: null, coreState: null, subs: state.subs, resting: false };
  }, [reading, crisis, paletteMode, manualPalette]);

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
    completeOnboarding,
    logout,
    connectionStatus,
    messages,
    thinking,
    thinkingSteps,
    activeAgents,
    liveEos,
    reading,
    paletteReading,
    crisis,
    dismissCrisis: () => setCrisis(null),
    sendMessage,
    regenerate,
    sessions,
    activeSessionId,
    startNewConversation,
    openSession,
    pinSession,
    renameSession,
    deleteSession,
    pendingJournalPrompt,
    prepareJournalReflection,
    clearJournalPrompt,
    previewMode: PREVIEW_MODE,
    companionId,
    companionName,
    applyCompanionPreference,
    applyPalettePreference,
    intensityCap,
    applyIntensityCap,
    saveNickname,
  };
}

export type MindLensClient = ReturnType<typeof useMindLensClient>;
