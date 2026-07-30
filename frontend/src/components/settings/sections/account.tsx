"use client";

/**
 * Settings > Account. Session revocation, two-factor, data export and hard
 * delete land here next; for now it owns sign-out, which moved off the old
 * Your Mindlens page when that page became this modal.
 */

import type { MindLensClient } from "@/lib/use-mindlens-client";
import { Row, SettingsGroup, SettingsHeading } from "../ui";

export function AccountSection({ client }: { client: MindLensClient }) {
  return (
    <>
      <SettingsHeading>Account</SettingsHeading>

      <SettingsGroup>
        <Row label="Email" description="Sign-in address." control={
          <span className="text-[13px]" style={{ color: "var(--ml-muted)" }}>
            {client.user?.email ?? "—"}
          </span>
        } />
        <Row
          label="Sign out"
          description="Ends this session on this device."
          control={
            <button
              type="button"
              onClick={client.logout}
              className="rounded-[99px] px-4 py-2 text-[12.5px]"
              style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-muted)" }}
            >
              Log out
            </button>
          }
        />
      </SettingsGroup>

      <p className="text-[11px] leading-[1.6]" style={{ color: "var(--ml-faint)" }}>
        Crisis support always uses a stable, high-clarity view — none of your
        settings change how a crisis is handled.
      </p>
    </>
  );
}
