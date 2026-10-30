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

/** Structured follow-up answers offered as buttons under a reply.
 *
 * Deliberately not a canned menu: generated per turn from what was actually
 * said, schema-validated rather than parsed out of prose, and never a closed
 * set — `allow_other` is always true because the point is to save typing,
 * not to limit what someone may say. */
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
    provider?: string;
    /** The reranker model that ordered these chunks, named only when it was
     * actually configured to run this turn. */
    model?: string | null;
  };
  /** Null when no agent that consults a modality ran. A modality is set on
   * every turn regardless, so a non-null value here is the only honest
   * signal that one actually shaped the reply. */
  modality?: string | null;
  substantive?: boolean;
  graph?: {
    nodes: string[];
    route: string;
  };
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
  /** Still streaming in (stream_chunk frames, before the final "response"). */
  pending?: boolean;
  /** A client- or server-side error rendered inline, not a real turn. */
  kind?: "error";
  telemetry?: TurnTelemetry;
  safety?: SafetyVerdict;
  options?: OptionsPayload | null;
  /** Real wall-clock seconds from send to this reply arriving — see
   * use-mindlens-client.ts's thinkingStartRef for why this has to be
   * measured client-side rather than left to the trail component. */
  thinkingDurationS?: number;
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
  | { type: "stage_update"; stage: string; detail: string }
  | { type: "stream_chunk"; chunk: string; index: number }
  | { type: "stream_end" }
  | {
      type: "response";
      text: string;
      agents_used: string[];
      eos_snapshot: EosSnapshot;
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

