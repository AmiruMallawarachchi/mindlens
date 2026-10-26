"use client";

import Link from "next/link";
import { PanelLeftClose, Plus } from "lucide-react";
import { Wordmark } from "@/components/brand/wordmark";
import type { ChatSidebarProps } from "./chat-sidebar-types";
import { ChatSidebarFooter } from "./chat-sidebar-footer";
import { ChatSidebarSessions } from "./chat-sidebar-sessions";
import { SidebarNavigation } from "./chat-sidebar-navigation";

export function ChatSidebarExpanded({ mood, user, sessions, activeSessionId, activeView,
  onNavigate, onNewConversation, onOpenSession, onPinSession, onRenameSession,
  onDeleteSession, onSaveToJournal, companionId, companionActivity = "idle", onToggleCollapsed,
}: ChatSidebarProps) {
    return (
    <aside
      className="ml-glass flex h-full w-[262px] shrink-0 flex-col rounded-[var(--r-22)]"
      aria-label="Conversations and navigation"
    >
      <div className="flex items-center gap-2 px-5 pb-4 pt-5">
        {/* Was a bare <span> â€” it looked like a home affordance and did
          * nothing when clicked. It goes to the marketing home, which is
          * what "/" actually is; the product's own landing view is the
          * Chat nav row below. */}
        <Link
          href="/"
          aria-label="Mindlens home"
          className="min-w-0 flex-1 rounded-[var(--r-10)] transition-opacity hover:opacity-80"
        >
          <Wordmark mood={mood} size={21} className="min-w-0" />
        </Link>
        {onToggleCollapsed && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
            className="grid size-7 shrink-0 place-items-center rounded-full transition-colors hover:bg-white/[0.06]"
            style={{ color: "var(--ml-faint)" }}
          >
            <PanelLeftClose size={14} strokeWidth={1.7} />
          </button>
        )}
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={onNewConversation}
          className="flex w-full items-center gap-2.5 rounded-[var(--r-13)] px-3.5 py-2.5 text-[13px] font-medium leading-none transition-transform hover:scale-[1.015] active:scale-[0.99]"
          style={{
            background:
              "linear-gradient(135deg, color-mix(in oklab, var(--e1) 26%, transparent), color-mix(in oklab, var(--e2) 18%, transparent))",
            border: "1px solid color-mix(in oklab, var(--e1) 34%, transparent)",
            color: "var(--ml-ink)",
          }}
        >
          <Plus size={15} strokeWidth={1.7} className="shrink-0" />
          <span className="truncate">New conversation</span>
          <span className="ml-num ml-auto shrink-0 text-[10px] leading-none" style={{ opacity: 0.5 }}>
            âŒ˜K
          </span>
        </button>
      </div>

      <SidebarNavigation activeView={activeView} onNavigate={onNavigate} />

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-3 pb-2">
        <ChatSidebarSessions sessions={sessions} activeSessionId={activeSessionId}
          onOpenSession={onOpenSession} onPinSession={onPinSession}
          onRenameSession={onRenameSession} onDeleteSession={onDeleteSession}
          onSaveToJournal={onSaveToJournal} />
      </div>

      <ChatSidebarFooter mood={mood} user={user} companionId={companionId}
        companionActivity={companionActivity} onNavigate={onNavigate} />


    </aside>
  );
}

