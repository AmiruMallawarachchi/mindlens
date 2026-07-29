"use client";

/**
 * The Mindlens wordmark — "the living dot". design.md §1.1.
 *
 * The dot of the `i` is removed from the glyph (dotless ı) and replaced by a
 * positioned orb: it breathes, recolours with the active emotion, and blinks
 * — a brief scaleY squash — whenever the emotion read updates.
 *
 * §1.1 also forbids the orb appearing more than once per lockup, so the mark
 * and the wordmark are the same component at different sizes rather than two
 * things that might both end up on screen.
 */

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { EmotionId } from "@/lib/emotion";
import { cn } from "@/lib/utils";

export function Wordmark({
  mood,
  size = 21,
  className,
}: {
  /** Passing the current emotion is what makes the orb blink on change. */
  mood?: EmotionId;
  size?: number;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  const [blinking, setBlinking] = useState(false);
  const previousMood = useRef(mood);

  useEffect(() => {
    if (previousMood.current === mood) return;
    previousMood.current = mood;
    if (reduceMotion) return;
    setBlinking(true);
    const timer = setTimeout(() => setBlinking(false), 180);
    return () => clearTimeout(timer);
  }, [mood, reduceMotion]);

  const orbSize = size * 0.26;

  return (
    <span
      className={cn("inline-flex items-baseline select-none", className)}
      style={{ fontSize: size }}
    >
      <span
        className="ml-display leading-none"
        style={{ letterSpacing: "-0.02em", color: "var(--ml-ink)" }}
      >
        {/* Dotless ı, with the orb anchored to that glyph rather than to the
         * wordmark — the `m` before it changes width with the font size, so a
         * fixed offset from the left edge drifts off the stem. */}
        m
        <span className="relative inline-block">
          ı
          <motion.span
            aria-hidden="true"
            className="absolute rounded-full"
            style={{
              width: orbSize,
              height: orbSize,
              left: "50%",
              marginLeft: -orbSize / 2,
              top: -orbSize * 1.05,
              background:
                "radial-gradient(circle at 34% 26%, #fff, var(--e1) 60%)",
              boxShadow: "0 0 18px var(--e1)",
            }}
            animate={
              blinking
                ? { scaleY: 0.2, scaleX: 1.1 }
                : reduceMotion
                  ? { scale: 1.1 }
                  : { scale: [1, 1.22, 1] }
            }
            transition={
              blinking
                ? { duration: 0.16, ease: "easeOut" }
                : reduceMotion
                  ? { duration: 0 }
                  : { duration: 4, repeat: Infinity, ease: "easeInOut" }
            }
          />
        </span>
        ndlens
      </span>
      <span className="sr-only">Mindlens</span>
    </span>
  );
}

/**
 * The mark alone — orb plus a short stem. §1.1: this is the favicon shape,
 * and at ≤16px it is just the orb.
 */
export function MindlensMark({ size = 28 }: { size?: number }) {
  const reduceMotion = useReducedMotion();
  const orbSize = size * 0.46;

  return (
    <span
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {size > 16 && (
        <span
          className="absolute rounded-full"
          style={{
            width: Math.max(1.5, size * 0.06),
            height: size * 0.34,
            bottom: 0,
            background: "var(--ml-ink)",
            opacity: 0.85,
          }}
        />
      )}
      <motion.span
        className="absolute rounded-full"
        style={{
          width: orbSize,
          height: orbSize,
          top: size * 0.06,
          background: "radial-gradient(circle at 34% 26%, #fff, var(--e1) 60%)",
          boxShadow: "0 0 18px var(--e1)",
        }}
        animate={reduceMotion ? { scale: 1.1 } : { scale: [1, 1.22, 1] }}
        transition={
          reduceMotion
            ? { duration: 0 }
            : { duration: 4, repeat: Infinity, ease: "easeInOut" }
        }
      />
    </span>
  );
}
