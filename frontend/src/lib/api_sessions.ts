import { request } from "./api";
import type {
  DashboardSummary,
  MoodLogEntry,
  ProgressInsight,
  SessionDetail,
  SessionListItem,
  SessionSummary,
} from "./types";

export async function createSession(
  title?: string,
): Promise<SessionSummary> {
  return request<SessionSummary>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify(title ? { title } : {}),
  });
}

// status=active — "Delete" in the sidebar calls the existing soft-end
// endpoint (session.py's DELETE, which sets status="ended" rather than
// erasing the transcript), so this filter is what makes that read as an
// actual delete from the user's side: an ended session stops appearing
// anywhere in the app once this list excludes it.
export async function listSessions(): Promise<SessionListItem[]> {
  return request<SessionListItem[]>("/api/v1/sessions?status=active");
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/v1/sessions/${sessionId}`);
}

export async function pinSession(sessionId: string, pinned: boolean): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/pin`, {
    method: "PATCH",
    body: JSON.stringify({ pinned }),
  });
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/title`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}`, { method: "DELETE" });
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>("/api/v1/dashboard/summary");
}

export async function fetchMoodLogs(limit = 30): Promise<MoodLogEntry[]> {
  const data = await request<{ moods: MoodLogEntry[] }>(
    `/api/v1/dashboard/mood?limit=${limit}`,
  );
  return data.moods;
}

export async function fetchProgressInsight(): Promise<ProgressInsight> {
  return request<ProgressInsight>("/api/v1/dashboard/insight");
}

