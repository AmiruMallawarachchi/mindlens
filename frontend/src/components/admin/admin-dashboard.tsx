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

import { useState } from "react";
import { LogOut } from "lucide-react";
import { MindlensMark } from "@/components/brand/wordmark";
import { AdminLoginForm } from "./admin-login-form";
import { SystemPanel } from "./admin-system-panel";
import { adminLogout, fetchAdminSystem, hasAdminSession } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { AdminSystemStatus } from "@/lib/types";

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
        setError(err instanceof ApiError ? err.message : "Couldn't reach MindLens.");
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


