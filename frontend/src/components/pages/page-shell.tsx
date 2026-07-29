"use client";

/**
 * Shared shell for Progress / Journal / Memory / Your Mindlens — design.md
 * §4.2: "Same shell (sidebar + full-width main, no inspector)". Reuses the
 * chat screen's sidebar and emotion field so navigating between pages never
 * feels like a different app.
 */

import { useState } from "react";
import { Menu } from "lucide-react";
import { EmotionField } from "@/components/field/emotion-field";
import { ChatSidebar, type ChatNavView } from "@/components/chat/chat-sidebar";
import { emotionCssVars, type EmotionReading } from "@/lib/emotion";
import { useGrade } from "@/lib/use-grade";
import type { MindLensClient } from "@/lib/use-mindlens-client";

export function PageShell({
  client,
  activeView,
  onNavigate,
  eyebrow,
  title,
  children,
}: {
  client: MindLensClient;
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  const { reading, sessions, activeSessionId, startNewConversation, openSession, user } = client;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { isDay, toggleGrade } = useGrade();

  return (
    <div
      className="ml-root relative flex h-dvh w-full gap-3 p-3"
      style={emotionCssVars(reading as EmotionReading) as React.CSSProperties}
    >
      <EmotionField reading={reading} />

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
        />
      </div>

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
            />
          </div>
        </div>
      )}

      <main className="ml-glass flex min-w-0 flex-1 flex-col overflow-y-auto rounded-[var(--r-22)]">
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
            <p className="ml-eyebrow">{eyebrow}</p>
            <h1 className="ml-display mt-0.5 truncate text-[24px]" style={{ color: "var(--ml-ink)" }}>
              {title}
            </h1>
          </div>

          <button
            type="button"
            onClick={toggleGrade}
            aria-label="Toggle day and night"
            title="Day / night"
            className="grid size-9 shrink-0 place-items-center rounded-full transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)]"
            style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          >
            {isDay ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4" />
              </svg>
            )}
          </button>
        </header>

        <div className="mx-auto w-full max-w-[1080px] flex-1 px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
