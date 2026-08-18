"use client";

/**
 * Read-aloud for an assistant turn, via the browser's SpeechSynthesis API.
 *
 * This is the counterpart to the composer's dictation, and the privacy
 * trade-off is genuinely different in a way worth stating rather than
 * assuming. Dictation sends your *voice* to the browser vendor. Synthesis
 * sends *text you are already looking at* — and on most platforms the
 * default voices are installed locally and nothing leaves the device at all.
 * Some browsers do offer higher-quality network voices; where they exist
 * they are opt-in per voice, and this hook never selects one, so the default
 * path stays local. That's why this needs no disclosure step where the mic
 * did.
 *
 * Only one utterance plays at a time across the whole app — a second Read
 * aloud cancels the first rather than talking over it.
 */

import { useCallback, useEffect, useRef, useState } from "react";

function synth(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  return window.speechSynthesis ?? null;
}

export function useReadAloud(text: string) {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Detection waits for the client: there is no window during SSR, and
  // rendering the control then removing it would flicker.
  useEffect(() => setSupported(synth() !== null), []);

  const stop = useCallback(() => {
    synth()?.cancel();
    utteranceRef.current = null;
    setSpeaking(false);
  }, []);

  // A turn can unmount mid-sentence (new conversation, navigation). Without
  // this the voice keeps talking about a message no longer on screen.
  useEffect(() => stop, [stop]);

  const toggle = useCallback(() => {
    const speech = synth();
    if (!speech || !text.trim()) return;

    if (speech.speaking || speech.pending) {
      // Covers both "stop this one" and "stop whichever other turn is
      // talking" — cancel() is global, which is the behaviour we want.
      stop();
      if (utteranceRef.current) return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    // Slightly under default: the default cadence reads briskly, which is
    // the wrong register for a reply someone may be upset while hearing.
    utterance.rate = 0.95;
    utterance.onend = () => {
      utteranceRef.current = null;
      setSpeaking(false);
    };
    utterance.onerror = () => {
      utteranceRef.current = null;
      setSpeaking(false);
    };

    utteranceRef.current = utterance;
    speech.speak(utterance);
    setSpeaking(true);
  }, [text, stop]);

  return { supported, speaking, toggle };
}
