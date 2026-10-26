import { request } from "./api";
import type { JournalEntry, JournalEntrySummary, JournalPrompt } from "./types";

// ---------------------------------------------------------------------------
// Journal
// ---------------------------------------------------------------------------

export async function fetchJournalPrompt(): Promise<JournalPrompt> {
  return request<JournalPrompt>("/api/v1/journal/prompt");
}

export async function listJournalEntries(
  limit = 30,
): Promise<JournalEntrySummary[]> {
  return request<JournalEntrySummary[]>(`/api/v1/journal?limit=${limit}`);
}

export async function getJournalEntry(entryId: string): Promise<JournalEntry> {
  return request<JournalEntry>(`/api/v1/journal/${entryId}`);
}

export async function createJournalEntry(input: {
  title?: string;
  text: string;
  prompt_used?: string;
}): Promise<JournalEntry> {
  return request<JournalEntry>("/api/v1/journal", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateJournalEntry(
  entryId: string,
  input: { title?: string | null; text: string },
): Promise<JournalEntry> {
  return request<JournalEntry>(`/api/v1/journal/${entryId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteJournalEntry(entryId: string): Promise<void> {
  await request(`/api/v1/journal/${entryId}`, { method: "DELETE" });
}

