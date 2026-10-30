"use client";

import { useMemo } from "react";
import { EMOTION_STATES, resolveEmotion, RESTING_READING, type EmotionId, type EmotionReading } from "./emotion";
import { buildReasoningTrail, type ReasoningStep } from "./reasoning";
import type { EosSnapshot } from "./types";
import type { useChatFrames } from "./use-chat-frames";

type Frames = ReturnType<typeof useChatFrames>;

export function useChatPresentation(
  frames: Pick<Frames, "messages" | "liveEos" | "crisis" | "thinking" | "activeAgents" | "liveSafety" | "liveMemory" | "liveDegraded" | "liveTelemetry">,
  paletteMode: "auto" | "manual",
  manualPalette: EmotionId,
) {
  const { messages, liveEos, crisis, thinking, activeAgents, liveSafety, liveMemory, liveDegraded, liveTelemetry } = frames;
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
      crisis: liveSafety?.is_crisis ?? false,
      memoryRecalled: liveMemory,
      degraded: liveDegraded,
      telemetry: liveTelemetry,
      safety: liveSafety,
    });
  }, [
    thinking,
    liveEos,
    activeAgents,
    liveMemory,
    liveDegraded,
    liveTelemetry,
    liveSafety,
  ]);

  return { reading, paletteReading, thinkingSteps };
}
