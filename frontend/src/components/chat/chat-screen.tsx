"use client";

/**
 * The chat screen â€” design.md Â§4.1, board 1a.
 *
 * Three columns: sidebar 262px / conversation / inspector 336px. The
 * inspector is collapsible and hidden below 981px.
 *
 * The header carries a mono eyebrow, the session title in Newsreader, and a
 * plain status pill â€” Â§4.1 explicitly forbids naming the therapy approach
 * here. It appears only inside the reasoning trail.
 */

import { Menu } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { EmotionField } from "@/components/field/emotion-field";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { ChatSidebar, type ChatNavView } from "./chat-sidebar";
import { Composer } from "./composer";
import { CrisisPanel } from "./crisis-banner";
import { AssistantTurn, UserTurn } from "./message-flow";
import { ReasoningTrail } from "./reasoning-trail";
import { LiveStageTrail } from "./live-stage-trail";
import { emotionCssVars } from "@/lib/emotion";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { useChatScreenState } from "./use-chat-screen-state";
import { EmptyRoom, MoonIcon, StatusPill, SunIcon } from "./chat-screen-components";

export function ChatScreen({
  client,
  activeView,
  onNavigate,
}: {
  client: MindLensClient;
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
}) {
  const state = useChatScreenState(client, onNavigate);
  const { messages, thinking, thinkingSteps, liveStages, crisis, dismissCrisis, regenerate, connectionStatus, sessions, activeSessionId, startNewConversation, openSession, pinSession, renameSession, deleteSession, user, previewMode, companionId, companionName, reading, cappedPalette, title, handleSend, lastMessage, streamingId, typing, setTyping, sending, mobileNavOpen, setMobileNavOpen, isDay, toggleGrade, sidebarCollapsed, toggleSidebar, saveToJournal } = state;

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
          onRenameSession={renameSession}
          onDeleteSession={deleteSession}
          onSaveToJournal={saveToJournal}
          companionId={companionId}
          companionActivity={
            crisis ? "idle" : sending ? "sending" : typing ? "listening" : "idle"
          }
          collapsed={sidebarCollapsed}
          onToggleCollapsed={toggleSidebar}
        />
      </div>

      {/* Mobile drawer â€” the mockup's Chat Mobile hides the sidebar behind a
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
              onRenameSession={renameSession}
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
              Preview Â· no backend
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
                    onChooseOption={handleSend}
                    showOptions={message.id === lastMessage?.id}
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

            {/* Two phases, not one. While the pipeline is still running,
              * stage_update frames arrive one at a time and LiveStageTrail
              * grows to match â€” this is the genuinely live half. Once the
              * pipeline finishes, thinking_update delivers the complete
              * picture and the full ReasoningTrail takes over; that one was
              * always "complete the instant it appears" and still is, but
              * now it appears after a real progression instead of after a
              * silent wait. */}
            {thinking && !streamingId && (thinkingSteps.length > 0 || liveStages.length > 0) && (
              <div className="flex w-full gap-3">
                {/* Same 44px gutter as an assistant turn (message-flow.tsx),
                  * so the trail doesn't jump sideways when the text arrives. */}
                <div className="w-[44px] shrink-0">
                  <CompanionAvatar companionId={companionId} size={44} mood={reading.state.id} activity="thinking" frozen={!!crisis} />
                </div>
                <div className="min-w-0 flex-1">
                  {thinkingSteps.length > 0 ? (
                    <ReasoningTrail steps={thinkingSteps} isStreaming />
                  ) : (
                    <LiveStageTrail stages={liveStages} />
                  )}
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
        />
      </main>
    </div>
  );
}
