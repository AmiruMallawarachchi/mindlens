"use client";

/**
 * Onboarding — shown once, right after register/login, whenever
 * onboarding_complete is false. Backend's /api/v1/onboarding/complete
 * creates the user_memory document memory_recall.py depends on for every
 * turn's personalization, so this isn't just a welcome screen: skipping it
 * means the memory system never has anything to read.
 *
 * Three short steps (nickname, up to two people, check-in time) — name and
 * age are already known from registration, so they're not asked again.
 */

import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { MindlensMark } from "@/components/brand/wordmark";
import type { OnboardingInput, UserProfile } from "@/lib/types";

type CheckinTime = OnboardingInput["checkin_preferred_time"];

const CHECKIN_OPTIONS: { id: CheckinTime; label: string }[] = [
  { id: "morning", label: "Morning" },
  { id: "evening", label: "Evening" },
  { id: "whenever", label: "Whenever" },
];

export function OnboardingFlow({
  user,
  busy,
  error,
  onComplete,
}: {
  user: UserProfile;
  busy: boolean;
  error: string | null;
  onComplete: (input: OnboardingInput) => void;
}) {
  const [step, setStep] = useState(0);
  const [nickname, setNickname] = useState(user.nickname || user.name);
  const [personName, setPersonName] = useState("");
  const [personRole, setPersonRole] = useState("");
  const [personContext, setPersonContext] = useState("");
  const [checkin, setCheckin] = useState<CheckinTime>("evening");

  const steps = ["What should we call you", "Who's important to you", "When should we check in"];
  const canAdvance = step === 0 ? nickname.trim().length > 0 : step === 1 ? personName.trim().length > 0 : true;

  const next = () => {
    if (step < steps.length - 1) {
      setStep((s) => s + 1);
      return;
    }
    onComplete({
      name: user.name,
      age: user.age,
      nickname: nickname.trim(),
      people: [
        {
          name: personName.trim(),
          role: personRole.trim() || "someone close to you",
          context: personContext.trim() || undefined,
        },
      ],
      checkin_preferred_time: checkin,
    });
  };

  return (
    <div className="ml-root grid min-h-screen place-items-center p-4" style={{ background: "var(--ml-canvas)" }}>
      <div className="ml-glass w-full max-w-[440px] rounded-[var(--r-24)] p-8">
        <div className="mb-6 flex items-center justify-between">
          <MindlensMark size={26} />
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <span
                key={i}
                className="h-[5px] w-6 rounded-full transition-colors"
                style={{ background: i <= step ? "var(--e1)" : "var(--ml-hairline-strong)" }}
              />
            ))}
          </div>
        </div>

        <p className="ml-eyebrow mb-1.5">Step {step + 1} of {steps.length}</p>
        <h1 className="ml-display mb-6 text-[22px]" style={{ color: "var(--ml-ink)" }}>
          {steps[step]}?
        </h1>

        {step === 0 && (
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Nickname</span>
            <input
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder={user.name}
              maxLength={100}
              autoFocus
              className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
            />
          </label>
        )}

        {step === 1 && (
          <div className="flex flex-col gap-3">
            <p className="text-[12.5px]" style={{ color: "var(--ml-muted)" }}>
              One person Mindlens should know about — a friend, family member, anyone who comes up often. You can add more later in Memory.
            </p>
            <label className="flex flex-col gap-1.5">
              <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Name</span>
              <input
                value={personName}
                onChange={(e) => setPersonName(e.target.value)}
                placeholder="Ravi"
                maxLength={100}
                autoFocus
                className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Who are they to you?</span>
              <input
                value={personRole}
                onChange={(e) => setPersonRole(e.target.value)}
                placeholder="Best friend"
                maxLength={100}
                className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[12px]" style={{ color: "var(--ml-muted)" }}>Anything worth knowing? (optional)</span>
              <input
                value={personContext}
                onChange={(e) => setPersonContext(e.target.value)}
                placeholder="Also doing the same exam"
                maxLength={200}
                className="rounded-[99px] px-4 py-3 text-[15px] outline-none"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
              />
            </label>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-2">
            {CHECKIN_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setCheckin(opt.id)}
                className="rounded-[var(--r-13)] p-3.5 text-left text-[14px] font-medium transition-colors"
                style={{
                  border: checkin === opt.id ? "1.5px solid var(--e1)" : "1px solid var(--ml-hairline)",
                  background: checkin === opt.id ? "color-mix(in oklab, var(--e1) 8%, transparent)" : "transparent",
                  color: "var(--ml-ink)",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {error && (
          <p className="mt-4 text-[12.5px]" style={{ color: "#ff6b6b" }}>{error}</p>
        )}

        <div className="mt-7 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0 || busy}
            className="text-[12.5px] disabled:opacity-0"
            style={{ color: "var(--ml-muted)" }}
          >
            Back
          </button>
          <button
            type="button"
            onClick={next}
            disabled={!canAdvance || busy}
            className="inline-flex items-center gap-2 rounded-[99px] px-5 py-2.5 text-[13px] font-medium disabled:opacity-50"
            style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
          >
            {busy ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <>
                {step === steps.length - 1 ? "Start" : "Next"}
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
