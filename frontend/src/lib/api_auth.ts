import { request, setAccessToken } from "./api";
import type { OnboardingInput, UserProfile } from "./types";

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

