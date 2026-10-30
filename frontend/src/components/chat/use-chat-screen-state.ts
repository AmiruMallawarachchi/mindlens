"use client";

import { useCallback, useMemo, useState } from "react";
import { capIntensity, RESTING_READING } from "@/lib/emotion";
import { useGrade } from "@/lib/use-grade";
import { useSidebarCollapsed } from "@/lib/use-sidebar-collapsed";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { sessionLabel, type ChatNavView } from "./chat-sidebar";

export function useChatScreenState(
  client: MindLensClient,
  onNavigate: (view: ChatNavView) => void,
) {
  const {
    messages,
    reading: liveReading,
    paletteReading,
    thinking,
    thinkingSteps,
    liveStages,
    crisis,
    dismissCrisis,
    sendMessage,
    regenerate,
    connectionStatus,
    sessions,
    activeSessionId,
    startNewConversation,
    openSession,
    pinSession,
    renameSession,
    deleteSession,
    prepareJournalReflection,
    user,
    previewMode,
    companionId,
    companionName,
    intensityCap,
  } = client;

  const saveToJournal = useCallback(
    (session: (typeof sessions)[number]) => {
      prepareJournalReflection(sessionLabel(session));
      onNavigate("journal");
    },
    [prepareJournalReflection, onNavigate],
  );
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { isDay, toggleGrade } = useGrade();
  const { collapsed: sidebarCollapsed, toggle: toggleSidebar } = useSidebarCollapsed();

  const reading = useMemo(
    () => (crisis ? RESTING_READING : liveReading),
    [liveReading, crisis],
  );
  const paletteColour = useMemo(
    () => (crisis ? RESTING_READING : paletteReading),
    [crisis, paletteReading],
  );
  const activeSession = sessions.find((s) => s.session_id === activeSessionId);
  const title = activeSession?.title ?? "A new conversation";
  const cappedPalette = useMemo(
    () => capIntensity(paletteColour, intensityCap),
    [paletteColour, intensityCap],
  );
  const handleSend = useCallback(
    (text: string) => {
      sendMessage(text);
      setTyping(false);
      setSending(true);
      window.setTimeout(() => setSending(false), 700);
    },
    [sendMessage],
  );
  const lastMessage = messages[messages.length - 1];
  const streamingId = lastMessage?.pending ? lastMessage.id : null;

  return {
    messages,
    thinking,
    thinkingSteps,
    liveStages,
    crisis,
    dismissCrisis,
    regenerate,
    connectionStatus,
    sessions,
    activeSessionId,
    startNewConversation,
    openSession,
    pinSession,
    renameSession,
    deleteSession,
    user,
    previewMode,
    companionId,
    companionName,
    reading,
    cappedPalette,
    title,
    handleSend,
    lastMessage,
    streamingId,
    typing,
    setTyping,
    sending,
    mobileNavOpen,
    setMobileNavOpen,
    isDay,
    toggleGrade,
    sidebarCollapsed,
    toggleSidebar,
    saveToJournal,
  };
}
