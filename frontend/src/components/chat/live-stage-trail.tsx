"use client";

/**
 * The genuinely live version of the reasoning trail.
 *
 * orchestrator.run_full_pipeline used to run to completion — safety, the
 * emotion read, memory recall, retrieval, agent selection, all of it —
 * before the router streamed anything at all. thinking_update, which the
 * rest of the trail is built from, is sent only once that whole pipeline
 * has already finished. So there was no "one by one" to watch: the trail
 * simply appeared complete the instant it existed.
 *
 * The backend now emits a `stage_update` frame as each stage genuinely
 * finishes (orchestrator's `on_stage` callback). This renders those frames
 * as they arrive — one row growing into the next, in real time — and steps
 * aside the moment the full trail (ReasoningTrail, fed by thinking_update)
 * is ready to take over. No animation here fakes progress on work that
 * already happened; every row appears exactly when the stage it names did.
 */

import { motion, AnimatePresence } from "motion/react";

const STAGE_LABELS: Record<string, string> = {
  safety: "Safety gate",
  reading: "Emotion read",
  memory: "Memory",
  retrieval: "Therapy notes",
  approach: "Approach",
};

export function LiveStageTrail({
  stages,
}: {
  stages: { stage: string; detail: string }[];
}) {
  if (stages.length === 0) return null;

  return (
    <ol className="relative flex flex-col gap-2.5 pl-4">
      <span
        aria-hidden="true"
        className="absolute left-[3px] top-1.5 bottom-1.5 w-px"
        style={{
          background:
            "linear-gradient(to bottom, color-mix(in oklab, var(--e1) 55%, transparent), transparent)",
        }}
      />
      <AnimatePresence initial={false}>
        {stages.map((s, index) => {
          const isLast = index === stages.length - 1;
          return (
            <motion.li
              key={`${s.stage}-${index}`}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="relative"
            >
              <span
                aria-hidden="true"
                className="absolute -left-4 top-[5px] size-[6px] rounded-full"
                style={{
                  background: "var(--e1)",
                  boxShadow: isLast
                    ? "0 0 8px color-mix(in oklab, var(--e1) 70%, transparent)"
                    : undefined,
                }}
              />
              <p className="ml-eyebrow mb-0.5" style={{ color: "var(--ml-faint)" }}>
                {STAGE_LABELS[s.stage] ?? s.stage}
              </p>
              <p
                className="text-[12.5px] leading-[1.5]"
                style={{ color: "var(--ml-muted)" }}
              >
                {s.detail}
                {isLast && (
                  <span
                    className="ml-1.5 inline-block size-[5px] animate-pulse rounded-full align-middle"
                    style={{ background: "var(--e1)" }}
                    aria-hidden="true"
                  />
                )}
              </p>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
