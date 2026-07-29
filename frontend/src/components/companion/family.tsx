"use client";

/**
 * The companion family members the chat screen uses. design.md §3.
 *
 * Spark, Anchor and Petal share Nimbus's construction language — soft radial
 * fills, one coloured shadow, no strokes except where the design calls for
 * one. The rest of the family (Ember, Fern, Loom, Orbit, Tide, Echo) belongs
 * to screens that aren't built yet.
 */

import { useId } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { EmotionId } from "@/lib/emotion";
import { cn } from "@/lib/utils";

/**
 * Spark — the blend. Arrives with a spring pop next to Nimbus when two
 * feelings are read at once, orbits slowly, and merges away when the blend
 * fades. It is only ever mounted when a blend genuinely exists.
 */
export function Spark({
  size = 22,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const reduceMotion = useReducedMotion();

  return (
    <motion.svg
      viewBox="0 0 40 40"
      width={size}
      height={size}
      role="img"
      aria-label="Spark, a second feeling alongside the first"
      className={cn("overflow-visible", className)}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 14 }}
    >
      <defs>
        <radialGradient id={`${uid}-spark`} cx="34%" cy="26%" r="80%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="var(--e-blend)" />
          <stop offset="100%" stopColor="var(--e-blend)" stopOpacity="0.55" />
        </radialGradient>
      </defs>
      <motion.g
        animate={
          reduceMotion ? undefined : { rotate: 360 }
        }
        transition={{ duration: 14, repeat: Infinity, ease: "linear" }}
        style={{ transformOrigin: "20px 20px" }}
      >
        <motion.circle
          cx="20"
          cy="12"
          r="7"
          fill={`url(#${uid}-spark)`}
          animate={reduceMotion ? undefined : { r: [7, 8.2, 7] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
          style={{
            filter: "drop-shadow(0 0 10px var(--e-blend))",
          }}
        />
      </motion.g>
    </motion.svg>
  );
}

/**
 * Anchor — crisis only. §3 and §6: deliberately still and colourless. It
 * takes no emotion custom properties and has no animation of any kind, so a
 * crisis view cannot inherit motion from anywhere.
 */
export function Anchor({
  size = 150,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 150 112"
      width={size}
      height={(size * 112) / 150}
      role="img"
      aria-label="Anchor, steady and still"
      className={cn("shrink-0", className)}
    >
      <defs>
        <linearGradient id="anchor-stone" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#9aa0ab" />
          <stop offset="100%" stopColor="#5f6672" />
        </linearGradient>
      </defs>
      <path
        d="M40 92 C28 74 34 50 54 40 C66 34 84 34 97 41 C116 51 122 74 110 92 Z"
        fill="url(#anchor-stone)"
      />
      <ellipse cx="75" cy="94" rx="42" ry="6" fill="#3b3f47" opacity="0.5" />
      <ellipse cx="62" cy="60" rx="3.2" ry="4.2" fill="#2b2f36" />
      <ellipse cx="90" cy="60" rx="3.2" ry="4.2" fill="#2b2f36" />
      <path
        d="M66 74 Q76 78 86 74"
        fill="none"
        stroke="#2b2f36"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  );
}

/** §3 — Petal is open at hopeful and folded at anxious or ashamed. */
const FOLDED: ReadonlySet<EmotionId> = new Set(["anxious", "ashamed", "grief", "flat"]);
const OPEN: ReadonlySet<EmotionId> = new Set(["hopeful", "joyful", "tender", "calm"]);

/**
 * Petal — the emotion-read chip icon. Four petals whose spread tracks how
 * open the feeling is.
 */
export function Petal({
  mood = "balanced",
  size = 13,
  className,
}: {
  mood?: EmotionId;
  size?: number;
  className?: string;
}) {
  const spread = FOLDED.has(mood) ? 3.2 : OPEN.has(mood) ? 6.4 : 5;
  const petalLength = FOLDED.has(mood) ? 5.4 : 7.2;

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden="true"
      className={cn("shrink-0", className)}
    >
      {[0, 90, 180, 270].map((angle) => (
        <motion.ellipse
          key={angle}
          cx="12"
          cy={12 - spread}
          rx="3.1"
          ry={petalLength}
          fill="var(--e1)"
          opacity="0.9"
          transform={`rotate(${angle} 12 12)`}
          initial={false}
          animate={{ cy: 12 - spread, ry: petalLength }}
          transition={{ type: "spring", stiffness: 140, damping: 16 }}
        />
      ))}
      <circle cx="12" cy="12" r="2.1" fill="var(--e2)" />
    </svg>
  );
}
