/**
 * REST client for the MindLens backend.
 *
 * Uses a bearer token in the Authorization header rather than the cookie
 * flow the backend also supports. The cookie path needs SameSite=None +
 * Secure to survive the cross-origin localhost:3000 -> localhost:8000 hop in
 * dev, which requires HTTPS the local setup doesn't have. A bearer header
 * sidesteps that entirely, and the backend's CSRF check is scoped to
 * cookie-authenticated requests only (see MindLensAuthMiddleware._csrf_failed),
 * so it never applies here.
 */

import type {
  DashboardSummary,
  JournalEntry,
  JournalEntrySummary,
  JournalPrompt,
  MemoryDoc,
  MemoryPreferences,
  MoodLogEntry,
  ProgressInsight,
  SessionDetail,
  SessionListItem,
  SessionSummary,
  UserProfile,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const TOKEN_STORAGE_KEY = "mindlens.access_token";

let inMemoryToken: string | null = null;

export function getAccessToken(): string | null {
  if (inMemoryToken) return inMemoryToken;
  if (typeof window === "undefined") return null;
  inMemoryToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  return inMemoryToken;
}

export function setAccessToken(token: string | null): void {
  inMemoryToken = token;
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<T> {
  const { auth = true, ...rest } = init;
  const headers = new Headers(rest.headers);
  headers.set("Content-Type", "application/json");
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
    credentials: "omit",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body wasn't JSON — keep the status text.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  role: string;
  csrf_token: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  name: string;
  age: number;
  nickname?: string;
}

export async function register(input: RegisterInput): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
    auth: false,
  });
  setAccessToken(data.access_token);
  return data;
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
    auth: false,
  });
  setAccessToken(data.access_token);
  return data;
}

export function logoutLocal(): void {
  setAccessToken(null);
}

export async function fetchMe(): Promise<UserProfile> {
  return request<UserProfile>("/api/v1/auth/me");
}

export async function createSession(
  title?: string,
): Promise<SessionSummary> {
  return request<SessionSummary>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify(title ? { title } : {}),
  });
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}

export async function listSessions(): Promise<SessionListItem[]> {
  return request<SessionListItem[]>("/api/v1/sessions");
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/v1/sessions/${sessionId}`);
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

// ---------------------------------------------------------------------------
// Journal
// ---------------------------------------------------------------------------

export async function fetchJournalPrompt(): Promise<JournalPrompt> {
  return request<JournalPrompt>("/api/v1/journal/prompt");
}

export async function listJournalEntries(
  limit = 30,
): Promise<JournalEntrySummary[]> {
  return request<JournalEntrySummary[]>(`/api/v1/journal?limit=${limit}`);
}

export async function getJournalEntry(entryId: string): Promise<JournalEntry> {
  return request<JournalEntry>(`/api/v1/journal/${entryId}`);
}

export async function createJournalEntry(input: {
  title?: string;
  text: string;
  prompt_used?: string;
}): Promise<JournalEntry> {
  return request<JournalEntry>("/api/v1/journal", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateJournalEntry(
  entryId: string,
  input: { title?: string | null; text: string },
): Promise<JournalEntry> {
  return request<JournalEntry>(`/api/v1/journal/${entryId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteJournalEntry(entryId: string): Promise<void> {
  await request(`/api/v1/journal/${entryId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export async function fetchMemory(): Promise<MemoryDoc> {
  return request<MemoryDoc>("/api/v1/memory");
}

export async function updateMemoryPreferences(
  prefs: MemoryPreferences,
): Promise<void> {
  await request("/api/v1/memory/preferences", {
    method: "PATCH",
    body: JSON.stringify(prefs),
  });
}

export async function updateMemoryPeople(
  people: Record<string, { role: string; context: string; sentiment: string }>,
): Promise<void> {
  await request("/api/v1/memory/people", {
    method: "PATCH",
    body: JSON.stringify({ people }),
  });
}

export async function addMemoryNote(text: string): Promise<{ note_id: string }> {
  return request<{ note_id: string; message: string }>("/api/v1/memory/notes", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function deleteMemoryNote(noteId: string): Promise<void> {
  await request(`/api/v1/memory/notes/${noteId}`, { method: "DELETE" });
}

export async function deleteMemoryEntry(
  section: "people" | "trigger_topics" | "effective_coping" | "milestones" | "raw_notes",
  key: string,
): Promise<void> {
  await request("/api/v1/memory/delete_entry", {
    method: "POST",
    body: JSON.stringify({ section, key }),
  });
}
