"use client";

import { Reveal } from "./reveal";

export function HomePhilosophy({}: Record<string, never>) {
  return (
    <section className="px-6 py-[140px]">
        <Reveal className="mx-auto max-w-[900px] text-center">
          <p className="m-0 mb-[26px] font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
            The idea Mindlens is built on
          </p>
          <p
            className="ml-display m-0"
            style={{ fontSize: "clamp(30px, 4.4vw, 52px)", lineHeight: 1.22, letterSpacing: "-.015em", fontStyle: "italic", textWrap: "balance" }}
          >
            &ldquo;Therapy did not fix me. Therapy gave me the tools to fix myself — <span style={{ color: "var(--e1)" }}>over and over again</span>, for the rest of my life.&rdquo;
          </p>
          <p className="mx-auto mt-[30px] max-w-[520px] text-[15.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
            Mindlens exists to help you build those tools: understand what you&rsquo;re feeling, regulate it, and notice yourself getting better at it.
          </p>
        </Reveal>
      </section>

  );
}
