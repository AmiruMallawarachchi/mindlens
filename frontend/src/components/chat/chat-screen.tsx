"use client";

/**
 * The chat screen — design.md §4.1, board 1a.
 *
 * Three columns: sidebar 262px / conversation / inspector 336px. The
 * inspector is collapsible and hidden below 981px.
 *
 * The header carries a mono eyebrow, the session title in Newsreader, and a
 * plain status pill — §4.1 explicitly forbids naming the therapy approach
 * here. It appears only inside the reasoning trail.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Menu, PanelRightClose, PanelRightOpen } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { EmotionField } from "@/components/field/emotion-field";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { ChatSidebar, sessionLabel, type ChatNavView } from "./chat-sidebar";
import { Composer } from "./composer";
import { CrisisPanel } from "./crisis-banner";
import { Inspector } from "./inspector";
import { AssistantTurn, UserTurn } from "./message-flow";
import { ReasoningTrail } from "./reasoning-trail";
import {
  capIntensity,
  EMOTION_STATES,
  emotionCssVars,
  RESTING_READING,
  type EmotionId,
} from "@/lib/emotion";
import { useGrade } from "@/lib/use-grade";
import { useSidebarCollapsed } from "@/lib/use-sidebar-collapsed";
import type { MindLensClient } from "@/lib/use-mindlens-client";

export function ChatScreen({
  client,
  activeView,
  onNavigate,
}: {
  client: MindLensClient;
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
}) {
  const {
    messages,
    reading: liveReading,
    paletteReading,
    thinking,
    thinkingSteps,
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

  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const [manualEmotion, setManualEmotion] = useState<EmotionId | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { isDay, toggleGrade } = useGrade();
  const { collapsed: sidebarCollapsed, toggle: toggleSidebar } = useSidebarCollapsed();

  // A fresh read from the backend always wins over a hand-picked one — the
  // picker is the user naming this moment, not a permanent override.
  useEffect(() => {
    setManualEmotion(null);
  }, [liveReading.state.id]);

  const reading = useMemo(() => {
    if (crisis) return RESTING_READING;
    if (!manualEmotion) return liveReading;
    return {
      ...liveReading,
      state: EMOTION_STATES[manualEmotion],
      // A hand-picked feeling has no classifier confidence behind it, and §8
      // forbids showing a score that didn't come from a read.
      confidence: null,
      subs: EMOTION_STATES[manualEmotion].subs,
      resting: false,
    };
  }, [liveReading, manualEmotion, crisis]);

  /** Colour only. Three things can decide it, in order of authority:
   * crisis (always neutral) > a deliberate tap in the inspector (this
   * moment) > the saved palette preference (auto tracks the read, manual
   * pins it). The transcript's read strip is never affected by any of it. */
  const paletteColour = useMemo(() => {
    if (crisis) return RESTING_READING;
    if (manualEmotion) return reading;
    return paletteReading;
  }, [crisis, manualEmotion, reading, paletteReading]);

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
      // The "sending" pose is a single pop, not a loop — it holds just long
      // enough to read, then the companion returns to the transcript.
      setSending(true);
      window.setTimeout(() => setSending(false), 700);
    },
    [sendMessage],
  );

  const lastMessage = messages[messages.length - 1];
  const streamingId = lastMessage?.pending ? lastMessage.id : null;

  return (
    <div
      className="ml-root relative flex h-dvh w-full gap-3 p-3"
      // Colour comes from paletteReading, not reading: in manual mode the
      // user has pinned the palette, and crisis freezes the field to neutral
      // regardless. The read strip and inspector still show the real verdict.
      style={emotionCssVars(cappedPalette) as React.CSSProperties}
    >
      <EmotionField reading={cappedPalette} />

      <div className="hidden min-[780px]:block">
        <ChatSidebar
          mood={reading.state.id}
          user={user}
          sessions={sessions}
          activeSessionId={activeSessionId}
          activeView={activeView}
          onNavigate={onNavigate}
          onNewConversation={startNewConversation}
          onOpenSession={openSession}
          onPinSession={pinSession}
          onDeleteSession={deleteSession}
          onSaveToJournal={saveToJournal}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={toggleSidebar}
        />
      </div>

      {/* Mobile drawer — the mockup's Chat Mobile hides the sidebar behind a
       * hamburger rather than shrinking it, since 262px doesn't fit. */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 min-[780px]:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
            className="absolute inset-0 border-none bg-black/40"
          />
          <div className="relative h-full w-[280px] p-3">
            <ChatSidebar
              mood={reading.state.id}
              user={user}
              sessions={sessions}
              activeSessionId={activeSessionId}
              activeView={activeView}
              onNavigate={(view) => {
                onNavigate(view);
                setMobileNavOpen(false);
              }}
              onNewConversation={() => {
                startNewConversation();
                setMobileNavOpen(false);
              }}
              onOpenSession={(id) => {
                openSession(id);
                setMobileNavOpen(false);
              }}
              onPinSession={pinSession}
              onDeleteSession={deleteSession}
              onSaveToJournal={(session) => {
                saveToJournal(session);
                setMobileNavOpen(false);
              }}
            />
          </div>
        </div>
      )}

      <main className="ml-glass flex min-w-0 flex-1 flex-col rounded-[var(--r-22)]">
        <header
          className="flex items-center gap-4 px-6 py-4"
          style={{ borderBottom: "1px solid var(--ml-hairline)" }}
        >
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation"
            className="grid size-9 shrink-0 place-items-center rounded-full transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)] min-[780px]:hidden"
            style={{ border: "1px solid var(--ml-hairline-strong)", background: "var(--ml-panel)" }}
          >
            <Menu size={15} strokeWidth={1.8} />
          </button>

          <div className="min-w-0 flex-1">
            <p className="ml-eyebrow">The room is listening</p>
            <h1
              className="ml-display mt-0.5 truncate text-[24px]"
              style={{ color: "var(--ml-ink)" }}
            >
              {title}
            </h1>
          </div>

          {previewMode && (
            <span
              className="ml-eyebrow rounded-[var(--r-pill)] px-2.5 py-1"
              style={{
                border: "1px solid #ffb15f",
                color: "#ffb15f",
              }}
            >
              Preview · no backend
            </span>
          )}

          <StatusPill status={connectionStatus} />

          <button
            type="button"
            onClick={toggleGrade}
            aria-label="Toggle day and night"
            title="Day / night"
            className="grid size-9 shrink-0 place-items-center rounded-full transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)]"
            style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          >
            {isDay ? <SunIcon /> : <MoonIcon />}
          </button>

          <button
            type="button"
            onClick={() => setInspectorOpen((open) => !open)}
            aria-label={inspectorOpen ? "Hide inspector" : "Show inspector"}
            className="hidden size-9 items-center justify-center rounded-[var(--r-11)] transition-colors hover:bg-white/[0.06] min-[981px]:inline-flex"
            style={{ color: "var(--ml-faint)" }}
          >
            {inspectorOpen ? (
              <PanelRightClose size={16} strokeWidth={1.7} />
            ) : (
              <PanelRightOpen size={16} strokeWidth={1.7} />
            )}
          </button>
        </header>

        <Conversation className="min-h-0 flex-1">
          <ConversationContent className="mx-auto flex w-full max-w-[760px] flex-col gap-7 px-4 py-6">
            {messages.length === 0 && !thinking && (
              <EmptyRoom mood={reading.state.id} companionId={companionId} companionName={companionName} />
            )}

            {messages.map((message, index) =>
              message.role === "user" ? (
                <UserTurn key={message.id} message={message} />
              ) : (
                <div key={message.id} className="group/turn">
                  <AssistantTurn
                    message={message}
                    isStreaming={message.id === streamingId}
                    companionId={companionId}
                    // Regenerate only makes sense on the latest reply.
                    onRegenerate={
                      index === messages.length - 1 && !previewMode
                        ? regenerate
                        : null
                    }
                  />
                </div>
              ),
            )}

            {/* The trail streams before any text arrives, so the room shows
             * its working rather than an anonymous typing dot. */}
            {thinking && !streamingId && thinkingSteps.length > 0 && (
              <div className="flex w-full gap-3">
                {/* Same 44px gutter as an assistant turn (message-flow.tsx),
                  * so the trail doesn't jump sideways when the text arrives. */}
                <div className="w-[44px] shrink-0">
                  <CompanionAvatar companionId={companionId} size={44} mood={reading.state.id} activity="thinking" frozen={!!crisis} />
                </div>
                <div className="min-w-0 flex-1">
                  <ReasoningTrail steps={thinkingSteps} isStreaming />
                </div>
              </div>
            )}

            {crisis && (
              <CrisisPanel
                text={crisis.text}
                resources={crisis.resources}
                onDismiss={dismissCrisis}
              />
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <Composer
          onSend={handleSend}
          onTypingChange={setTyping}
          connectionStatus={connectionStatus}
          disabled={previewMode}
          preview={previewMode}
          showSuggestions={messages.length === 0 && !thinking}
        />
      </main>

      {inspectorOpen && (
        <div className="hidden min-[981px]:block">
          <Inspector
            reading={reading}
            messages={messages}
            manualEmotion={manualEmotion}
            onPickEmotion={setManualEmotion}
            companionId={companionId}
            companionName={companionName}
          />
        </div>
      )}

      {/* The companion leans toward the composer while the user types, then
       * pops once as the message goes. Kept out of the message flow so it
       * doesn't shift the transcript. */}
      <span className="pointer-events-none fixed bottom-28 right-[360px] hidden min-[981px]:block">
        {(typing || sending) && !crisis && (
          <CompanionAvatar
            companionId={companionId}
            size={56}
            mood={reading.state.id}
            activity={sending ? "sending" : "listening"}
            withShadow
          />
        )}
      </span>
    </div>
  );
}

function StatusPill({ status }: { status: MindLensClient["connectionStatus"] }) {
  const label =
    status === "open"
      ? "Live"
      : status === "connecting"
        ? "Connecting"
        : status === "reconnecting"
          ? "Reconnecting"
          : status === "closed"
            ? "Offline"
            : "Idle";

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[var(--r-pill)] px-2.5 py-1 text-[11px]"
      style={{
        border: "1px solid var(--ml-hairline)",
        color: "var(--ml-muted)",
      }}
    >
      <span
        aria-hidden="true"
        className="size-[6px] rounded-full"
        style={{
          background: status === "open" ? "var(--e1)" : "var(--ml-faint)",
          boxShadow: status === "open" ? "0 0 8px var(--e1)" : undefined,
        }}
      />
      {label}
    </span>
  );
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4" />
    </svg>
  );
}

function EmptyRoom({
  mood,
  companionId,
  companionName,
}: {
  mood: EmotionId;
  companionId: string;
  companionName: string;
}) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <CompanionAvatar companionId={companionId} size={150} mood={mood} withShadow />
      <h2 className="ml-display text-[26px]" style={{ color: "var(--ml-ink)" }}>
        Come as you are.
      </h2>
      <p
        className="max-w-[38ch] text-[14px] leading-[1.65]"
        style={{ color: "var(--ml-muted)" }}
      >
        Start anywhere — the middle of the thought is fine. {companionName} will catch up.
      </p>
    </div>
  );
}
