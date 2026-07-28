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

export interface SessionSummary {
  session_id: string;
  user_id: string;
  title: string | null;
  started_at: string;
  status: string;
}

/** One row from GET /api/v1/sessions (session.py::SessionListItem). */
export interface SessionListItem {
  session_id: string;
  title: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  turn_count: number;
  primary_modality: string | null;
}

/** One turn as stored by chat.py::_save_turn — role is "user" or "assistant";
 * only assistant turns carry agents_used/eos_snapshot/crisis_flag. */
export interface SessionTurn {
  role: ChatRole;
  text: string;
  timestamp: string;
  agents_used?: string[];
  eos_snapshot?: EosSnapshot;
  crisis_flag?: boolean;
}

/** GET /api/v1/sessions/{id} (session.py::SessionDetailResponse). */
export interface SessionDetail {
  session_id: string;
  user_id: string;
  title: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  turns: SessionTurn[];
  eos_timeline: EosSnapshot[];
  agents_used: string[];
  primary_modality: string | null;
}

/** One backend/app/routers/chat.py::_save_mood_log entry. Crisis turns are
 * never logged (their EOS is a hardcoded placeholder, not a real reading). */
export interface MoodLogEntry {
  timestamp: string;
  surface_emotion: string | null;
  core_emotion: string | null;
  distress_level: number | null;
  valence: string | null;
  modality: string | null;
}

export interface DashboardSummary {
  session_count: number;
  latest_moods: MoodLogEntry[];
  memory_enabled: boolean;
}

/** Emotional Operating State snapshot. Server sends the full Pydantic dump;
 * only the fields the UI reads are typed here, the rest pass through. */
export interface EosSnapshot {
  surface_emotion?: string;
  core_emotion?: string;
  distress_level?: number;
  modality?: string;
  trust_level?: number;
  session_depth?: number;
  [key: string]: unknown;
}

export interface CrisisResource {
  name: string;
  number: string;
  available?: string;
  note?: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  eos?: EosSnapshot;
  agentsUsed?: string[];
  crisis?: boolean;
  degraded?: string[];
  /** Still streaming in (stream_chunk frames, before the final "response"). */
  pending?: boolean;
  /** A client- or server-side error rendered inline, not a real turn. */
  kind?: "error";
}

// ---------------------------------------------------------------------------
// WebSocket frames — backend/app/core/connection_manager.py send_* methods
// ---------------------------------------------------------------------------

export type ServerFrame =
  | {
      type: "thinking_update";
      agents_active: string[];
      eos: EosSnapshot;
      memory_recalled?: string[];
    }
  | { type: "stream_chunk"; chunk: string; index: number }
  | { type: "stream_end" }
  | {
      type: "response";
      text: string;
      agents_used: string[];
      eos_snapshot: EosSnapshot;
      music?: unknown;
      crisis_flag: boolean;
      resources?: CrisisResource[];
      degraded?: string[];
    }
  | {
      type: "crisis_response";
      text: string;
      crisis_flag: true;
      resources: CrisisResource[];
      session_paused: boolean;
    }
  | { type: "checkin"; text: string; from_session: string }
  | { type: "error"; detail: string }
  | { type: "pong" }
  | { type: "ping"; timestamp: number };

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";
