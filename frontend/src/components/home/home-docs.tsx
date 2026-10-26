"use client";

import { Reveal } from "./reveal";
import { DOCS, GITHUB_URL, REPO_URL } from "./home-copy";

export function HomeDocs({}: Record<string, never>) {
  return (
    <section id="docs" className="px-6 py-[130px] pb-[110px]">
        <div className="mx-auto max-w-[1200px]">
          <Reveal className="mb-[50px] flex flex-wrap items-end justify-between gap-4.5">
            <div>
              <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                {"/// Built in the open"}
              </p>
              <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,60px)" }}>
                Read the docs
              </h2>
            </div>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-[99px] px-[18px] py-2.5 font-[family-name:var(--font-geist-mono)] text-[11.5px] no-underline"
              style={{ border: "1px solid var(--ml-hairline-strong)" }}
            >
              github.com/AmiruMallawarachchi ↗
            </a>
          </Reveal>
          <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {DOCS.map((doc, i) => (
              <Reveal key={doc.file} delay={i * 0.05}>
                <a
                  href={`${REPO_URL}/blob/main/docs/${doc.file}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-full min-h-[170px] flex-col gap-3 rounded-[22px] p-6 no-underline transition-colors"
                  style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
                >
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11.5px]" style={{ color: "var(--e1)" }}>
                    {doc.file}
                  </span>
                  <h3 className="ml-display m-0 text-[22px] font-normal tracking-[-.01em]">{doc.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.6]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {doc.body}
                  </p>
                  <span className="mt-auto text-[13px] font-medium" style={{ color: "var(--e1)" }}>
                    Open →
                  </span>
                </a>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

  );
}
