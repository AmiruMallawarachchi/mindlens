"use client";

import { Reveal } from "./reveal";
import { RULES } from "./home-copy";

export function HomeSafety({}: Record<string, never>) {
  return (
    <section id="safety" className="px-6 pb-[130px] pt-10">
        <div className="mx-auto grid max-w-[1200px] gap-10" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          <Reveal>
            <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
              {"/// Safety & privacy"}
            </p>
            <h2 className="m-0 mb-5 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,60px)" }}>
              The non-negotiables
            </h2>
            <p className="m-0 max-w-[420px] text-[14.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
              MindLens is support software. It is not a clinical service, a diagnostic tool, or an emergency service — and it is built so it can never quietly pretend to be one.
            </p>
            <div
              className="mt-[26px] rounded-[18px] px-[18px] py-4"
              style={{ border: "1px solid color-mix(in oklab, #ff6941 45%, transparent)", background: "color-mix(in oklab, #ff6941 8%, transparent)" }}
            >
              <p className="m-0 text-[13px] leading-[1.65]">
                <strong className="font-semibold">In immediate danger?</strong> Contact your local emergency services. MindLens always surfaces real human resources first, before anything else.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.1} className="flex flex-col">
            {RULES.map((rule) => (
              <div key={rule.num} className="flex gap-4 py-[18px]" style={{ borderBottom: "1px solid var(--ml-hairline)" }}>
                <span className="whitespace-nowrap pt-[3px] font-[family-name:var(--font-geist-mono)] text-[11px]" style={{ color: "var(--e1)" }}>
                  {rule.num}
                </span>
                <div>
                  <h3 className="m-0 mb-1 text-[15.5px] font-semibold tracking-[-.01em]">{rule.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.6]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {rule.body}
                  </p>
                </div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

  );
}
