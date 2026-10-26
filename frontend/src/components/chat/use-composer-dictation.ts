"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type SpeechResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };
type SpeechResultEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

const VOICE_NOTICE_KEY = "ml-voice-notice-ack";

function speechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const scope = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function useComposerDictation(onTypingChange?: (typing: boolean) => void) {
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [showVoiceNotice, setShowVoiceNotice] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => setVoiceSupported(speechRecognitionCtor() !== null), []);
  const stopDictation = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setListening(false);
  }, []);
  useEffect(() => () => recognitionRef.current?.stop(), []);

  const startDictation = useCallback(() => {
    const Recognition = speechRecognitionCtor();
    if (!Recognition) return;
    setVoiceError(null);
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = navigator.language || "en-US";
    recognition.onresult = (event) => {
      let settled = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) settled += result[0].transcript;
      }
      if (!settled.trim()) return;
      setDraft((current) => {
        const next = current.trim()
          ? `${current.trimEnd()} ${settled.trim()}`
          : settled.trim();
        onTypingChange?.(next.length > 0);
        return next;
      });
    };
    recognition.onerror = (event) => {
      setVoiceError(
        event.error === "not-allowed"
          ? "Microphone access was blocked. Allow it in your browser to dictate."
          : "Dictation stopped unexpectedly — keep typing, nothing was lost.",
      );
      stopDictation();
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
    };
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, [onTypingChange, stopDictation]);

  const handleMicClick = () => {
    if (listening) {
      stopDictation();
      return;
    }
    if (window.localStorage.getItem(VOICE_NOTICE_KEY) !== "1") {
      setShowVoiceNotice(true);
      return;
    }
    startDictation();
  };
  const acceptVoiceNotice = () => {
    window.localStorage.setItem(VOICE_NOTICE_KEY, "1");
    setShowVoiceNotice(false);
    startDictation();
  };

  return {
    draft,
    setDraft,
    listening,
    voiceSupported,
    showVoiceNotice,
    setShowVoiceNotice,
    voiceError,
    handleMicClick,
    acceptVoiceNotice,
    stopDictation,
  };
}
