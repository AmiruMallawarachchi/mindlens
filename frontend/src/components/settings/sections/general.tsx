"use client";

/**
 * Settings > General — who Mindlens thinks you are and how it should talk
 * to you. Everything here reaches the empathy agent's system prompt, so
 * nothing on this screen is decoration.
 */

import { useEffect, useState } from "react";
import { PERSONALITIES } from "@/lib/personalities";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import type { MemoryPreferences } from "@/lib/types";
import { Row, SaveBar, Select, SettingsGroup, SettingsHeading, TextInput } from "../ui";
import { usePrefs } from "../use-prefs";

const KEYS: (keyof MemoryPreferences)[] = [
  "personality",
  "custom_instructions",
  "tone_preference",
];

const TONES = [
  { id: "gentle" as const, label: "Gentle", hint: "Softer landings. Warmth before the point." },
  { id: "balanced" as const, label: "Balanced", hint: "Warm, but says the hard thing when it matters." },
  { id: "direct" as const, label: "Direct", hint: "Straight to it. Kind, not cushioned." },
];

export function GeneralSection({ client }: { client: MindLensClient }) {
  const { draft, set, save, isDirty, loading, saving, justSaved, error } = usePrefs();
  const instructions = draft.custom_instructions ?? "";

  // The nickname lives on the user record, not in preferences, so it saves
  // through its own endpoint alongside the preference save below.
  const [nickname, setNickname] = useState("");
  const [savedNickname, setSavedNickname] = useState("");
  const [nicknameError, setNicknameError] = useState<string | null>(null);

  useEffect(() => {
    const current = client.user?.nickname ?? "";
    setNickname(current);
    setSavedNickname(current);
  }, [client.user?.nickname]);

  const nicknameDirty = nickname.trim() !== savedNickname;

  const saveAll = async () => {
    setNicknameError(null);
    if (nicknameDirty && nickname.trim()) {
      try {
        await client.saveNickname(nickname.trim());
        setSavedNickname(nickname.trim());
      } catch {
        setNicknameError("Couldn't save your name.");
      }
    }
    await save(KEYS);
  };

  if (loading) {
    return <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>;
  }

  return (
    <>
      <SettingsHeading>General</SettingsHeading>

      <SettingsGroup title="Profile">
        <Row
          label="Signed in as"
          description={client.user?.email ?? "—"}
          control={
            <span className="text-[13px]" style={{ color: "var(--ml-muted)" }}>
              {client.user?.name ?? ""}
            </span>
          }
        />
        <Row
          label="What should Mindlens call you?"
          description="Used when it speaks to you directly."
          control={
            <TextInput
              ariaLabel="What should Mindlens call you"
              value={nickname}
              onChange={setNickname}
              maxLength={60}
              placeholder={client.user?.name ?? "Your name"}
            />
          }
        />
        <Row
          label="What describes you best?"
          description="Changes how replies are written — an overthinker and a doer need different things from the same sentence."
          control={
            <Select
              ariaLabel="What describes you best"
              value={(draft.personality ?? "") as string}
              options={PERSONALITIES.map((p) => ({ id: p.id, label: p.label, hint: p.hint }))}
              onChange={(id) => set("personality", id)}
            />
          }
        />
        <Row
          label="Tone"
          description="How direct Mindlens should be with you."
          control={
            <Select
              ariaLabel="Tone"
              value={(draft.tone_preference ?? "balanced") as string}
              options={TONES.map((t) => ({ id: t.id as string, label: t.label, hint: t.hint }))}
              onChange={(id) => set("tone_preference", id as MemoryPreferences["tone_preference"])}
            />
          }
        />
      </SettingsGroup>

      <SettingsGroup title="Instructions for Mindlens">
        <div className="pb-4" style={{ borderBottom: "1px solid var(--ml-hairline)" }}>
          <p className="mb-3 text-[12.5px] leading-[1.55]" style={{ color: "var(--ml-muted)" }}>
            Anything it should keep in mind every time you talk. Not a place for
            anything you wouldn&rsquo;t want stored &mdash; it&rsquo;s saved with your memory and
            you can clear it here at any time.
          </p>
          <textarea
            value={instructions}
            onChange={(e) => set("custom_instructions", e.target.value)}
            maxLength={1500}
            rows={5}
            aria-label="Instructions for Mindlens"
            placeholder="e.g. I'm in my final year and stressed about my viva. Don't tell me to relax — help me make the next move small."
            className="w-full resize-none rounded-[var(--r-13)] px-3.5 py-3 text-[13px] leading-[1.6] outline-none"
            style={{
              background: "var(--ml-panel)",
              border: "1px solid var(--ml-hairline-strong)",
              color: "var(--ml-ink)",
            }}
          />
          <p className="mt-1.5 text-right text-[11px]" style={{ color: "var(--ml-faint)" }}>
            {instructions.length} / 1500
          </p>
        </div>
      </SettingsGroup>

      {(error || nicknameError) && (
        <p className="mb-3 text-[12.5px]" style={{ color: "#e08a8a" }}>
          {error ?? nicknameError}
        </p>
      )}

      <SaveBar
        onSave={saveAll}
        saving={saving}
        saved={justSaved}
        dirty={isDirty(KEYS) || nicknameDirty}
      />
    </>
  );
}
