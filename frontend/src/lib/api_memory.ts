import { request } from "./api";
import type { MemoryDoc, MemoryPreferences } from "./types";

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export async function fetchMemory(): Promise<MemoryDoc> {
  return request<MemoryDoc>("/api/v1/memory");
}

export async function updateMemoryPreferences(
  prefs: MemoryPreferences,
): Promise<void> {
  await request("/api/v1/memory/preferences", {
    method: "PATCH",
    body: JSON.stringify(prefs),
  });
}

export async function updateMemoryPeople(
  people: Record<string, { role: string; context: string; sentiment: string }>,
): Promise<void> {
  await request("/api/v1/memory/people", {
    method: "PATCH",
    body: JSON.stringify({ people }),
  });
}

export async function addMemoryNote(text: string): Promise<{ note_id: string }> {
  return request<{ note_id: string; message: string }>("/api/v1/memory/notes", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function deleteMemoryNote(noteId: string): Promise<void> {
  await request(`/api/v1/memory/notes/${noteId}`, { method: "DELETE" });
}

export async function deleteMemoryEntry(
  section: "people" | "trigger_topics" | "effective_coping" | "milestones" | "raw_notes",
  key: string,
): Promise<void> {
  await request("/api/v1/memory/delete_entry", {
    method: "POST",
    body: JSON.stringify({ section, key }),
  });
}
