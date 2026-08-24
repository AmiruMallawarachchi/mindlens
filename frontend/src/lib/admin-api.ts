/**
 * Admin REST client — deliberately separate from lib/api.ts.
 *
 * The backend has two different admin auth schemes (backend/app/routers/
 * system.py + app/middleware/auth.py::require_admin): the ops endpoints
 * here take a short-lived (1h) admin JWT signed with a different secret
 * than the normal user access token, minted by its own
 * POST /api/v1/auth/admin/login. It is not a role claim on the regular
 * token, and there is no refresh endpoint for it.
 *
 * That token must never pass through lib/api.ts's request(): that helper
 * hardcodes getAccessToken() and its 401 path calls refreshAccessToken(),
 * which unconditionally overwrites the *user* token slot — storing the
 * admin token under the same key would let any admin 401 silently clobber
 * the signed-in user's session. So this file keeps its own storage key,
 * its own fetch wrapper, and never imports getAccessToken/setAccessToken.
 *
 * Stored in sessionStorage, not localStorage: the token is good for one
 * hour with no way to renew it, so there is no reason for it to outlive
 * the tab.
 */

import type { AdminSystemStatus, AdminTokenResponse } from "./types";
import { apiBaseUrl, ApiError } from "./api";

const ADMIN_TOKEN_STORAGE_KEY = "mindlens.admin_token";
const REQUEST_TIMEOUT_MS = 12_000;

let inMemoryAdminToken: string | null = null;

export function getAdminToken(): string | null {
  if (inMemoryAdminToken) return inMemoryAdminToken;
  if (typeof window === "undefined") return null;
  inMemoryAdminToken = window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
  return inMemoryAdminToken;
}

function setAdminToken(token: string | null): void {
  inMemoryAdminToken = token;
  if (typeof window === "undefined") return;
  if (token) {
    window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  }
}

/** True once a token is held — the dashboard's own logged-in/out gate.
 * Not a claim that the token is still valid; a call can still 401 if the
 * hour has run out, same as any bearer token. */
export function hasAdminSession(): boolean {
  return getAdminToken() !== null;
}

/** Clears the stored token client-side only. There is no admin logout
 * endpoint — create_admin_token mints a jti but nothing ever adds it to
 * the blocklist (that only happens for user logout), so the token itself
 * stays valid server-side for the rest of its hour regardless. */
export function adminLogout(): void {
  setAdminToken(null);
}

async function adminRequest<T>(path: string): Promise<T> {
  const token = getAdminToken();
  if (!token) {
    throw new ApiError(0, "Not signed in as admin.");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "ngrok-skip-browser-warning": "true",
      },
      credentials: "omit",
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "Mindlens is taking too long to respond. Try again in a moment.");
    }
    throw new ApiError(
      0,
      typeof navigator !== "undefined" && !navigator.onLine
        ? "You're offline. Check your connection and try again."
        : "Couldn't reach Mindlens. It may be down — try again in a moment.",
    );
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 401) {
    // No refresh path exists for this token — unlike the user client, a
    // 401 here always means "sign in again", never "silently retry."
    setAdminToken(null);
    throw new ApiError(401, "Your admin session has expired. Sign in again.");
  }

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

  return (await response.json()) as T;
}

/** POST /api/v1/auth/admin/login. Requires role="admin" on the account —
 * a 403 here means the credentials are correct but the account isn't an
 * admin, which is a different, more actionable message than "wrong
 * password" and the backend already distinguishes the two. */
export async function adminLogin(email: string, password: string): Promise<void> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1/auth/admin/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      credentials: "omit",
      body: JSON.stringify({ email, password }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "Mindlens is taking too long to respond. Try again in a moment.");
    }
    throw new ApiError(
      0,
      typeof navigator !== "undefined" && !navigator.onLine
        ? "You're offline. Check your connection and try again."
        : "Couldn't reach Mindlens. It may be down — try again in a moment.",
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body wasn't JSON — keep the status text.
    }
    if (response.status === 401) detail = "Those credentials weren't right.";
    else if (response.status === 403) detail = "That account isn't an admin.";
    else if (response.status === 429) detail = "Too many attempts. Try again in 15 minutes.";
    throw new ApiError(response.status, detail);
  }

  const data = (await response.json()) as AdminTokenResponse;
  setAdminToken(data.admin_token);
}

export async function fetchAdminSystem(): Promise<AdminSystemStatus> {
  return adminRequest<AdminSystemStatus>("/api/v1/admin/system");
}
