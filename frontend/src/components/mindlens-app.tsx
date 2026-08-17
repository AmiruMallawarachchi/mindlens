"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthGate } from "./auth-gate";
import { ChatScreen } from "./chat/chat-screen";
import { MindlensMark } from "./brand/wordmark";
import { OnboardingFlow } from "./onboarding/onboarding-flow";
import { PageShell } from "./pages/page-shell";
import { ProgressPage } from "./pages/progress-page";
import { JournalPage } from "./pages/journal-page";
import { MemoryPage } from "./pages/memory-page";
import { SettingsModal } from "./settings/settings-modal";
import { useMindLensClient } from "../lib/use-mindlens-client";
import type { ChatNavView } from "./chat/chat-sidebar";

type View = ChatNavView;

export function MindLensApp() {
  const client = useMindLensClient();
  const [view, setView] = useState<View>("chat");
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Home's "Sign up" link (/app?auth=register) should land on the register
  // tab, not the login one AuthGate defaults to.
  const searchParams = useSearchParams();
  const initialAuthMode = searchParams.get("auth") === "register" ? "register" : "login";

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
            initialMode={initialAuthMode}
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
  // "settings" is no longer a destination — it opens the modal over whatever
  // you were doing, the way Claude's does, so you never lose your place.
  const navigate = (next: View) => {
    if (next === "settings") {
      setSettingsOpen(true);
      return;
    }
    setView(next);
  };

  const settings = (
    <SettingsModal client={client} open={settingsOpen} onClose={() => setSettingsOpen(false)} />
  );

  if (view === "chat") {
    return (
      <>
        <ChatScreen client={client} activeView="chat" onNavigate={navigate} />
        {settings}
      </>
    );
  }

  const titles: Record<Exclude<View, "chat" | "settings">, { eyebrow: string; title: string }> = {
    progress: { eyebrow: "Your rhythm, not a score", title: "How things have been landing" },
    journal: { eyebrow: "Private reflection", title: "Make space for the thought underneath" },
    memory: { eyebrow: "Transparent personalization", title: "You decide what Mindlens remembers" },
  };
  const { eyebrow, title } = titles[view as Exclude<View, "chat" | "settings">];

  return (
    <>
      <PageShell client={client} activeView={view} onNavigate={navigate} eyebrow={eyebrow} title={title}>
        {view === "progress" && <ProgressPage />}
        {view === "journal" && <JournalPage client={client} />}
        {view === "memory" && <MemoryPage />}
      </PageShell>
      {settings}
    </>
  );
}
