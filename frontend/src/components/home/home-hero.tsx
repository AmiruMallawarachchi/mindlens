"use client";

import Link from "next/link";
import { Magnetic } from "./magnetic";
import { Reveal } from "./reveal";
import { EMOTION_ORDER, EMOTION_STATES } from "@/lib/emotion";

export function HomeHero({reduceMotion}: { reduceMotion: boolean | null }) {
  return (
    <header
        id="top"
        className="relative flex min-h-[100dvh] flex-col items-center justify-center overflow-hidden px-6 pb-[60px] pt-[120px]"
      >
        <div
          className="mb-auto flex w-full max-w-[1200px] justify-between font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]"
          style={{ color: "var(--ml-faint)" }}
        >
          <span>{"/// Mindlens"}</span>
          <span>Personal wellbeing companion</span>
        </div>

        <Reveal className="relative my-auto max-w-[1100px] text-center">
          <h1
            className="m-0 font-semibold leading-[.98] tracking-[-.045em]"
            style={{ fontSize: "clamp(58px, 9.5vw, 148px)", textWrap: "balance" }}
          >
            See what
            <span
              aria-hidden="true"
              className="mx-[.06em] inline-block h-[.55em] w-[.55em] align-baseline"
              style={{
                borderRadius: "38% 62% 55% 45% / 45% 40% 60% 55%",
                background: "linear-gradient(140deg, var(--e2), var(--e1))",
                boxShadow: "0 18px 44px -12px var(--e1)",
              }}
            />
            you feel.
          </h1>
          <p
            className="mx-auto mt-7 max-w-[560px] text-[17px] leading-[1.65]"
            style={{ color: "var(--ml-muted)", textWrap: "pretty" }}
          >
            A wise friend that reads the feeling underneath your words, remembers what matters, and helps you build the tools to steady yourself — over and over, for life.
          </p>
          <div className="mt-[34px] flex flex-wrap justify-center gap-3">
            <Magnetic>
              <Link
                href="/app"
                className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
                style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)", boxShadow: "0 18px 40px -16px var(--e1)" }}
              >
                Start a conversation
              </Link>
            </Magnetic>
            <Magnetic>
              <a
                href="#how"
                className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", backdropFilter: "blur(12px)" }}
              >
                Read how it works
              </a>
            </Magnetic>
          </div>
          <p className="mt-[22px] font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
            Free · Yours alone, not encrypted end-to-end · Not a replacement for professional care
          </p>
        </Reveal>

        <div
          className="relative mt-auto w-full max-w-[1200px] overflow-hidden"
          style={{ maskImage: "linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)", WebkitMaskImage: "linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)" }}
        >
          <div
            className="flex w-max gap-[34px] py-2"
            style={{ animation: reduceMotion ? undefined : "mlMarquee 36s linear infinite" }}
          >
            {[...EMOTION_ORDER, ...EMOTION_ORDER].map((id, i) => {
              const state = EMOTION_STATES[id];
              return (
                <span
                  key={`${id}-${i}`}
                  className="inline-flex items-center gap-2.5 whitespace-nowrap font-[family-name:var(--font-geist-mono)] text-[11px] uppercase tracking-[.12em]"
                  style={{ color: "var(--ml-muted)" }}
                >
                  <span
                    className="size-[9px] rounded-full"
                    style={{ background: `linear-gradient(140deg, ${state.c1}, ${state.c2})` }}
                  />
                  {state.name}
                </span>
              );
            })}
          </div>
        </div>
      </header>

  );
}
