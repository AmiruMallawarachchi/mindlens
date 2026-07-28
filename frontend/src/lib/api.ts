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

import type { SessionSummary, UserProfile } from "./types";

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
