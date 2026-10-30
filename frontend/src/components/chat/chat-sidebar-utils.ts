import type { SessionListItem } from "@/lib/types";

const DAY = 86_400_000;

export function groupSessions(sessions: SessionListItem[]) {
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
