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
  OnboardingInput,
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

/**
 * The access token is short-lived (backend: `jwt_expire_minutes`, 15 by
 * default) on purpose. The refresh token is a 7-day httpOnly cookie the
 * backend already sets on login/register/onboarding — `/api/v1/auth/refresh`
 * exchanges it for a new access token — but nothing ever called it, so every
 * session died after 15 minutes and dropped the user back to the login
 * screen regardless of how recently they'd signed in. This is the one call
 * in the module that needs the cookie, so it opts into `credentials:
 * "include"` rather than the header comment's `omit` — the cookie is scoped
 * to `/api/v1/auth` and same-site in dev (`SameSite=Lax`), cross-site+Secure
 * in production, so it survives the fetch without needing anything else
 * here to change.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const data = (await response.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(
  path: string,
  init: RequestInit & { auth?: boolean; _retried?: boolean } = {},
): Promise<T> {
  const { auth = true, _retried = false, ...rest } = init;
  const headers = new Headers(rest.headers);
  headers.set("Content-Type", "application/json");
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  // `fetch` only rejects when no HTTP response happened at all — the device is
  // offline, DNS failed, or nothing is listening on API_BASE_URL. Left bare,
  // that surfaced through callers' generic fallbacks ("Could not sign in."),
  // which reads as a rejected password and sends people to check credentials
  // that were never actually sent. Status 0 means "never reached the server",
  // so it can't be confused with a real 401.
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers,
      credentials: "omit",
    });
  } catch {
    throw new ApiError(
      0,
      typeof navigator !== "undefined" && !navigator.onLine
        ? "You're offline. Check your connection and try again."
        : "Couldn't reach Mindlens. It may be down — try again in a moment.",
    );
  }

  if (response.status === 401 && auth && !_retried) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return request<T>(path, { ...init, _retried: true });
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
        // FastAPI's own 422s (pydantic validation failures) shape `detail`
        // as a list of {msg, loc, ...} objects, not a string — the check
        // above always missed it, so every validation error in the app
        // surfaced as the raw HTTP reason phrase ("Unprocessable Entity")
        // instead of what actually failed ("value is not a valid email
        // address: ..."). Join every message rather than just the first,
        // since a single request can fail more than one field at once.
        const messages = body.detail
          .map((item: unknown) =>
            typeof item === "object" && item !== null && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : null,
          )
          .filter((msg: string | null): msg is string => Boolean(msg));
        if (messages.length > 0) detail = messages.join(" ");
      }
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

export async function completeOnboarding(
  input: OnboardingInput,
): Promise<UserProfile> {
  const data = await request<{ access_token: string }>(
    "/api/v1/onboarding/complete",
    { method: "POST", body: JSON.stringify(input) },
  );
  // onboarding/complete issues a fresh token (the role/claims can change
  // once onboarding_complete flips), so the client has to pick it up before
  // the next request rather than keep using the pre-onboarding one.
  setAccessToken(data.access_token);
  return fetchMe();
}

export async function fetchMe(): Promise<UserProfile> {
  return request<UserProfile>("/api/v1/auth/me");
}

export async function updateMe(input: { nickname?: string }): Promise<UserProfile> {
  return request<UserProfile>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

// --- Account: the controls behind the privacy promise ----------------------

export interface DeviceSession {
  jti: string;
  device: string;
  created_at: string;
  current: boolean;
}

export async function listDeviceSessions(): Promise<DeviceSession[]> {
  return request<DeviceSession[]>("/api/v1/account/sessions");
}

export async function revokeDeviceSession(jti: string): Promise<void> {
  await request(`/api/v1/account/sessions/${jti}`, { method: "DELETE" });
}

export async function revokeOtherDeviceSessions(): Promise<{ revoked: number }> {
  return request<{ revoked: number }>("/api/v1/account/sessions/revoke-others", {
    method: "POST",
  });
}

export async function exportAccountData(): Promise<unknown> {
  return request<unknown>("/api/v1/account/export");
}

export async function deleteAccount(password: string): Promise<void> {
  await request("/api/v1/account", {
    method: "DELETE",
    body: JSON.stringify({ password, confirm: "DELETE" }),
  });
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
