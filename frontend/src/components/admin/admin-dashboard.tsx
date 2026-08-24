"use client";

/**
 * Admin ops dashboard — /admin, not linked from the product UI.
 *
 * Deliberately reads no user data: no accounts, no emails, no
 * conversations, no memory. Only what backend/app/routers/system.py
 * exposes — model health, database connectivity, environment/release.
 * That restraint is the point in a mental-health app: this page adds no
 * new privacy claim to defend. If a user list is ever needed, it is a
 * separate, harder decision — not a checkbox on this one.
 *
 * Auth is a completely separate token from the product's — see
 * lib/admin-api.ts for why it can't reuse lib/api.ts's client.
 */

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, LogOut, RefreshCw, ShieldAlert } from "lucide-react";
import { MindlensMark } from "@/components/brand/wordmark";
import { adminLogin, adminLogout, fetchAdminSystem, hasAdminSession } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { AdminModelHealth, AdminSystemStatus } from "@/lib/types";

export function AdminDashboard() {
  const [signedIn, setSignedIn] = useState(hasAdminSession);
  const [status, setStatus] = useState<AdminSystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminSystem();
      setStatus(data);
      setLastChecked(new Date());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSignedIn(false);
        setStatus(null);
      } else {
        setError(err instanceof ApiError ? err.message : "Couldn't reach Mindlens.");
      }
    } finally {
      setLoading(false);
    }
  };

  // SystemPanel's own mount effect covers both entry paths — a fresh sign-in
  // and a reload where sessionStorage already held a token — so this just
  // flips the gate rather than also triggering the fetch itself.
  const handleSignedIn = () => setSignedIn(true);

  const handleLogout = () => {
    adminLogout();
    setSignedIn(false);
    setStatus(null);
    setLastChecked(null);
  };

  return (
    <div
      className="ml-root ml-grain min-h-screen p-6"
      style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}
    >
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-6 pt-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <MindlensMark size={22} />
            <span className="ml-eyebrow">Admin</span>
          </div>
          {signedIn && (
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-[var(--r-pill)] px-3 py-1.5 text-[12px] transition-colors hover:bg-white/[0.04]"
              style={{ color: "var(--ml-muted)", border: "1px solid var(--ml-hairline)" }}
            >
              <LogOut size={13} strokeWidth={1.8} />
              Sign out
            </button>
          )}
        </div>

        {!signedIn ? (
          <AdminLoginForm onSignedIn={handleSignedIn} />
        ) : (
          <SystemPanel
            status={status}
            error={error}
            loading={loading}
            lastChecked={lastChecked}
            onRefresh={load}
          />
        )}
      </div>
    </div>
  );
}

function AdminLoginForm({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await adminLogin(email.trim(), password);
      onSignedIn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach Mindlens.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="ml-glass mx-auto w-full max-w-[380px] rounded-[var(--r-22)] p-8"
      style={{ background: "var(--ml-panel-legible)", border: "1px solid var(--ml-hairline)" }}
    >
      <div className="mb-2 flex items-center gap-2" style={{ color: "var(--ml-muted)" }}>
        <ShieldAlert size={16} strokeWidth={1.8} />
        <p className="ml-eyebrow">Admin sign in</p>
      </div>
      <p className="mb-6 text-[12.5px]" style={{ color: "var(--ml-faint)" }}>
        A separate token from your normal account, valid for one hour. Requires
        an account with admin access.
      </p>

      <form className="flex flex-col gap-3" onSubmit={submit}>
        <label className="flex flex-col gap-1.5">
          <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            autoFocus
            className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
          />
        </label>

        {error && (
          <p className="flex items-center gap-2 text-[12.5px]" style={{ color: "#e08a8a" }}>
            <AlertCircle size={14} />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-[99px] py-3 text-[14px] font-medium disabled:opacity-60"
          style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
        >
          {busy ? <Loader2 size={15} className="animate-spin" /> : "Sign in"}
        </button>
      </form>
    </div>
  );
}

function SystemPanel({
  status,
  error,
  loading,
  lastChecked,
  onRefresh,
}: {
  status: AdminSystemStatus | null;
  error: string | null;
  loading: boolean;
  lastChecked: Date | null;
  onRefresh: () => void;
}) {
  // Covers both ways this panel can appear: a fresh sign-in, and a reload
  // where sessionStorage already held a token so the parent mounted
  // straight into the signed-in state.
  useEffect(() => {
    onRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="ml-display text-[19px]">System</p>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-[var(--r-pill)] px-3.5 py-2 text-[12.5px] transition-colors hover:bg-white/[0.04] disabled:opacity-60"
          style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {loading ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <RefreshCw size={13} strokeWidth={1.8} />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div
          className="flex items-center gap-2 rounded-[var(--r-16)] p-4 text-[13px]"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)", color: "#e08a8a" }}
        >
          <AlertCircle size={15} />
          {error}
        </div>
      )}

      {!status && !error && (
        <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
      )}

      {status && (
        <>
          <div
            className="rounded-[var(--r-18)] p-5"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <p className="ml-eyebrow mb-3">Environment</p>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Environment" value={status.environment} />
              <Field label="Release" value={status.release} mono />
              <Field
                label="Database"
                value={status.database}
                tone={status.database === "connected" ? "good" : "bad"}
              />
            </div>
          </div>

          <div
            className="rounded-[var(--r-18)] p-5"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <p className="ml-eyebrow mb-3">Models</p>
            <div className="flex flex-col gap-2">
              {Object.entries(status.models).map(([name, health]) => (
                <ModelRow key={name} name={name} health={health} />
              ))}
            </div>
          </div>
        </>
      )}

      {lastChecked && (
        <p className="text-[11px]" style={{ color: "var(--ml-faint)" }}>
          Last checked {lastChecked.toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good" ? "#7fd8a8" : tone === "bad" ? "#e08a8a" : "var(--ml-ink)";
  return (
    <div>
      <p className="text-[10.5px]" style={{ color: "var(--ml-faint)" }}>{label}</p>
      <p className={mono ? "ml-num mt-0.5 text-[13.5px]" : "mt-0.5 text-[13.5px]"} style={{ color }}>
        {value}
      </p>
    </div>
  );
}

function ModelRow({ name, health }: { name: string; health: AdminModelHealth }) {
  // A model that isn't "ready", or has ever errored, is exactly what would
  // have made this week's silent all-classifiers-failing bug visible at a
  // glance instead of showing up as generic replies with no obvious cause.
  const flagged = health.status !== "ready" || health.error_count > 0;
  return (
    <div
      className="flex items-center justify-between rounded-[var(--r-13)] px-3.5 py-2.5"
      style={{
        background: flagged ? "color-mix(in oklab, #e08a8a 10%, transparent)" : "var(--ml-panel-strong)",
        border: `1px solid ${flagged ? "#e08a8a" : "var(--ml-hairline)"}`,
      }}
    >
      <div className="min-w-0">
        <p className="text-[13px]" style={{ color: "var(--ml-ink)" }}>{name}</p>
        <p className="ml-num mt-0.5 truncate text-[11px]" style={{ color: "var(--ml-faint)" }}>
          {health.model_id}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-right">
        {health.error_count > 0 && (
          <span className="text-[11px]" style={{ color: "#e08a8a" }}>
            {health.error_count} error{health.error_count === 1 ? "" : "s"}
          </span>
        )}
        <span
          className="ml-num rounded-[var(--r-pill)] px-2.5 py-1 text-[11px]"
          style={{
            background: flagged ? "transparent" : "color-mix(in oklab, #7fd8a8 16%, transparent)",
            color: flagged ? "#e08a8a" : "#7fd8a8",
          }}
        >
          {health.status}
        </span>
      </div>
    </div>
  );
}
