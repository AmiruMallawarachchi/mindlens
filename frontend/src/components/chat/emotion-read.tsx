"use client";

/**
 * The emotion read strip — design.md §4.1, sits under each user message.
 *
 * §8 is binding here: this is informational, never a diagnosis label, and the
 * score never appears without the plain-language name beside it. The blend
 * chip is dashed and only rendered when a blend was genuinely detected.
 */

import { AnimatePresence, motion } from "motion/react";
import { Petal, Spark } from "@/components/companion/family";
import type { EmotionReading } from "@/lib/emotion";
import { cn } from "@/lib/utils";

export function EmotionRead({
  reading,
  className,
}: {
  reading: EmotionReading;
  className?: string;
}) {
  if (reading.resting) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 0.61, 0.36, 1] }}
      className={cn("flex flex-wrap items-center justify-end gap-1.5", className)}
    >
      {/* Primary chip: petal + name + confidence, in that order. */}
      <span
        className="inline-flex items-center gap-1.5 rounded-[var(--r-pill)] border px-2.5 py-1"
        style={{
          borderColor: "color-mix(in oklab, var(--e1) 42%, transparent)",
          background: "color-mix(in oklab, var(--e1) 12%, transparent)",
        }}
      >
        <Petal mood={reading.state.id} size={13} />
        <span
          className="font-[family-name:var(--font-instrument-sans)] text-[11.5px] font-medium"
          style={{ color: "var(--ml-ink)" }}
        >
          {reading.state.name}
        </span>
        {reading.confidence !== null && (
          <span
            className="ml-num text-[10px]"
            style={{ color: "var(--ml-faint)" }}
            title="How confident the emotion model is in this read"
          >
            {reading.confidence.toFixed(2)}
          </span>
        )}
      </span>

      {reading.subs.map((sub) => (
        <span
          key={sub}
          className="rounded-[var(--r-pill)] border px-2 py-[3px] text-[10.5px]"
          style={{
            borderColor: "var(--ml-hairline)",
            color: "var(--ml-muted)",
          }}
        >
          {sub}
        </span>
      ))}

      {/* A blend gets a dashed chip and a second Spark (§2). */}
      <AnimatePresence>
        {reading.blend && (
          <motion.span
            key={reading.blend.name}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 240, damping: 18 }}
            className="inline-flex items-center gap-1 rounded-[var(--r-pill)] border border-dashed px-2 py-[3px] text-[10.5px]"
            style={{
              borderColor: "color-mix(in oklab, var(--e-blend) 60%, transparent)",
              color: "var(--e-blend)",
            }}
          >
            <Spark size={13} />
            {reading.blend.name}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
