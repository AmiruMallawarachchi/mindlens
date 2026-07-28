"use client";

import { AlertCircle, ArrowRight, Loader2, LockKeyhole, Mail, User } from "lucide-react";
import { useState } from "react";
import { MindLensMark } from "./mindlens-mark";

type Mode = "login" | "register";

export function AuthGate({
  busy,
  error,
  onLogin,
  onRegister,
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
}) {
  const [mode, setMode] = useState<Mode>("login");
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
    <div className="auth-gate">
      <div className="auth-card glass-panel">
        <MindLensMark />

        <div className="auth-tabs" role="tablist" aria-label="Sign in or create an account">
          <button
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "is-active" : ""}
            onClick={() => setMode("login")}
            type="button"
          >
            Sign in
          </button>
          <button
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "is-active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            Create account
          </button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label className="auth-field">
              <User size={15} />
              <input
                type="text"
                placeholder="What should we call you?"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                required
                maxLength={100}
              />
            </label>
          )}

          <label className="auth-field">
            <Mail size={15} />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="auth-field">
            <LockKeyhole size={15} />
            <input
              type="password"
              placeholder={mode === "register" ? "Password (min 8 characters)" : "Password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              minLength={mode === "register" ? 8 : undefined}
              required
            />
          </label>

          {mode === "register" && (
            <label className="auth-field">
              <span className="auth-field-suffix">Age</span>
              <input
                type="number"
                placeholder="Age"
                value={age}
                onChange={(event) => setAge(event.target.value)}
                min={13}
                max={100}
                required
              />
            </label>
          )}

          {error && (
            <p className="auth-error">
              <AlertCircle size={14} />
              {error}
            </p>
          )}

          <button className="button-primary auth-submit" type="submit" disabled={busy}>
            {busy ? (
              <Loader2 size={15} className="auth-spinner" />
            ) : (
              <>
                {mode === "login" ? "Sign in" : "Start with MindLens"}
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        <p className="auth-disclaimer">
          MindLens is a wellbeing companion, not emergency or medical care.
        </p>
      </div>
    </div>
  );
}
