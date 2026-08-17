"use client";

/**
 * Settings > Privacy & data.
 *
 * The most valuable thing on this screen is not a control — it's the plain
 * list of what is and isn't true. Someone deciding whether to type the thing
 * they haven't told anyone needs to be able to check the claim, so every
 * line here is one the codebase actually backs, including the limitation.
 * An accurate small promise earns more trust than an impressive vague one.
 */

import { useState } from "react";
import { Check, Download, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";
import { deleteAccount, exportAccountData } from "@/lib/api";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { Row, SettingsGroup, SettingsHeading } from "../ui";

/** All seven are guarantees, so all seven get a check. A ✗ beside "never
 * sold" would read as a failure at a glance, which is the opposite of what
 * it says.
 *
 * Every line here has to survive someone reading the source. Three of them
 * previously did not:
 *  - the sign-in line claimed the token lived in an httpOnly cookie "so page
 *    scripts can't read it". Only the refresh token does; the access token is
 *    in localStorage and sent as a Bearer header (lib/api.ts), so the exact
 *    threat model it named — script access — was not covered.
 *  - "nothing is remembered without showing up in Memory" was untrue of the
 *    conversation transcript, the mood log, and the inferred introvert score,
 *    none of which appear on that page.
 *  - "never shared" omitted that generation is a Groq API call carrying the
 *    message text. The marketing page disclosed it; this screen didn't. */
const PROMISES: string[] = [
  "Everything is scoped to your account. Every query that reads your conversations, memory, journal or moods filters by your user id.",
  "Your conversations are saved so Mindlens can pick up where you left off. Anything it *learns* from them — people, hard topics, what's helped — appears in Memory first, where you can edit or delete it.",
  "Your 7-day sign-in token is an httpOnly cookie that page scripts can't read. The short-lived access token is kept in browser storage so the app can call the API.",
  "Sign-in records keep the device name only. Logins are also audited with a one-way, unreadable hash of your IP — enough to spot a break-in attempt, not enough to locate you — and it's erased when you delete your account.",
  "In a crisis, Mindlens answers from human-written templates. Zero AI calls, every time.",
  "Your conversations are never sold or used for advertising.",
  "To write a reply, this turn's message goes to Groq, the model provider, with emails, phone numbers and ID numbers stripped first. Your first name and anyone you've told Mindlens about travel with it unstripped — that's what lets the reply sound like it knows you. Nowhere else.",
  "Mindlens never trains its own models on what you write. What Groq does with the text it receives to generate a reply is covered by Groq's terms, not this app's.",
];

export function PrivacySection({ client }: { client: MindLensClient }) {
  const [exporting, setExporting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const data = await exportAccountData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mindlens-my-data-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Couldn't build your download. Try again in a moment.");
    } finally {
      setExporting(false);
    }
  };

  const runDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(password);
      client.logout();
    } catch {
      setError("That password isn't right.");
      setDeleting(false);
    }
  };

  return (
    <>
      <SettingsHeading>Privacy &amp; data</SettingsHeading>

      <SettingsGroup title="What's true">
        <ul className="mb-2 flex flex-col gap-2.5">
          {PROMISES.map((promise) => (
            <li key={promise} className="flex items-start gap-2.5">
              <Check size={14} strokeWidth={2.2} className="mt-[3px] shrink-0" style={{ color: "#4fae6f" }} />
              <span className="text-[13px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
                {promise}
              </span>
            </li>
          ))}
        </ul>

        {/* Stating the limitation is the point. A privacy page that only
          * lists wins is the kind users stop believing. */}
        <div
          className="mt-3 flex items-start gap-2.5 rounded-[var(--r-13)] p-3.5"
          style={{
            border: "1px solid var(--ml-hairline-strong)",
            background: "var(--ml-panel)",
          }}
        >
          <ShieldCheck size={15} strokeWidth={1.8} className="mt-[2px] shrink-0" style={{ color: "var(--ml-muted)" }} />
          <p className="text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
            <strong style={{ color: "var(--ml-ink)" }}>What Mindlens is not:</strong>{" "}
            it isn&rsquo;t end-to-end encrypted. The models that read how you&rsquo;re
            feeling have to see your message to do it, so your words are
            readable on the server. That&rsquo;s the honest trade for the app
            working at all — and it&rsquo;s why the delete below is a real delete.
          </p>
        </div>
      </SettingsGroup>

      <SettingsGroup title="Your data">
        <Row
          label="Download everything"
          description="Your profile, memory, conversations, journal and mood history, as one JSON file."
          control={
            <button
              type="button"
              onClick={runExport}
              disabled={exporting}
              className="inline-flex items-center gap-2 rounded-[99px] px-4 py-2 text-[12.5px] disabled:opacity-50"
              style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
            >
              {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} strokeWidth={1.8} />}
              Export
            </button>
          }
        />

        <Row
          label="Delete your account"
          description="Erases your account and everything in it — memory, conversations, journal, mood history. This cannot be undone."
          control={
            !confirmOpen ? (
              <button
                type="button"
                onClick={() => setConfirmOpen(true)}
                className="rounded-[99px] px-4 py-2 text-[12.5px]"
                style={{ border: "1px solid color-mix(in oklab, #e08a8a 55%, transparent)", color: "#e08a8a" }}
              >
                Delete
              </button>
            ) : undefined
          }
        />

        {confirmOpen && (
          <div
            className="mt-4 rounded-[var(--r-16)] p-4"
            style={{
              border: "1px solid color-mix(in oklab, #e08a8a 45%, transparent)",
              background: "color-mix(in oklab, #e08a8a 7%, transparent)",
            }}
          >
            <p className="mb-3 flex items-start gap-2 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-ink)" }}>
              <TriangleAlert size={15} strokeWidth={1.8} className="mt-[2px] shrink-0" style={{ color: "#e08a8a" }} />
              This deletes everything immediately and permanently. Consider
              exporting your data first — afterwards there is nothing to export.
            </p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Confirm your password"
              aria-label="Confirm your password to delete your account"
              className="w-full rounded-[var(--r-11)] px-3.5 py-2 text-[13px] outline-none"
              style={{
                background: "var(--ml-panel)",
                border: "1px solid var(--ml-hairline-strong)",
                color: "var(--ml-ink)",
              }}
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={runDelete}
                disabled={deleting || !password}
                className="inline-flex items-center gap-2 rounded-[99px] px-4 py-2 text-[12.5px] font-medium disabled:opacity-50"
                style={{ background: "#e08a8a", color: "#1a1410" }}
              >
                {deleting && <Loader2 size={13} className="animate-spin" />}
                Delete everything
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmOpen(false);
                  setPassword("");
                  setError(null);
                }}
                className="rounded-[99px] px-4 py-2 text-[12.5px]"
                style={{ color: "var(--ml-muted)" }}
              >
                Keep my account
              </button>
            </div>
          </div>
        )}

        {error && (
          <p className="mt-3 text-[12.5px]" style={{ color: "#e08a8a" }}>
            {error}
          </p>
        )}
      </SettingsGroup>
    </>
  );
}
