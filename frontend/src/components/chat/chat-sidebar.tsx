"use client";

/**
 * Sidebar — design.md §4.1, fixed 262px.
 *
 * Brand lockup, "New conversation ⌘K", nav, session list grouped
 * Today / Previous 7 days / Earlier, and the privacy card pinned at the base.
 */

import { useEffect, useState } from "react";
import {
  BookOpen,
  Brain,
  LineChart,
  MessageCircle,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff,
  Plus,
  Settings2,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { MindlensMark, Wordmark } from "@/components/brand/wordmark";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { EmotionId } from "@/lib/emotion";
import type { SessionListItem, UserProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ChatNavView = "chat" | "progress" | "journal" | "memory" | "settings";

const NAV: { id: ChatNavView; label: string; icon: typeof MessageCircle }[] = [
  { id: "chat", label: "Chat", icon: MessageCircle },
  { id: "progress", label: "Progress", icon: LineChart },
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "settings", label: "Your Mindlens", icon: Settings2 },
];

const DAY = 86_400_000;

function groupSessions(sessions: SessionListItem[]) {
  const now = Date.now();
  // Pinned sessions get their own group regardless of age — that's the
  // point of pinning them — and are excluded from the date buckets below so
  // they don't appear twice.
  const groups: Record<string, SessionListItem[]> = {
    Pinned: [],
    Today: [],
    "Previous 7 days": [],
    Earlier: [],
  };
  for (const session of sessions) {
    if (session.pinned) {
      groups.Pinned.push(session);
      continue;
    }
    const age = now - new Date(session.started_at).getTime();
    if (age < DAY) groups.Today.push(session);
    else if (age < 7 * DAY) groups["Previous 7 days"].push(session);
    else groups.Earlier.push(session);
  }
  return groups;
}

export function sessionLabel(session: SessionListItem): string {
  if (session.title) return session.title;
  const date = new Date(session.started_at);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ChatSidebar({
  mood,
  user,
  sessions,
  activeSessionId,
  activeView,
  onNavigate,
  onNewConversation,
  onOpenSession,
  onPinSession,
  onDeleteSession,
  onSaveToJournal,
  collapsed = false,
  onToggleCollapsed,
}: {
  mood: EmotionId;
  user: UserProfile | null;
  sessions: SessionListItem[];
  activeSessionId: string | null;
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
  onNewConversation: () => void;
  onOpenSession: (sessionId: string) => void;
  onPinSession: (sessionId: string, pinned: boolean) => void;
  onDeleteSession: (sessionId: string) => void;
  onSaveToJournal: (session: SessionListItem) => void;
  /** Icon-only rail instead of the full 262px panel. Optional — callers
   * that don't offer the collapse feature (the mobile drawer) just omit it. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}) {
  // A "Delete" click arms that one session rather than deleting immediately
  // — same proportionate two-click pattern as Memory's Forget and Journal's
  // delete. Radix's dropdown normally closes on item select, so the Delete
  // item's onSelect below prevents that default until the second click.
  const [armedSessionId, setArmedSessionId] = useState<string | null>(null);
  // §8 — full keyboard nav, ⌘K starts a new conversation.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onNewConversation();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onNewConversation]);

  const groups = groupSessions(sessions);

  if (collapsed) {
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

        <nav className="mt-4 flex flex-col gap-1" aria-label="Sections">
          {NAV.map(({ id, label, icon: Icon }) => {
            const active = activeView === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onNavigate(id)}
                title={label}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className="relative grid size-10 place-items-center rounded-[var(--r-11)] transition-colors"
                style={{
                  background: active ? "var(--ml-panel-strong)" : undefined,
                  border: active ? "1px solid var(--ml-hairline)" : "1px solid transparent",
                  color: active ? "var(--ml-ink)" : "var(--ml-muted)",
                }}
              >
                <Icon size={16} strokeWidth={1.7} />
              </button>
            );
          })}
        </nav>

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

  return (
    <aside
      className="ml-glass flex h-full w-[262px] shrink-0 flex-col rounded-[var(--r-22)]"
      aria-label="Conversations and navigation"
    >
      <div className="flex items-center gap-2 px-5 pb-4 pt-5">
        <Wordmark mood={mood} size={21} className="min-w-0 flex-1" />
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
            ⌘K
          </span>
        </button>
      </div>

      <nav className="mt-4 flex flex-col gap-0.5 px-3" aria-label="Sections">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = activeView === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onNavigate(id)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-[var(--r-11)] px-3 py-2 text-[13px] transition-colors",
                active ? "font-medium" : "hover:bg-white/[0.04]",
              )}
              style={{
                background: active ? "var(--ml-panel-strong)" : undefined,
                border: active
                  ? "1px solid var(--ml-hairline)"
                  : "1px solid transparent",
                color: active ? "var(--ml-ink)" : "var(--ml-muted)",
              }}
            >
              <Icon size={15} strokeWidth={1.7} />
              {label}
              {active && (
                <span
                  aria-hidden="true"
                  className="ml-auto size-[6px] rounded-full"
                  style={{
                    background: "var(--e1)",
                    boxShadow: "0 0 8px var(--e1)",
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-3 pb-2">
        {sessions.length === 0 ? (
          <p className="px-3 py-4 text-[12px]" style={{ color: "var(--ml-faint)" }}>
            Your conversations will appear here.
          </p>
        ) : (
          Object.entries(groups).map(([label, items]) =>
            items.length === 0 ? null : (
              <div key={label} className="mb-4">
                <p className="ml-eyebrow px-3 pb-1.5">{label}</p>
                <ul className="flex flex-col gap-0.5">
                  {items.map((session) => {
                    const active = session.session_id === activeSessionId;
                    const armed = armedSessionId === session.session_id;
                    return (
                      <li key={session.session_id} className="group/session relative flex items-center">
                        <button
                          type="button"
                          onClick={() => onOpenSession(session.session_id)}
                          className={cn(
                            "w-full truncate rounded-[var(--r-11)] py-2 pl-3 pr-8 text-left text-[12.5px] transition-colors",
                            !active && "hover:bg-white/[0.04]",
                          )}
                          style={{
                            background: active
                              ? "color-mix(in oklab, var(--e1) 12%, transparent)"
                              : undefined,
                            color: active ? "var(--ml-ink)" : "var(--ml-muted)",
                          }}
                        >
                          {session.pinned && (
                            <Pin size={10} strokeWidth={2} className="mr-1 inline-block shrink-0 align-middle" aria-hidden="true" />
                          )}
                          {sessionLabel(session)}
                        </button>

                        <DropdownMenu
                          onOpenChange={(open) => {
                            if (!open) setArmedSessionId((k) => (k === session.session_id ? null : k));
                          }}
                        >
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              aria-label={`More options for ${sessionLabel(session)}`}
                              className="absolute right-1 grid size-6 shrink-0 place-items-center rounded-[8px] opacity-0 transition-opacity group-hover/session:opacity-100 focus-visible:opacity-100 hover:bg-white/[0.08]"
                              style={{ color: "var(--ml-faint)" }}
                            >
                              <MoreHorizontal size={14} strokeWidth={1.8} />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            align="start"
                            style={{
                              background: "var(--ml-panel-legible)",
                              border: "1px solid var(--ml-hairline-strong)",
                              color: "var(--ml-ink)",
                            }}
                          >
                            <DropdownMenuItem
                              onSelect={() => onPinSession(session.session_id, !session.pinned)}
                              style={{ color: "var(--ml-ink)" }}
                            >
                              {session.pinned ? (
                                <PinOff size={14} strokeWidth={1.8} />
                              ) : (
                                <Pin size={14} strokeWidth={1.8} />
                              )}
                              {session.pinned ? "Unpin" : "Pin"}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => onSaveToJournal(session)}
                              style={{ color: "var(--ml-ink)" }}
                            >
                              <BookOpen size={14} strokeWidth={1.8} />
                              Save to Journal
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={(event) => {
                                if (!armed) {
                                  event.preventDefault();
                                  setArmedSessionId(session.session_id);
                                  return;
                                }
                                setArmedSessionId(null);
                                onDeleteSession(session.session_id);
                              }}
                            >
                              <Trash2 size={14} strokeWidth={1.8} />
                              {armed ? "Click to confirm" : "Delete"}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ),
          )
        )}
      </div>

      <div className="p-3">
        <button
          type="button"
          onClick={() => onNavigate("settings")}
          aria-label="Open settings"
          className="flex w-full items-center gap-2.5 rounded-[var(--r-13)] p-3 text-left transition-colors hover:bg-white/[0.04]"
          style={{
            background: "var(--ml-panel-strong)",
            border: "1px solid var(--ml-hairline)",
          }}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12.5px]" style={{ color: "var(--ml-ink)" }}>
              {user?.nickname || user?.name || "Signed in"}
            </span>
            <span
              className="mt-1 flex items-center gap-1.5 text-[10.5px]"
              style={{ color: "var(--ml-faint)" }}
            >
              {/* Not "end-to-end", and not "only you" either: the server must
                * read every message for the classifiers to run, and Groq
                * reads it to write the reply — so "only you" is a stronger,
                * false claim, not a weaker safe one. An accurate promise is
                * worth more here than an impressive one that doesn't survive
                * being checked. */}
              <ShieldCheck size={12} strokeWidth={1.7} />
              Private · not end-to-end encrypted
            </span>
          </span>
          <Settings2 size={15} strokeWidth={1.7} className="shrink-0" style={{ color: "var(--ml-faint)" }} />
        </button>
      </div>
    </aside>
  );
}
