"use client";

import { AlertCircle, ArrowRight, Loader2, LockKeyhole, Mail, User } from "lucide-react";
import { useState } from "react";
import { Wordmark } from "./brand/wordmark";

type Mode = "login" | "register";

export function AuthGate({
  busy,
  error,
  onLogin,
  onRegister,
  initialMode = "login",
}: {
  busy: boolean;
  error: string | null;
  onLogin: (email: string, password: string) => void;
  onRegister: (input: {
    email: string;
    password: string;
    name: string;
    age: number;
  }) => void;
  /** So a "Sign up" link (Home's nav) can land straight on the register tab
   * instead of the login one it'd otherwise default to. */
  initialMode?: Mode;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [age, setAge] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (mode === "login") {
      onLogin(email.trim(), password);
    } else {
      const parsedAge = Number.parseInt(age, 10);
      onRegister({
        email: email.trim(),
        password,
        name: name.trim(),
        age: parsedAge,
      });
    }
  };

  return (
    <div
      className="ml-root ml-grain grid min-h-screen place-items-center p-6"
      style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}
    >
      <div
        className="ml-glass w-full max-w-[400px] rounded-[var(--r-22)] p-8"
        style={{ background: "var(--ml-panel-legible)", border: "1px solid var(--ml-hairline)" }}
      >
        <div className="mb-7">
          <Wordmark size={24} />
          <p className="mt-2 text-[13px]" style={{ color: "var(--ml-muted)" }}>Think clearly. Feel fully.</p>
        </div>

        <div
          role="tablist"
          aria-label="Sign in or create an account"
          className="mb-5 inline-flex w-full rounded-[99px] p-1"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          <button
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => setMode("login")}
            type="button"
            className="flex-1 rounded-[99px] py-2 text-[13px] font-medium transition-colors"
            style={{
              background: mode === "login" ? "var(--ml-ink)" : "transparent",
              color: mode === "login" ? "var(--ml-canvas)" : "var(--ml-muted)",
            }}
          >
            Sign in
          </button>
          <button
            role="tab"
            aria-selected={mode === "register"}
            onClick={() => setMode("register")}
            type="button"
            className="flex-1 rounded-[99px] py-2 text-[13px] font-medium transition-colors"
            style={{
              background: mode === "register" ? "var(--ml-ink)" : "transparent",
              color: mode === "register" ? "var(--ml-canvas)" : "var(--ml-muted)",
            }}
          >
            Create account
          </button>
        </div>

        <form className="flex flex-col gap-3" onSubmit={submit}>
          {mode === "register" && (
            <label
              className="flex items-center gap-2.5 rounded-[var(--r-13)] px-4 py-3"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)" }}
            >
              <User size={15} style={{ color: "var(--ml-faint)" }} />
              <input
                type="text"
                placeholder="What should we call you?"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                required
                maxLength={100}
                className="min-w-0 flex-1 bg-transparent text-[14px] outline-none"
                style={{ color: "var(--ml-ink)" }}
              />
            </label>
          )}

          <label
            className="flex items-center gap-2.5 rounded-[var(--r-13)] px-4 py-3"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)" }}
          >
            <Mail size={15} style={{ color: "var(--ml-faint)" }} />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
              className="min-w-0 flex-1 bg-transparent text-[14px] outline-none"
              style={{ color: "var(--ml-ink)" }}
            />
          </label>

          <label
            className="flex items-center gap-2.5 rounded-[var(--r-13)] px-4 py-3"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)" }}
          >
            <LockKeyhole size={15} style={{ color: "var(--ml-faint)" }} />
            <input
              type="password"
              placeholder={mode === "register" ? "Password (min 8 characters)" : "Password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              minLength={mode === "register" ? 8 : undefined}
              required
              className="min-w-0 flex-1 bg-transparent text-[14px] outline-none"
              style={{ color: "var(--ml-ink)" }}
            />
          </label>

          {mode === "register" && (
            <label
              className="flex items-center gap-2.5 rounded-[var(--r-13)] px-4 py-3"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)" }}
            >
              <span className="text-[12px]" style={{ color: "var(--ml-faint)" }}>Age</span>
              <input
                type="number"
                placeholder="Age"
                value={age}
                onChange={(event) => setAge(event.target.value)}
                min={13}
                max={100}
                required
                className="min-w-0 flex-1 bg-transparent text-[14px] outline-none"
                style={{ color: "var(--ml-ink)" }}
              />
            </label>
          )}

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
            {busy ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <>
                {mode === "login" ? "Sign in" : "Start with Mindlens"}
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        <p className="mt-5 text-center text-[11px] leading-[1.5]" style={{ color: "var(--ml-faint)" }}>
          Mindlens is a wellbeing companion, not emergency or medical care.
        </p>
      </div>
    </div>
  );
}
