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

