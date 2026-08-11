"use client";

/**
 * Scroll reveal — the mockup (Mindlens Home.dc.html) uses GSAP+ScrollTrigger
 * for its "fade up once, on entering view" sections. motion/react is already
 * a dependency for the whole app (the companion, cards), so this reproduces the
 * same one-time reveal with `whileInView` instead of adding a second
 * animation library for one page.
 */

import { motion } from "motion/react";

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
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ y: 30, opacity: 0, filter: "blur(6px)" }}
      whileInView={{ y: 0, opacity: 1, filter: "blur(0px)" }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
