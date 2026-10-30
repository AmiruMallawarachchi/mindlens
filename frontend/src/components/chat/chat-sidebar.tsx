"use client";

import { useEffect } from "react";
import type { ChatSidebarProps } from "./chat-sidebar-types";
import { ChatSidebarCollapsed } from "./chat-sidebar-collapsed";
import { ChatSidebarExpanded } from "./chat-sidebar-expanded";

export type { ChatNavView } from "./chat-sidebar-types";
export { sessionLabel } from "./chat-sidebar-utils";

export function ChatSidebar(props: ChatSidebarProps) {
  const { onNewConversation, collapsed } = props;
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

  return collapsed ? <ChatSidebarCollapsed {...props} /> : <ChatSidebarExpanded {...props} />;
}
