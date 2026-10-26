"use client";

import { BookOpen, Brain, LineChart, MessageCircle, Settings2 } from "lucide-react";
import type { ChatNavView } from "./chat-sidebar-types";

const NAV: { id: ChatNavView; label: string; icon: typeof MessageCircle }[] = [
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "progress", label: "Progress", icon: LineChart },
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "settings", label: "Your Mindlens", icon: Settings2 },
];

export function SidebarNavigation({ activeView, onNavigate, collapsed = false }: {
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
  collapsed?: boolean;
}) {
  if (collapsed) {
    return (
      <nav className="mt-4 flex flex-col gap-1" aria-label="Sections">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = activeView === id;
          return (
            <button key={id} type="button" onClick={() => onNavigate(id)} title={label}
              aria-label={label} aria-current={active ? "page" : undefined}
              className="relative grid size-10 place-items-center rounded-[var(--r-11)] transition-colors"
              style={{ background: active ? "var(--ml-panel-strong)" : undefined,
                border: active ? "1px solid var(--ml-hairline)" : "1px solid transparent",
                color: active ? "var(--ml-ink)" : "var(--ml-muted)" }}>
              <Icon size={16} strokeWidth={1.7} />
            </button>
          );
        })}
      </nav>
    );
  }
  return (
    <nav className="mt-4 flex flex-col gap-0.5 px-3" aria-label="Sections">
      {NAV.map(({ id, label, icon: Icon }) => {
        const active = activeView === id;
        return (
          <button key={id} type="button" onClick={() => onNavigate(id)}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2.5 rounded-[var(--r-11)] px-3 py-2 text-[13px] transition-colors ${active ? "font-medium" : "hover:bg-white/[0.04]"}`}
            style={{ background: active ? "var(--ml-panel-strong)" : undefined,
              border: active ? "1px solid var(--ml-hairline)" : "1px solid transparent",
              color: active ? "var(--ml-ink)" : "var(--ml-muted)" }}>
            <Icon size={15} strokeWidth={1.7} />{label}
            {active && <span aria-hidden="true" className="ml-auto size-[6px] rounded-full"
              style={{ background: "var(--e1)", boxShadow: "0 0 8px var(--e1)" }} />}
          </button>
        );
      })}
    </nav>
  );
}
