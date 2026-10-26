"use client";

import { useState } from "react";
import { BookOpen, MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { SessionListItem } from "@/lib/types";
import { groupSessions, sessionLabel } from "./chat-sidebar-utils";
import { DeleteSessionDialog, SessionTitleInput } from "./chat-sidebar-dialogs";

export function ChatSidebarSessions({ sessions, activeSessionId, onOpenSession, onPinSession, onRenameSession, onDeleteSession, onSaveToJournal }: {
  sessions: SessionListItem[];
  activeSessionId: string | null;
  onOpenSession: (sessionId: string) => void;
  onPinSession: (sessionId: string, pinned: boolean) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onSaveToJournal: (session: SessionListItem) => void;
}) {
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SessionListItem | null>(null);
  const groups = groupSessions(sessions);
  return (
    <>
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
                    return (
                      <li key={session.session_id} className="group/session relative flex items-center">
                        {renamingSessionId === session.session_id ? (
                          <SessionTitleInput
                            initial={sessionLabel(session)}
                            onCommit={(next) => {
                              setRenamingSessionId(null);
                              if (next && next !== sessionLabel(session)) {
                                onRenameSession(session.session_id, next);
                              }
                            }}
                            onCancel={() => setRenamingSessionId(null)}
                          />
                        ) : (
                        <>
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

                        <DropdownMenu>
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
                              onSelect={() => setRenamingSessionId(session.session_id)}
                              style={{ color: "var(--ml-ink)" }}
                            >
                              <Pencil size={14} strokeWidth={1.8} />
                              Rename
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
                              onSelect={() => setPendingDelete(session)}
                            >
                              <Trash2 size={14} strokeWidth={1.8} />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                        </>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ),
          )
        )}
      </div>
      {pendingDelete && (
        <DeleteSessionDialog
          session={pendingDelete}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => {
            const id = pendingDelete.session_id;
            setPendingDelete(null);
            onDeleteSession(id);
          }}
        />
      )}
    </>
  );
}
