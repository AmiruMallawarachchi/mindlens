"use client";

import { useState } from "react";
import { AlertCircle, Loader2, ShieldAlert } from "lucide-react";
import { adminLogin } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";

export function AdminLoginForm({ onSignedIn }: { onSignedIn: () => void }) {
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
      setError(err instanceof ApiError ? err.message : "Couldn't reach MindLens.");
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

