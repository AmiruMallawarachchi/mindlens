"use client";

/**
 * Home — the marketing/landing page. Ported from the approved mockup
 * (design project "Mindlens UI Mockups" → Mindlens Home.dc.html): warm
 * paper editorial, animated blob field, a philosophy quote, a 5-step "what
 * happens when you press send" band, a dark Models band, an interactive
 * Emotion lab, a Docs band, and Safety rules.
 *
 * The mockup's GSAP+ScrollTrigger reveals are reimplemented with
 * motion/react's `whileInView` (see ./reveal.tsx) — same one-time fade-up
 * effect, no second animation library. Copy, structure and the real
 * hf.co/AmiruMallawarachchi and github.com/AmiruMallawarachchi links are
 * carried over verbatim.
 */

import { useEffect } from "react";
import { motion, useMotionValue, useScroll, useSpring, useTransform } from "motion/react";
import { useGrade } from "@/lib/use-grade";
import { useHomeEmotion } from "./use-home-emotion";
import { HomeNav } from "./home-nav";
import { HomeHero } from "./home-hero";
import { HomePortraitBand } from "./home-portrait";
import { HomePhilosophy } from "./home-philosophy";
import { HomeHowItWorks } from "./home-how";
import { HomeAgents } from "./home-agents";
import { HomeEmotionLab } from "./home-emotion";
import { HomeDocs } from "./home-docs";
import { HomeSafety } from "./home-safety";
import { HomeFooter } from "./home-footer";

export function HomePage() {
  const { isDay, toggleGrade } = useGrade();
  const { activeId, setActiveId, reduceMotion, activeName, activeSubs, rootStyle } = useHomeEmotion();

  const { scrollY } = useScroll();
  const navShadow = useTransform(scrollY, [0, 80], [0, 1]);

  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const blobAX = useSpring(useTransform(mx, [-1, 1], [-18, 18]), { stiffness: 60, damping: 20 });
  const blobAY = useSpring(useTransform(my, [-1, 1], [-18, 18]), { stiffness: 60, damping: 20 });
  const blobBX = useSpring(useTransform(mx, [-1, 1], [14, -14]), { stiffness: 60, damping: 20 });
  const blobBY = useSpring(useTransform(my, [-1, 1], [14, -14]), { stiffness: 60, damping: 20 });

  useEffect(() => {
    if (reduceMotion) return;
    const onMove = (e: MouseEvent) => {
      mx.set((e.clientX / window.innerWidth) * 2 - 1);
      my.set((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [reduceMotion, mx, my]);


  return (
    <div
      className="ml-root ml-grain relative min-h-screen w-full overflow-x-hidden"
      style={{ ...(rootStyle as React.CSSProperties), color: "var(--ml-ink)", background: "var(--ml-canvas)" }}
    >
      {!reduceMotion && (
        <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
          <motion.span
            className="absolute left-[8%] top-[12%] aspect-square w-[44vw] rounded-full"
            style={{
              background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 55%, transparent), transparent 70%)",
              filter: "blur(70px)",
              animation: "mlBlobA 16s ease-in-out infinite",
              x: blobAX,
              y: blobAY,
            }}
          />
          <motion.span
            className="absolute right-[4%] top-[30%] aspect-square w-[38vw] rounded-full"
            style={{
              background: "radial-gradient(circle, color-mix(in oklab, var(--e2) 55%, transparent), transparent 70%)",
              filter: "blur(80px)",
              animation: "mlBlobB 20s ease-in-out infinite",
              x: blobBX,
              y: blobBY,
            }}
          />
        </div>
      )}

      <HomeNav navShadow={navShadow} isDay={isDay} toggleGrade={toggleGrade} />
      <HomeHero reduceMotion={reduceMotion} />
      <HomePortraitBand reduceMotion={reduceMotion} activeId={activeId} />
      <HomePhilosophy />
      <HomeHowItWorks />
      <HomeAgents />
      <HomeEmotionLab activeId={activeId} setActiveId={setActiveId} activeName={activeName} activeSubs={activeSubs} />
      <HomeDocs />
      <HomeSafety />
      <HomeFooter />

    </div>
  );
}
