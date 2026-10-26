"use client";

import { Reveal } from "./reveal";
import { EMOTION_ORDER, EMOTION_STATES, type EmotionId } from "@/lib/emotion";

export function HomeEmotionLab({activeId, setActiveId, activeName, activeSubs}: { activeId: EmotionId | null; setActiveId: (id: EmotionId | null) => void; activeName: string; activeSubs: readonly string[] }) {
  return (
    <section
        id="emotions"
        className="relative overflow-hidden px-6 py-[130px]"
        style={{ background: "var(--ml-deep)", color: "#f7f3ec", borderRadius: "0 0 44px 44px" }}
      >
        <div className="relative mx-auto max-w-[1200px]">
          <Reveal className="mb-[54px] text-center">
            <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(247,243,236,.45)" }}>
              {"/// One room, twelve weathers"}
            </p>
            <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
              The interface is lit
              <br />
              by what you feel
            </h2>
            <p className="mx-auto mt-5 max-w-[520px] text-[14.5px] leading-[1.65]" style={{ color: "rgba(247,243,236,.55)", textWrap: "pretty" }}>
              Tap a state. The field, the shadows and every accent on this page crossfade over 1.6 seconds — nothing ever snaps.
            </p>
          </Reveal>
          <div className="grid items-stretch gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            <Reveal className="grid content-center gap-2.5" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              {EMOTION_ORDER.map((id) => {
                const state = EMOTION_STATES[id];
                const isActive = activeId === id;
                return (
                  <button
                    key={id}
                    type="button"
                    title={state.name}
                    onClick={() => setActiveId(isActive ? null : id)}
                    className="h-[74px] cursor-pointer rounded-2xl transition-transform hover:scale-105"
                    style={{
                      border: isActive ? "2px solid #fffdf8" : "1px solid rgba(247,243,236,.15)",
                      background: `linear-gradient(140deg, ${state.c1}, ${state.c2})`,
                      opacity: isActive || activeId === null ? 1 : 0.72,
                    }}
                  >
                    <span className="sr-only">{state.name}</span>
                  </button>
                );
              })}
            </Reveal>
            <Reveal
              delay={0.1}
              className="relative flex min-h-[420px] flex-col justify-end overflow-hidden rounded-[26px] p-[26px]"
              style={{
                border: "1px solid rgba(247,243,236,.12)",
                background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 60%, var(--ml-deep)), color-mix(in oklab, var(--e3) 80%, var(--ml-deep)))",
                transition: "background 1.6s cubic-bezier(.22,.61,.36,1)",
              }}
            >
              <div className="relative">
                <p className="m-0 mb-1.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(255,253,248,.6)" }}>
                  Current read
                </p>
                <p className="ml-display m-0 text-[46px] font-light tracking-[-.02em]" style={{ color: "#fffdf8" }}>
                  {activeName}
                </p>
                <div className="mt-3.5 flex flex-wrap gap-2">
                  {activeSubs.map((sub) => (
                    <span
                      key={sub}
                      className="rounded-[99px] px-3 py-[5px] text-[11.5px]"
                      style={{ border: "1px solid rgba(255,253,248,.35)", color: "rgba(255,253,248,.85)" }}
                    >
                      {sub}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

  );
}
