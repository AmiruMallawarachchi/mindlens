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


const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const TOKEN_STORAGE_KEY = "mindlens.access_token";

// A dead or unreachable API_BASE_URL (a stale tunnel hostname, a sleeping
// host) used to hang on the browser's own fetch timeout — 60s or more,
// depending on platform — with nothing on screen but a spinner the whole
// time. That read as the app being merely slow, not actually broken.
const REQUEST_TIMEOUT_MS = 12_000;

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

export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    // Same reasoning as request()'s timeout: an unreachable backend must
    // not hang this silently for a minute — every caller of request() is
    // awaiting this before it can even report its own error.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    refreshInFlight = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "ngrok-skip-browser-warning": "true" },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const data = (await response.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        clearTimeout(timeout);
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function request<T>(
  path: string,
  init: RequestInit & { auth?: boolean; _retried?: boolean } = {},
): Promise<T> {
  const { auth = true, _retried = false, ...rest } = init;
  const headers = new Headers(rest.headers);
  headers.set("Content-Type", "application/json");
  // Free ngrok tunnels serve an HTML "you're about to visit..." interstitial
  // to anything that looks like a browser request, in place of the real
  // response — this header opts the request out of it. A no-op against any
  // non-ngrok backend, so it's safe to always send.
  headers.set("ngrok-skip-browser-warning", "true");
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
  //
  // Three distinct failures get three distinct messages, because they call
  // for different next actions from the person reading them — "check your
  // wifi" is useless advice for a request that's simply taking too long, and
  // vice versa. What the browser will *not* tell JavaScript, on purpose, for
  // privacy reasons, is which of DNS failure / connection refused / CORS
  // block actually happened — those three collapse into one identical
  // TypeError. Claiming to tell them apart would be a claim the code can't
  // back up (rule 2), so the unreachable branch stays honestly generic.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers,
      credentials: "omit",
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(
        0,
        "MindLens is taking too long to respond. It may be waking up — try again in a moment.",
      );
    }
    throw new ApiError(
      0,
      typeof navigator !== "undefined" && !navigator.onLine
        ? "You're offline. Check your connection and try again."
        : "Couldn't reach MindLens. It may be down — try again in a moment.",
    );
  } finally {
    clearTimeout(timeout);
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


export function apiBaseUrl(): string {
  return API_BASE_URL;
}

/** Public API surface retained for existing callers. */
export * from "./api_auth";
export * from "./api_sessions";
export * from "./api_journal";
export * from "./api_memory";
