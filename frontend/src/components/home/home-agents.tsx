"use client";

import { Reveal } from "./reveal";
import { AGENTS, ARCHITECTURE_URL } from "./home-copy";

export function HomeAgents({}: Record<string, never>) {
  return (
    <section
        id="models"
        className="relative overflow-hidden px-6 py-[110px]"
        style={{ background: "var(--ml-deep)", color: "#f7f3ec", borderRadius: "44px 44px 0 0" }}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-[10%] -top-[30%] aspect-square w-[60vw] rounded-full"
          style={{ background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 26%, transparent), transparent 70%)", filter: "blur(90px)" }}
        />
        <div className="relative mx-auto max-w-[1200px]">
          <Reveal className="mb-[54px] flex flex-wrap items-end justify-between gap-4.5">
            <div>
              <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(247,243,236,.45)" }}>
                {"/// The read"}
              </p>
              <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
                Seven graph nodes,
                <br />
                one careful response
              </h2>
              <p className="m-0 mt-4 max-w-[420px] text-[13px] leading-[1.65]" style={{ color: "rgba(247,243,236,.5)" }}>
                A bounded LangGraph workflow coordinates deterministic safety,
                hosted assessment, memory, retrieval, one specialist, and
                optional review.
              </p>
            </div>
            <a
              href={ARCHITECTURE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-[99px] px-[18px] py-2.5 font-[family-name:var(--font-geist-mono)] text-[11.5px] no-underline"
              style={{ border: "1px solid rgba(247,243,236,.2)", color: "#f7f3ec" }}
            >
              read the architecture ↗
            </a>
          </Reveal>
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
            {AGENTS.map((agent, i) => (
              <Reveal key={agent.id} delay={i * 0.05}>
                <article
                  className="flex h-full min-h-[200px] flex-col gap-3 rounded-[20px] p-5 transition-colors"
                  style={{ border: "1px solid rgba(247,243,236,.12)", background: "rgba(255,252,246,.04)" }}
                >
                  <span className="size-[10px] rounded-full" style={{ background: "linear-gradient(140deg, var(--e2), var(--e1))" }} />
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11.5px] break-all" style={{ color: "var(--e2)" }}>
                    {agent.id}
                  </span>
                  <h3 className="m-0 text-[16.5px] font-semibold tracking-[-.015em]">{agent.title}</h3>
                  <p className="m-0 text-[12.5px] leading-[1.6]" style={{ color: "rgba(247,243,236,.55)", textWrap: "pretty" }}>
                    {agent.body}
                  </p>
                </article>
              </Reveal>
            ))}
          </div>
          <Reveal delay={0.2}>
            <p className="m-0 mt-9 max-w-[640px] text-[13.5px] leading-[1.7]" style={{ color: "rgba(247,243,236,.55)" }}>
              Generation runs on Groq — a smaller open model for simple turns, a larger one when the moment is emotional or complex. Crisis turns use <span style={{ color: "var(--e2)" }}>zero</span> LLM calls: vetted templates only.
            </p>
          </Reveal>
        </div>
      </section>

  );
}
