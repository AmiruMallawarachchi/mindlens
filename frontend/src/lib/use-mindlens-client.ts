"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  completeOnboarding as apiCompleteOnboarding,
  fetchMe,
  getAccessToken,
  login as apiLogin,
  logoutLocal,
  register as apiRegister,
  updateMe,
  type RegisterInput,
} from "./api";
import { PREVIEW_MODE, PREVIEW_USER } from "./preview";
import type { OnboardingInput, UserProfile } from "./types";
import { useChatAppearance } from "./use-chat-appearance";
import { useChatFrames } from "./use-chat-frames";
import { useChatPresentation } from "./use-chat-presentation";
import { useChatRuntime } from "./use-chat-runtime";
import { useChatSessions } from "./use-chat-sessions";

export type AuthStatus = "checking" | "anonymous" | "onboarding" | "ready";

/**
 * Composes authentication, chat runtime, session, appearance, and presentation
 * hooks into the stable client API consumed by the app.
 */
export function useMindLensClient() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  const frames = useChatFrames();
  const sessions = useChatSessions(frames.clearForPreview);
  const runtime = useChatRuntime(authStatus, frames, sessions);
  const appearance = useChatAppearance(authStatus);
  const resetFramesForLogout = frames.resetForLogout;
  const resetSessionsForLogout = sessions.resetForLogout;
  const presentation = useChatPresentation(
    frames,
    appearance.paletteMode,
    appearance.manualPalette,
  );

  // --- Auth bootstrap: verify a stored token before showing the app -------
  useEffect(() => {
    if (PREVIEW_MODE) {
      setUser(PREVIEW_USER);
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

  /** Rename yourself and refresh local UI state without reloading. */
  const saveNickname = useCallback(async (nickname: string) => {
    const profile = await updateMe({ nickname });
    setUser(profile);
  }, []);

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
      // New accounts pass through onboarding before entering chat.
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
    resetFramesForLogout();
    resetSessionsForLogout();
    logoutLocal();
    setUser(null);
    setAuthStatus("anonymous");
  }, [resetFramesForLogout, resetSessionsForLogout]);

  return {
    authStatus,
    user,
    authError,
    authBusy,
    login,
    register,
    completeOnboarding,
    logout,
    connectionStatus: frames.connectionStatus,
    messages: frames.messages,
    thinking: frames.thinking,
    thinkingSteps: presentation.thinkingSteps,
    liveStages: frames.liveStages,
    activeAgents: frames.activeAgents,
    liveEos: frames.liveEos,
    reading: presentation.reading,
    paletteReading: presentation.paletteReading,
    crisis: frames.crisis,
    dismissCrisis: () => frames.setCrisis(null),
    sendMessage: runtime.sendMessage,
    regenerate: runtime.regenerate,
    sessions: sessions.sessions,
    activeSessionId: sessions.activeSessionId,
    startNewConversation: sessions.startNewConversation,
    openSession: sessions.openSession,
    pinSession: sessions.pinSession,
    renameSession: sessions.renameSession,
    deleteSession: sessions.deleteSession,
    pendingJournalPrompt: sessions.pendingJournalPrompt,
    prepareJournalReflection: sessions.prepareJournalReflection,
    clearJournalPrompt: sessions.clearJournalPrompt,
    previewMode: PREVIEW_MODE,
    companionId: appearance.companionId,
    companionName: appearance.companionName,
    applyCompanionPreference: appearance.applyCompanionPreference,
    applyPalettePreference: appearance.applyPalettePreference,
    intensityCap: appearance.intensityCap,
    applyIntensityCap: appearance.applyIntensityCap,
    saveNickname,
  };
}

export type MindLensClient = ReturnType<typeof useMindLensClient>;
