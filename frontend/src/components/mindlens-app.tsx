"use client";

import { useState } from "react";
import { AuthGate } from "./auth-gate";
import { ChatScreen } from "./chat/chat-screen";
import { MindlensMark } from "./brand/wordmark";
import { OnboardingFlow } from "./onboarding/onboarding-flow";
import { PageShell } from "./pages/page-shell";
import { ProgressPage } from "./pages/progress-page";
import { JournalPage } from "./pages/journal-page";
import { MemoryPage } from "./pages/memory-page";
import { YourMindlensPage } from "./pages/your-mindlens-page";
import { useMindLensClient } from "../lib/use-mindlens-client";
import type { ChatNavView } from "./chat/chat-sidebar";

type View = ChatNavView;

export function MindLensApp() {
  const client = useMindLensClient();
  const [view, setView] = useState<View>("chat");

  if (client.authStatus === "onboarding" && client.user) {
    return (
      <OnboardingFlow
        user={client.user}
        busy={client.authBusy}
        error={client.authError}
        onComplete={client.completeOnboarding}
      />
    );
  }

  if (client.authStatus !== "ready") {
    return (
      <main
        className="ml-root grid min-h-screen place-items-center"
        style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}
      >
        {client.authStatus === "checking" ? (
          <div className="flex flex-col items-center gap-4">
            <MindlensMark size={40} />
            <p className="text-[13px]" style={{ color: "var(--ml-muted)" }}>
              Loading your space…
            </p>
          </div>
        ) : (
          <AuthGate
            busy={client.authBusy}
            error={client.authError}
            onLogin={client.login}
            onRegister={client.register}
          />
        )}
      </main>
    );
  }

  // Every view now shares one real shell — chat brings its own three-column
  // layout (sidebar + conversation + inspector); Progress/Journal/Memory/
  // Your Mindlens share PageShell (sidebar + full-width main, no inspector),
  // matching design.md §4.2. The legacy atmosphere shell, mood-swatch topbar
  // and modal SettingsDialog are gone — Your Mindlens is a real page now.
  if (view === "chat") {
    return <ChatScreen client={client} activeView="chat" onNavigate={setView} />;
  }

  const titles: Record<Exclude<View, "chat">, { eyebrow: string; title: string }> = {
    progress: { eyebrow: "Progress", title: "Your rhythm" },
    journal: { eyebrow: "Journal", title: "A place to think out loud" },
    memory: { eyebrow: "Memory", title: "What Mindlens remembers" },
    settings: { eyebrow: "Your Mindlens", title: "Make it yours" },
  };
  const { eyebrow, title } = titles[view];

  return (
    <PageShell client={client} activeView={view} onNavigate={setView} eyebrow={eyebrow} title={title}>
      {view === "progress" && <ProgressPage />}
      {view === "journal" && <JournalPage />}
      {view === "memory" && <MemoryPage />}
      {view === "settings" && <YourMindlensPage onLogout={client.logout} />}
    </PageShell>
  );
}
