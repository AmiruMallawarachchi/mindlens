"use client";

import { Reveal } from "./reveal";
import { STEPS } from "./home-copy";

export function HomeHowItWorks({}: Record<string, never>) {
  return (
    <section id="how" className="px-6 py-[60px] pb-[130px]">
        <div className="mx-auto max-w-[1200px]">
          <Reveal className="mb-14 flex flex-wrap items-end justify-between gap-4.5">
            <h2 className="m-0 max-w-[560px] font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
              What happens when you press send
            </h2>
            <p className="m-0 max-w-[360px] text-[14.5px] leading-[1.65]" style={{ color: "var(--ml-muted)" }}>
              Every message moves through the same careful pipeline — safety first, always, with no way around it.
            </p>
          </Reveal>
          <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
            {STEPS.map((step, i) => (
              <Reveal key={step.num} delay={i * 0.05}>
                <article
                  className="flex h-full min-h-[230px] flex-col gap-3.5 rounded-[22px] p-[22px]"
                  style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
                >
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11px]" style={{ color: "var(--e1)" }}>
                    {step.num}
                  </span>
                  <h3 className="ml-display m-0 text-[22px] font-normal tracking-[-.01em]">{step.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.65]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {step.body}
                  </p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

  );
}
