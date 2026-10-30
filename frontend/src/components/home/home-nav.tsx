"use client";

import Link from "next/link";
import { motion, type MotionValue, useTransform } from "motion/react";
import { MindlensMark } from "@/components/brand/wordmark";
import { Magnetic } from "./magnetic";
import { NAV_LINKS } from "./home-copy";
import { SunIcon, MoonIcon } from "./home-icons";

export function HomeNav({navShadow, isDay, toggleGrade}: { navShadow: MotionValue<number>; isDay: boolean; toggleGrade: () => void }) {
  return (
    <motion.nav
        className="fixed left-1/2 top-4 z-[60] flex w-max max-w-[calc(100vw-32px)] -translate-x-1/2 items-center gap-6 whitespace-nowrap rounded-[99px] py-2.5 pl-[18px] pr-3"
        style={{
          background: "var(--ml-panel)",
          backdropFilter: "blur(20px) saturate(1.2)",
          border: "1px solid var(--ml-hairline)",
          boxShadow: useTransform(
            navShadow,
            [0, 1],
            ["0 12px 40px -18px rgba(36,26,14,.25)", "0 16px 50px -12px rgba(36,26,14,.45)"],
          ),
        }}
      >
        <a href="#top" className="flex items-center gap-2">
          <MindlensMark size={22} />
          <span className="text-[15px] font-semibold tracking-[-.02em]">MindLens</span>
        </a>
        <div className="hidden gap-4.5 text-[12.5px] sm:flex" style={{ color: "var(--ml-muted)" }}>
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} style={{ color: "var(--ml-muted)" }}>
              {link.label}
            </a>
          ))}
        </div>
        <button
          type="button"
          onClick={toggleGrade}
          aria-label="Toggle day and night"
          title="Day / night"
          className="grid size-[34px] shrink-0 place-items-center rounded-full transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_6%,transparent)]"
          style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {isDay ? <SunIcon /> : <MoonIcon />}
        </button>
        <Link
          href="/app"
          className="hidden text-[12.5px] font-medium no-underline sm:inline"
          style={{ color: "var(--ml-muted)" }}
        >
          Log in
        </Link>
        <Magnetic strength={0.25}>
          <Link
            href="/app?auth=register"
            className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-[99px] px-4 py-[9px] text-[12.5px] font-medium no-underline"
            style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
          >
            Sign up <span className="text-[14px] leading-none">→</span>
          </Link>
        </Magnetic>
      </motion.nav>

  );
}
