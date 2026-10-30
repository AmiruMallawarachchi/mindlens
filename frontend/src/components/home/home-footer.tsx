"use client";

import Link from "next/link";
import { MindlensMark } from "@/components/brand/wordmark";
import { Reveal } from "./reveal";
import { GITHUB_URL, REPO_URL } from "./home-copy";

export function HomeFooter() {
  return (
    <footer
        className="px-6 pb-10 pt-[70px]"
        style={{
          borderTop: "1px solid transparent",
          borderImage: "linear-gradient(90deg, var(--ml-hairline), color-mix(in oklab, var(--e1) 30%, var(--ml-hairline)), var(--ml-hairline)) 1",
        }}
      >
        <div className="mx-auto max-w-[1200px]">
          {/* Single column under sm: — the fixed 420px left track would
            * force a horizontal squeeze on narrow screens otherwise. */}
          <div className="grid grid-cols-1 gap-x-[60px] gap-y-[34px] sm:grid-cols-[minmax(0,420px)_1fr]">
            <Reveal className="max-w-[420px]">
              <div className="mb-3.5 flex items-center gap-2">
                <MindlensMark size={20} />
                <span className="text-[15px] font-semibold tracking-[-.02em]">MindLens</span>
              </div>
              <p className="m-0 text-[12.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                MindLens is support software — not a clinical service, diagnostic tool, or replacement for professional care. If you are in crisis, please reach a human: local emergency services or a crisis line near you.
              </p>
            </Reveal>
            <div className="flex flex-wrap gap-11 text-[13px] sm:justify-end">
              <Reveal delay={0.08} className="flex flex-col gap-2.5">
                <span className="font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                  Product
                </span>
                <FooterLink href="/app">Open the app</FooterLink>
                <FooterLink href="#emotions">Emotion system</FooterLink>
              </Reveal>
              <Reveal delay={0.14} className="flex flex-col gap-2.5">
                <span className="font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                  Open source
                </span>
                <FooterLink href={GITHUB_URL} external>GitHub</FooterLink>
              <FooterLink href={REPO_URL} external>GitHub</FooterLink>
                <FooterLink href="#docs">Documentation</FooterLink>
              </Reveal>
            </div>
          </div>
          <div
            className="mt-[54px] pt-5"
            style={{ borderTop: "1px solid var(--ml-hairline)" }}
          >
            <p className="m-0 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
              A final-year project by Amiru Mallawarachchi · Cardiff Metropolitan University · 2026
            </p>
          </div>
        </div>
      </footer>
  );
}

/** Every footer link previously had zero hover treatment — a link that
 * doesn't visibly respond to hover reads as inert. The colour shift + small
 * shift toward the cursor is feedback, the smallest of the four motion
 * categories Section 5 asks every animation to be motivated by. */
function FooterLink({
  href,
  external,
  children,
}: {
  href: string;
  external?: boolean;
  children: React.ReactNode;
}) {
  const className = "inline-flex w-fit items-center transition-[color,transform] duration-200 hover:translate-x-[3px]";
  const style = { color: "var(--ml-muted)" } as React.CSSProperties;
  const hoverProps = {
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => (e.currentTarget.style.color = "var(--ml-ink)"),
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => (e.currentTarget.style.color = "var(--ml-muted)"),
  };
  // Only the real route change (/app) goes through next/link — the original
  // markup used plain anchors for the two same-page hashes and the two
  // external links, and that distinction stays: a hash href through next/link
  // is same-page navigation Next has to reconcile, where a plain anchor is
  // just the browser doing what anchors already do.
  if (external || href.startsWith("#")) {
    return (
      <a
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
        className={className}
        style={style}
        {...hoverProps}
      >
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={className} style={style} {...hoverProps}>
      {children}
    </Link>
  );
}

