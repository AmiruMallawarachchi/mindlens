"use client";

/**
 * Scroll reveal — the mockup (Mindlens Home.dc.html) uses GSAP+ScrollTrigger
 * for its "fade up once, on entering view" sections. motion/react is already
 * a dependency for the whole app (the companion, cards), so this reproduces the
 * same one-time reveal with `whileInView` instead of adding a second
 * animation library for one page.
 *
 * Reduced-motion: `whileInView` doesn't disable itself under
 * prefers-reduced-motion on its own — every other animated surface on this
 * page checks useReducedMotion() explicitly, this one hadn't been, which
 * left every Reveal-wrapped section (nearly the whole page) sliding and
 * blurring in regardless of the setting. Content still appears at the same
 * scroll position either way; only the motion is removed.
 */

import { motion, useReducedMotion } from "motion/react";

export function Reveal({
  children,
  className,
  style,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  delay?: number;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={reduceMotion ? false : { y: 30, opacity: 0, filter: "blur(6px)" }}
      whileInView={reduceMotion ? undefined : { y: 0, opacity: 1, filter: "blur(0px)" }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
