"use client";

/**
 * Settings > Account. Email, the devices signed in, and sign-out.
 *
 * The session list is the security control most likely to actually be used:
 * "is that me?" is a question a person can answer, unlike anything involving
 * key material. Deliberately shows device and time only — no IP or location,
 * because storing a location history to power a settings screen would
 * contradict the promise the screen exists to demonstrate.
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, MonitorSmartphone } from "lucide-react";
import {
  listDeviceSessions,
  revokeDeviceSession,
  revokeOtherDeviceSessions,
  type DeviceSession,
} from "@/lib/api";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { Row, SettingsGroup, SettingsHeading } from "../ui";

export function AccountSection({ client }: { client: MindLensClient }) {
  const [sessions, setSessions] = useState<DeviceSession[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listDeviceSessions()
      .then(setSessions)
      .catch(() => setError("Couldn't load your devices."));
  }, []);

  useEffect(load, [load]);

  const revokeOne = async (jti: string) => {
    setBusy(jti);
    setError(null);
    try {
      await revokeDeviceSession(jti);
      load();
    } catch {
      setError("Couldn't sign that device out.");
    } finally {
      setBusy(null);
    }
  };

  const revokeOthers = async () => {
    setBusy("others");
    setError(null);
    try {
      await revokeOtherDeviceSessions();
      load();
    } catch {
      setError("Couldn't sign the other devices out.");
    } finally {
      setBusy(null);
    }
  };

  const others = (sessions ?? []).filter((s) => !s.current).length;

  return (
    <>
      <SettingsHeading>Account</SettingsHeading>

      <SettingsGroup>
        <Row
          label="Email"
          description="You sign in with this."
          control={
            <span className="text-[13px]" style={{ color: "var(--ml-muted)" }}>
              {client.user?.email ?? "—"}
            </span>
          }
        />
      </SettingsGroup>

      <SettingsGroup title="Where you're signed in">
        <p className="mb-3 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
          If you don&rsquo;t recognise one of these, sign it out — that device is
          signed out immediately and has to log in again.
        </p>

        {error && (
          <p className="mb-3 text-[12.5px]" style={{ color: "#e08a8a" }}>
            {error}
          </p>
        )}

        {sessions === null ? (
          <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
        ) : (
          <div className="flex flex-col">
            {sessions.map((session) => (
              <Row
                key={session.jti}
                label={session.device}
                description={
                  <>
                    Signed in{" "}
                    {new Date(session.created_at).toLocaleDateString(undefined, {
                      day: "numeric",
                      month: "short",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                    {session.current && " · this device"}
                  </>
                }
                control={
                  session.current ? (
                    <span
                      className="rounded-[99px] px-2.5 py-1 text-[11px]"
                      style={{
                        border: "1px solid color-mix(in oklab, var(--e1) 45%, transparent)",
                        color: "var(--e1)",
                      }}
                    >
                      Current
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => revokeOne(session.jti)}
                      disabled={busy === session.jti}
                      className="inline-flex items-center gap-1.5 rounded-[99px] px-3.5 py-1.5 text-[12.5px] disabled:opacity-50"
                      style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-muted)" }}
                    >
                      {busy === session.jti && <Loader2 size={12} className="animate-spin" />}
                      Sign out
                    </button>
                  )
                }
              />
            ))}

            {others > 0 && (
              <div className="pt-4">
                <button
                  type="button"
                  onClick={revokeOthers}
                  disabled={busy === "others"}
                  className="inline-flex items-center gap-2 rounded-[99px] px-4 py-2 text-[12.5px] disabled:opacity-50"
                  style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
                >
                  {busy === "others" ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <MonitorSmartphone size={13} strokeWidth={1.8} />
                  )}
                  Sign out {others === 1 ? "the other device" : `all ${others} other devices`}
                </button>
              </div>
            )}
          </div>
        )}
      </SettingsGroup>

      <SettingsGroup>
        <Row
          label="Sign out"
          description="Ends this session on this device only."
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
