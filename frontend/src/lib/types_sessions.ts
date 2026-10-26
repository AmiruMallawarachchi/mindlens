import type { ChatRole, EosSnapshot } from "./types_chat";

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
  pinned: boolean;
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

/** GET /api/v1/dashboard/insight (dashboard.py::get_progress_insight). */
export interface ProgressInsight {
  available: boolean;
  session_count: number;
  sessions_needed?: number;
  insight?: string | null;
  generated_at?: string;
  error?: string;
}

