import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useJournalPage } from "@/components/pages/use-journal-page";

const api = vi.hoisted(() => ({
  createJournalEntry: vi.fn(),
  deleteJournalEntry: vi.fn(),
  fetchJournalPrompt: vi.fn(),
  getJournalEntry: vi.fn(),
  listJournalEntries: vi.fn(),
  updateJournalEntry: vi.fn(),
}));

vi.mock("@/lib/api", () => api);

describe("useJournalPage", () => {
  it("creates an entry with the trimmed text and the shown prompt", async () => {
    api.fetchJournalPrompt.mockResolvedValue({
      prompt: "What felt heavy today?",
      date: "2026-10-30",
    });
    api.listJournalEntries.mockResolvedValue([]);
    api.createJournalEntry.mockResolvedValue({
      entry_id: "entry-1",
      title: null,
      text: "Exams.",
      prompt_used: "What felt heavy today?",
      created_at: "2026-10-30T10:00:00Z",
      updated_at: "2026-10-30T10:00:00Z",
    });

    const { result } = renderHook(() => useJournalPage());
    await waitFor(() => expect(result.current.prompt).not.toBeNull());

    act(() => result.current.setDraftText("  Exams.  "));
    await act(async () => {
      await result.current.save();
    });

    expect(api.createJournalEntry).toHaveBeenCalledWith({
      title: undefined,
      text: "Exams.",
      prompt_used: "What felt heavy today?",
    });
    expect(result.current.composerOpen).toBe(false);
  });
});
