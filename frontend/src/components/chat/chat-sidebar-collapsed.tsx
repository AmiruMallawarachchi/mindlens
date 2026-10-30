"use client";

import { MindlensMark } from "@/components/brand/wordmark";
import { PanelLeftOpen, Plus } from "lucide-react";
import type { ChatSidebarProps } from "./chat-sidebar-types";
import { SidebarNavigation } from "./chat-sidebar-navigation";

export function ChatSidebarCollapsed({ user, onNewConversation, activeView, onNavigate, onToggleCollapsed }: ChatSidebarProps) {
      return (
      <aside
        className="ml-glass flex h-full w-[72px] shrink-0 flex-col items-center rounded-[var(--r-22)] py-5"
        aria-label="Conversations and navigation"
      >
        <MindlensMark size={22} />

        <button
          type="button"
          onClick={onNewConversation}
          title="New conversation (⌘K)"
          aria-label="New conversation"
          className="mt-5 grid size-10 place-items-center rounded-[var(--r-13)] transition-transform hover:scale-105 active:scale-95"
          style={{
            background:
              "linear-gradient(135deg, color-mix(in oklab, var(--e1) 26%, transparent), color-mix(in oklab, var(--e2) 18%, transparent))",
            border: "1px solid color-mix(in oklab, var(--e1) 34%, transparent)",
            color: "var(--ml-ink)",
          }}
        >
          <Plus size={16} strokeWidth={1.7} />
        </button>

        <SidebarNavigation activeView={activeView} onNavigate={onNavigate} collapsed />

        <div className="mt-auto flex flex-col items-center gap-3">
          {onToggleCollapsed && (
            <button
              type="button"
              onClick={onToggleCollapsed}
              title="Expand sidebar"
              aria-label="Expand sidebar"
              className="grid size-8 place-items-center rounded-full transition-colors hover:bg-white/[0.06]"
              style={{ color: "var(--ml-faint)" }}
            >
              <PanelLeftOpen size={15} strokeWidth={1.7} />
            </button>
          )}
          <span
            title={user?.nickname || user?.name || "Signed in"}
            className="grid size-8 place-items-center rounded-full text-[11px] font-semibold"
            style={{
              background: "linear-gradient(140deg, var(--e2), var(--e1))",
              color: "#fffdf8",
            }}
          >
            {(user?.nickname || user?.name || "?").slice(0, 1).toUpperCase()}
          </span>
        </div>
      </aside>
    );
}
