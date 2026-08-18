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
  /** Both already power empathy_agent's prompt (Settings > General) — asked
   * here too so the very first reply is personalized. */
  personality?: string;
  tone_preference?: "gentle" | "balanced" | "direct";
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

// ---------------------------------------------------------------------------
// Journal — backend/app/routers/journal.py
// ---------------------------------------------------------------------------

export interface JournalPrompt {
  prompt: string;
  date: string;
}

export interface JournalEntrySummary {
  entry_id: string;
  title: string | null;
  excerpt: string;
  created_at: string;
}

export interface JournalEntry {
  entry_id: string;
  title: string | null;
  text: string;
  prompt_used: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Memory — backend/app/routers/memory.py
// ---------------------------------------------------------------------------

export interface MemoryPerson {
  role: string;
  context: string;
  sentiment: string;
}

export interface MemoryPreferences {
  music_genres?: string[];
  mindfulness_style?: string;
  /** Inferred by PersonalityAgent from what's been said, not typed by the
   * user. `null` clears it — distinct from "not sent" (which leaves the
   * stored value untouched). */
  introvert_score?: number | null;
  preferred_modality?: string;
  checkin_preferred_time?: string;
  tone_preference?: "gentle" | "balanced" | "direct";
  memory_depth?: "everything" | "key_details" | "nothing";
  companion_name?: string;
  companion_id?: string;
  personality?: string;
  custom_instructions?: string;
  /** "auto" = recolour from each turn's read; "manual" = pinned palette. */
  palette_mode?: "auto" | "manual";
  manual_palette?: string;
  intensity_cap?: number;
}

export interface MemoryEmotionalPatterns {
  most_common_emotion?: string | null;
  average_distress?: number;
  trigger_topics?: string[];
  effective_coping?: string[];
}

export interface MemoryNote {
  note_id: string;
  text: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryProfile {
  name?: string;
  nickname?: string;
  age?: number;
  age_group?: string;
  onboarding_complete?: boolean;
}

/** GET /api/v1/memory (memory.py::get_memory) — the full user_memory doc. */
export interface MemoryDoc {
  id: string;
  user_id: string;
  display_name?: string;
  profile: MemoryProfile;
  people: Record<string, MemoryPerson>;
  emotional_patterns: MemoryEmotionalPatterns;
  preferences: MemoryPreferences;
  milestones: string[];
  raw_notes: MemoryNote[];
  created_at: string;
  updated_at: string;
}

/** Emotional Operating State snapshot. Server sends the full Pydantic dump
 * (backend/app/core/emotional_os.py::EmotionalOperatingState); only the
 * fields the UI reads are typed here, the rest pass through. */
export interface EosSnapshot {
  surface_emotion?: string;
  surface_confidence?: number;
  core_emotion?: string;
  suppressed_emotion?: string | null;
  distortion_label?: string | null;
  distress_level?: number;
  emotional_stability?: number;
  mental_fatigue?: number;
  social_energy?: number;
  modality?: string;
  trust_level?: number;
  alliance_score?: number;
  session_depth?: number;
  [key: string]: unknown;
}

export interface CrisisResource {
  name: string;
  number: string;
  available?: string;
  note?: string;
}

/** backend/app/agents/streaming.py::_extract_music_payload. Null when the
 * music agent didn't run this turn — distinct from running with no tracks.
 * Tracks come from Apple's iTunes Search API (music_agent.py) — no user
 * connection step. preview_url is a real, directly-playable 30s clip,
 * present on most but not all tracks; track_url (the Apple Music page) is
 * present whenever preview_url is. */
export interface MusicPayload {
  message: string;
  tracks: Array<{ name?: string; artist?: string; preview_url?: string | null; track_url?: string | null }>;
  emotion: string | null;
}

/** Structured follow-up answers offered as buttons under a reply.
 *
 * Deliberately not the canned menu empathy_agent forbids: generated per
 * turn from what was actually said, schema-validated rather than parsed out
 * of prose, and never a closed set — `allow_other` is always true because
 * the point is to save typing, not to limit what someone may say. */
export interface OptionsPayload {
  options: string[];
  allow_other: boolean;
}

export type ChatRole = "user" | "assistant";

/** What the pipeline actually did this turn, so the reasoning trail can
 * describe it rather than assert a script. backend: orchestrator's
 * `telemetry` key. */
export interface TurnTelemetry {
  rag?: {
    /** "ran" | "skipped_trivial" | "skipped_crisis" | "failed" | "provided" */
    status: string;
    chunks: number;
    /** The reranker model that ordered these chunks, named only when it was
     * actually configured to run this turn. */
    model?: string | null;
  };
  /** Null when no agent that consults a modality ran. A modality is set on
   * every turn regardless, so a non-null value here is the only honest
   * signal that one actually shaped the reply. */
  modality?: string | null;
  substantive?: boolean;
}

/** The safety gate's real verdict — computed on every turn and, until now,
 * dropped before it reached the client. backend: SafetyGateResult. */
export interface SafetyVerdict {
  is_crisis?: boolean;
  layer_triggered?: string | null;
  confidence?: number;
  reason?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** On a user turn this is the read taken *of* that message, which is what
   * the emotion read strip beneath it renders. On an assistant turn it's the
   * state the reply was written against. */
  eos?: EosSnapshot;
  agentsUsed?: string[];
  crisis?: boolean;
  degraded?: string[];
  /** Anything the backend reported recalling for this turn. */
  memoryRecalled?: string[];
  /** Set when the music agent ran this turn — renders the music player card. */
  music?: MusicPayload | null;
  /** Still streaming in (stream_chunk frames, before the final "response"). */
  pending?: boolean;
  /** A client- or server-side error rendered inline, not a real turn. */
  kind?: "error";
  telemetry?: TurnTelemetry;
  safety?: SafetyVerdict;
  options?: OptionsPayload | null;
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
      telemetry?: TurnTelemetry;
      safety?: SafetyVerdict;
      degraded?: string[];
    }
  | { type: "stream_chunk"; chunk: string; index: number }
  | { type: "stream_end" }
  | {
      type: "response";
      text: string;
      agents_used: string[];
      eos_snapshot: EosSnapshot;
      music?: MusicPayload | null;
      crisis_flag: boolean;
      resources?: CrisisResource[];
      degraded?: string[];
      memory_recalled?: string[];
      telemetry?: TurnTelemetry;
      safety?: SafetyVerdict;
      options?: OptionsPayload | null;
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
