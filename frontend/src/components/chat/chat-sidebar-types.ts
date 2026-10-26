import type { EmotionId } from "@/lib/emotion";
import type { SessionListItem, UserProfile } from "@/lib/types";

export type ChatNavView = "chat" | "progress" | "journal" | "memory" | "settings";

export type ChatSidebarProps = {
  mood: EmotionId;
  user: UserProfile | null;
  sessions: SessionListItem[];
  activeSessionId: string | null;
  activeView: ChatNavView;
  onNavigate: (view: ChatNavView) => void;
  onNewConversation: () => void;
  onOpenSession: (sessionId: string) => void;
  onPinSession: (sessionId: string, pinned: boolean) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onSaveToJournal: (session: SessionListItem) => void;
  companionId?: string;
  companionActivity?: "idle" | "listening" | "sending" | "thinking";
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
};
