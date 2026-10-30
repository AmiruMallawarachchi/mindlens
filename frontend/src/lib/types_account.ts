/**
 * Shared types for the MindLens API + WebSocket clients.
 * Mirrors backend/app/routers/{auth,session,chat}.py and
 * backend/app/core/connection_manager.py response shapes.
 */

export type AgeGroup = "teen" | "adult";

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  nickname: string | null;
  age: number;
  age_group: AgeGroup | string;
  role: string;
  onboarding_complete: boolean;
  created_at: string;
}

/** POST /api/v1/onboarding/complete request body. */
export interface OnboardingInput {
  name: string;
  age: number;
  nickname?: string;
  people: { name: string; role: string; context?: string }[];
  checkin_preferred_time: "morning" | "evening" | "whenever";
  /** Stored on the profile and editable in Settings > General; memory recall
   * offers them to the specialist as context for the first reply. */
  personality?: string;
  tone_preference?: "gentle" | "balanced" | "direct";
}

