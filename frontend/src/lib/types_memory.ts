// ---------------------------------------------------------------------------
// Memory — backend/app/routers/memory.py
// ---------------------------------------------------------------------------

export interface MemoryPerson {
  role: string;
  context: string;
  sentiment: string;
}

export interface MemoryPreferences {
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

