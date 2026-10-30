import type { ChatMessage, SessionTurn } from "./types";

export function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Turns persisted session rows into the client chat message shape. */
export function hydrateMessages(turns: SessionTurn[]): ChatMessage[] {
  return turns.map((turn, index) => ({
    id: `${turn.timestamp}-${index}`,
    role: turn.role,
    text: turn.text,
    eos: turn.eos_snapshot,
    agentsUsed: turn.agents_used,
    crisis: turn.crisis_flag,
  }));
}
