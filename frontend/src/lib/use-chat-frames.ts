"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { makeId } from "./chat-client-utils";
import type {
  ChatMessage,
  ConnectionStatus,
  CrisisResource,
  EosSnapshot,
  SafetyVerdict,
  ServerFrame,
  TurnTelemetry,
} from "./types";
import type { MindLensSocket } from "./websocket";

export function useChatFrames() {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [liveEos, setLiveEos] = useState<EosSnapshot | null>(null);
  const [liveMemory, setLiveMemory] = useState<string[]>([]);
  // The live trail used to hardcode crisis:false and degraded:[], so it
  // structurally could not report a problem while one was happening.
  const [liveTelemetry, setLiveTelemetry] = useState<TurnTelemetry | null>(null);
  const [liveSafety, setLiveSafety] = useState<SafetyVerdict | null>(null);
  const [liveDegraded, setLiveDegraded] = useState<string[]>([]);
  // Filled in one entry at a time as `stage_update` frames arrive *during*
  // the pipeline, before thinking_update. thinking_update itself is sent
  // only once the whole pipeline has already finished, so before this the
  // client had nothing real to show while a turn was actually running —
  // the trail simply appeared complete the moment it existed at all.
  const [liveStages, setLiveStages] = useState<{ stage: string; detail: string }[]>([]);
  const [crisis, setCrisis] = useState<{
    text: string;
    resources: CrisisResource[];
  } | null>(null);

  const socketRef = useRef<MindLensSocket | null>(null);
  const streamingIdRef = useRef<string | null>(null);
  // Real wall-clock elapsed time for the trail's "Thought for Ns"
  // trigger. The persisted trail (message-flow.tsx) renders in a fresh
  // <Reasoning> instance that never itself observes a streaming
  // transition, so without this it always fell back to a generic
  // "quick thought" regardless of how long the turn actually took.
  const thinkingStartRef = useRef<number | null>(null);
  // Mirror of `messages` for callbacks that need to read without
  // subscribing (regenerate reads the last user turn at click time).
  const messagesRef = useRef<ChatMessage[]>([]);


  const handleFrame = useCallback((frame: ServerFrame) => {
    switch (frame.type) {
      case "stage_update": {
        setThinking(true);
        setLiveStages((current) => [...current, { stage: frame.stage, detail: frame.detail }]);
        break;
      }
      case "thinking_update": {
        setThinking(true);
        setActiveAgents(frame.agents_active ?? []);
        setLiveEos(frame.eos ?? null);
        setLiveMemory(frame.memory_recalled ?? []);
        setLiveTelemetry(frame.telemetry ?? null);
        setLiveSafety(frame.safety ?? null);
        setLiveDegraded(frame.degraded ?? []);
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
        const thinkingDurationS = thinkingStartRef.current
          ? Math.max(1, Math.round((Date.now() - thinkingStartRef.current) / 1000))
          : undefined;
        thinkingStartRef.current = null;
        setMessages((current) => {
          const finalized: ChatMessage = {
            id,
            role: "assistant",
            text: frame.text,
            eos: frame.eos_snapshot,
            agentsUsed: frame.agents_used,
            degraded: frame.degraded,
            memoryRecalled: frame.memory_recalled ?? [],
          telemetry: frame.telemetry,
          safety: frame.safety,
          options: frame.options ?? null,
            pending: false,
            thinkingDurationS,
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

      case "crisis_response": {
        streamingIdRef.current = null;
        const thinkingDurationS = thinkingStartRef.current
          ? Math.max(1, Math.round((Date.now() - thinkingStartRef.current) / 1000))
          : undefined;
        thinkingStartRef.current = null;
        setMessages((current) => [
          ...current,
          { id: makeId(), role: "assistant", text: frame.text, crisis: true, thinkingDurationS },
        ]);
        setCrisis({ text: frame.text, resources: frame.resources });
        setThinking(false);
        setActiveAgents([]);
        break;
      }

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
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const clearForPreview = useCallback(() => {
    setMessages([]);
    setCrisis(null);
  }, []);

  const resetForLogout = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    setMessages([]);
    setCrisis(null);
    setConnectionStatus("idle");
  }, []);

  return {
    connectionStatus, setConnectionStatus, messages, setMessages, thinking, setThinking,
    activeAgents, setActiveAgents, liveEos, setLiveEos, liveMemory, setLiveMemory,
    liveTelemetry, setLiveTelemetry, liveSafety, setLiveSafety, liveDegraded,
    setLiveDegraded, liveStages, setLiveStages, crisis, setCrisis, socketRef,
    streamingIdRef, thinkingStartRef, messagesRef, handleFrame, clearForPreview,
    resetForLogout,
  };
}
