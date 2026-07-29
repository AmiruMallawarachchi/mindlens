"use client";

/**
 * Crisis panel — ported from the approved mockup (Mindlens Chat.dc.html,
 * "Crisis panel"): warm-bordered panel on the standard surface, "Let's pause
 * here" eyebrow, Newsreader lede, contact rows with mono numbers, and the
 * template-only disclosure line.
 *
 * §6 still holds: nothing in this panel animates, and the crisis accent is
 * a fixed warm tone (#d14a24 / rgba(255,105,65)) rather than the live
 * emotion channel — the caller freezes --e1/--e2 to the resting state, and
 * this panel doesn't read them anyway.
 *
 * The resources are whatever the backend's crisis template sent. This
 * component never substitutes, reorders or supplements them.
 */

import type { CrisisResource } from "@/lib/types";

export function CrisisPanel({
  text,
  resources,
  onDismiss,
}: {
  text: string;
  resources: CrisisResource[];
  onDismiss: () => void;
}) {
  return (
    <section
      role="alert"
      aria-live="assertive"
      className="rounded-[20px] p-[22px]"
      style={{
        border: "1.5px solid rgba(255,105,65,.55)",
        background: "var(--ml-panel-legible)",
        boxShadow: "0 20px 50px -24px rgba(255,105,65,.5)",
      }}
    >
      <p className="m-0 mb-1.5 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.14em]" style={{ color: "#d14a24" }}>
        Let&rsquo;s pause here
      </p>
      <p
        className="m-0 mb-3.5 font-[family-name:var(--font-newsreader)] text-[19px] leading-[1.45]"
        style={{ color: "var(--ml-ink)", textWrap: "pretty" }}
      >
        {text}
      </p>

      {resources.length > 0 && (
        <div className="mb-3.5 flex flex-col gap-2">
          {resources.map((resource) => (
            <a
              key={`${resource.name}-${resource.number}`}
              href={`tel:${resource.number.replace(/[^\d+]/g, "")}`}
              className="flex justify-between gap-3 rounded-[13px] border px-3.5 py-[11px] text-[13px] no-underline transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_4%,transparent)]"
              style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
            >
              <span>{resource.name}</span>
              <span className="font-[family-name:var(--font-geist-mono)] text-[12.5px]">
                {resource.number}
              </span>
            </a>
          ))}
        </div>
      )}

      <p className="m-0 text-[11.5px]" style={{ color: "var(--ml-faint)" }}>
        This message was written by people, not generated. Mindlens makes no
        model calls during a crisis.
      </p>

      <button
        type="button"
        onClick={onDismiss}
        className="mt-4 cursor-pointer rounded-[99px] bg-transparent px-4 py-2 text-[12.5px]"
        style={{
          border: "1px solid var(--ml-hairline-strong)",
          color: "var(--ml-muted)",
        }}
      >
        Continue the conversation
      </button>
    </section>
  );
}
