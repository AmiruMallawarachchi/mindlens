"use client";

import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { COMPANIONS } from "@/lib/companions";
import { EMOTION_ORDER } from "@/lib/emotion";
import type { EmotionId } from "@/lib/emotion";
import { Reveal } from "./reveal";

export function HomePortraitBand({reduceMotion, activeId}: { reduceMotion: boolean | null; activeId: EmotionId | null }) {
  return (
    <section className="px-6">
        <Reveal
          className="ml-grain relative mx-auto h-[min(72vh,560px)] max-w-[1200px] overflow-hidden rounded-[30px]"
          delay={0.1}
        >
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 30%, var(--ml-canvas)), color-mix(in oklab, var(--e2) 24%, var(--ml-canvas)))",
              boxShadow: "0 34px 80px -30px color-mix(in oklab, var(--e1) 60%, rgba(36,26,14,.4))",
            }}
          />
          {!reduceMotion && (
            <>
              <span
                aria-hidden="true"
                className="absolute left-[6%] top-[10%] aspect-square w-[52%] rounded-full"
                style={{
                  background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 65%, transparent), transparent 70%)",
                  filter: "blur(60px)",
                  animation: "mlBlobA 18s ease-in-out infinite",
                }}
              />
              <span
                aria-hidden="true"
                className="absolute right-[2%] bottom-[6%] aspect-square w-[48%] rounded-full"
                style={{
                  background: "radial-gradient(circle, color-mix(in oklab, var(--e2) 60%, transparent), transparent 70%)",
                  filter: "blur(70px)",
                  animation: "mlBlobB 24s ease-in-out infinite",
                }}
              />
            </>
          )}
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(120% 90% at 50% 100%, transparent 40%, color-mix(in oklab, var(--ml-deep) 55%, transparent) 100%)",
            }}
          />
          <div className="absolute inset-0 grid place-items-center">
            <CompanionAvatar
              companionId={COMPANIONS[activeId ? EMOTION_ORDER.indexOf(activeId) % COMPANIONS.length : 0].id}
              activity="idle"
              size={200}
              withShadow
            />
          </div>
          <div
            className="absolute left-7 bottom-6 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]"
            style={{ color: "#fffdf8", textShadow: "0 1px 12px rgba(0,0,0,.35)" }}
          >
            The room is listening
          </div>
        </Reveal>
      </section>

  );
}
