"use client";

import { useState } from "react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { COMPANIONS, type CompanionActivity } from "@/lib/companions";
import { EMOTION_ORDER, EMOTION_STATES, emotionCssVars, RESTING_READING } from "@/lib/emotion";

const STATES: CompanionActivity[] = ["idle", "listening", "sending", "thinking", "asking", "celebrating"];

export default function Lab() {
  const [ei, setEi] = useState<number>(EMOTION_ORDER.indexOf("balanced"));
  const state = EMOTION_STATES[EMOTION_ORDER[ei]];
  const vars = emotionCssVars({ ...RESTING_READING, state, intensity: 0.75 });

  return (
    <div className="ml-root min-h-dvh p-8" style={{ ...(vars as React.CSSProperties), background: "var(--ml-canvas)" }}>
      <div className="mb-6 flex gap-2">
        {EMOTION_ORDER.map((id, i) => (
          <button
            key={id}
            onClick={() => setEi(i)}
            className="size-6 rounded-full"
            style={{ background: `linear-gradient(135deg, ${EMOTION_STATES[id].c1}, ${EMOTION_STATES[id].c2})`, outline: i === ei ? "2px solid var(--ml-ink)" : "none" }}
          />
        ))}
      </div>
      <div className="grid gap-px" style={{ gridTemplateColumns: `130px repeat(${STATES.length}, minmax(0,1fr))`, background: "var(--ml-hairline)" }}>
        <div style={{ background: "var(--ml-canvas)" }} />
        {STATES.map((s) => (
          <div key={s} className="p-2 text-[11px]" style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}>
            {s}
          </div>
        ))}
        {COMPANIONS.map((c) => (
          <>
            <div key={c.id} className="p-2 text-[13px]" style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}>
              {c.name}
            </div>
            {STATES.map((s) => (
              <div
                key={c.id + s}
                data-cell={`${c.id}-${s}`}
                className="grid h-[190px] place-items-center"
                style={{ background: "var(--ml-canvas)" }}
              >
                <CompanionAvatar companionId={c.id} activity={s} size={110} />
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  );
}
