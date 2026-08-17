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

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { MindlensMark } from "@/components/brand/wordmark";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { COMPANIONS } from "@/lib/companions";
import { useGrade } from "@/lib/use-grade";
import {
  EMOTION_ORDER,
  EMOTION_STATES,
  emotionCssVars,
  type EmotionId,
} from "@/lib/emotion";
import { Reveal } from "./reveal";
import { Magnetic } from "./magnetic";

/** The hero's resting state before anyone taps a swatch — the marketing
 * site's own amber accent (design.md §1.3), not any live emotion read. */
const WARM = {
  name: "Warm spectrum",
  c1: "#ff7a4d",
  c2: "#ffb45c",
  c3: "#2b1410",
  subs: ["settled", "open", "present"] as const,
};

const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#models", label: "Models" },
  { href: "#emotions", label: "Emotions" },
  { href: "#docs", label: "Docs" },
  { href: "#safety", label: "Safety" },
];

const STEPS = [
  {
    num: "01",
    title: "The gate",
    body: "A hardwired safety gate reads every message before anything else. It cannot be bypassed — and in a crisis, Mindlens answers from vetted templates only. No model improvises.",
  },
  {
    num: "02",
    title: "The read",
    body: "Five small models read the feeling: what's on the surface, what's underneath, how heavy it sits. You always see the read — a weather report, never a diagnosis.",
  },
  {
    num: "03",
    title: "The recall",
    body: "Mindlens remembers what you've shared — people, deadlines, wins — and brings back only what this moment actually needs.",
  },
  {
    num: "04",
    title: "The response",
    // Not "always ending in a choice": empathy_agent deliberately drops the
    // options above 0.8 distress ("No advice. No choices."), which is the
    // right behaviour and the opposite of what the old copy promised.
    body: "A team of agents drafts a reply in the voice of a wise coaching friend: practical, warm, and usually ending in a choice — music, breathing, journaling, or just talking. When distress runs high it drops the options and just stays with you.",
  },
  {
    num: "05",
    title: "The record",
    body: "Moods and progress are logged so next week's Mindlens knows what this week's you worked through — and the people and topics it picks up land in Memory, where you can change them.",
  },
];

/** `id` is the real Hugging Face repo each card runs on, not a label.
 * `adopted` marks a public checkpoint someone else trained: the emotion
 * classifier is SamLowe's go_emotions model, and presenting it under the
 * hf.co/AmiruMallawarachchi banner alongside the four fine-tuned here would
 * claim authorship the code doesn't have. Keep these ids in step with
 * `backend/app/config.py`'s *_MODEL_ID settings — if the model swaps, the
 * card is what tells people which one is actually running. */
const MODELS = [
  { id: "SamLowe/roberta-base-go_emotions", adopted: true, title: "Emotion classifier", body: "28 emotion classes (GoEmotions), folded into the 12 named states that light the interface." },
  { id: "AmiruMallawarachchi/mindlens-mh-classifier", adopted: false, title: "Mental-health signal", body: "Screens every message for anxiety, depression and stress signals — quietly, in context, and never shown back to you as a label." },
  { id: "AmiruMallawarachchi/mindlens-crisis", adopted: false, title: "Crisis detector", body: "Second-layer screening, behind a hardwired keyword gate that runs first on every turn. Either one alone can stop the conversation and switch to templates." },
  { id: "AmiruMallawarachchi/mindlens-rag-reranker", adopted: false, title: "RAG reranker", body: "Re-orders passages retrieved from a curated therapy corpus so the most relevant guidance wins." },
  { id: "AmiruMallawarachchi/mindlens-distortion-classifier", adopted: false, title: "Distortion classifier", body: "Looks for thinking traps — catastrophizing, all-or-nothing, mind-reading. The weakest of the five; see its model card for how far to trust it." },
];

// href is the actual doc on GitHub, not the profile — each card ends in
// "Open →", a promise to open *that* file, so the link has to go there.
const DOCS = [
  { file: "SYSTEM.md", title: "The single source of truth", body: "Architecture, the five models, agent behavior, safety rules — everything that is non-negotiable, in one file." },
  { file: "API.md", title: "HTTP & WebSocket contract", body: "Every endpoint, the streaming chat protocol, and how agent activity reaches the client in real time." },
  { file: "DEPLOYMENT.md", title: "Hugging Face Space & Vercel runbook", body: "How the backend, the vector store rebuilt fresh on every boot, and the web client ship — and how production fails closed." },
];
const REPO_URL = "https://github.com/AmiruMallawarachchi/mindlens";

/** Rules 03, 04 and 05 each overstated something and have been narrowed to
 * what the code actually guarantees: the access token is in browser storage
 * (only the refresh token is an httpOnly cookie), the conversation
 * transcript is kept even though it isn't listed on the Memory page, and
 * the confidence figure is the classifier's real score rather than a
 * constant — it was hardcoded until the orchestrator started assigning it. */
const RULES = [
  { num: "01", title: "Crisis answers are template-only", body: "Zero LLM calls when it matters most. Every crisis response is written and vetted by humans." },
  { num: "02", title: "The safety gate runs first, every turn", body: "No agent, prompt or feature can skip it. Safety overrides convenience — by design." },
  { num: "03", title: "Your words stay yours", body: "Every database query scoped to you, rate limits everywhere, and never sold or used for advertising. Replies are written by Groq — this turn's message goes to them with emails, phone numbers and ID numbers stripped, though your name and anyone you've mentioned go with it, because that's what makes a reply sound like it knows you." },
  { num: "04", title: "Memory is visible", body: "Your conversations are saved so next week picks up where this one left off. Anything Mindlens learns from them shows up in Memory first, where you can edit or delete it." },
  { num: "05", title: "Never a diagnosis", body: "Mindlens names feelings in plain language and shows how sure it is. It never labels you." },
];

const GITHUB_URL = "https://github.com/AmiruMallawarachchi";
const HF_URL = "https://huggingface.co/AmiruMallawarachchi";

export function HomePage() {
  const { isDay, toggleGrade } = useGrade();
  const [activeId, setActiveId] = useState<EmotionId | null>(null);
  const reduceMotion = useReducedMotion();

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

  // The hero blobs, the portrait band and the whole page's --e1/--e2/--e3
  // palette all derive from `activeId` (rootStyle below), so cycling it here
  // is what makes the entire page's colour genuinely alive on a page nobody
  // has touched yet — the same "emotion drives colour" mechanic the app
  // itself uses, just running on a timer instead of waiting for a message.
  // Skipped under reduced motion, same as every other ambient loop on this
  // page; a manual swatch click still shows immediately, the cycle just
  // continues from there on the next tick rather than stopping.
  useEffect(() => {
    if (reduceMotion) return;
    const id = window.setInterval(() => {
      setActiveId((current) => {
        const idx = current ? EMOTION_ORDER.indexOf(current) : -1;
        return EMOTION_ORDER[(idx + 1) % EMOTION_ORDER.length];
      });
    }, 5000);
    return () => window.clearInterval(id);
  }, [reduceMotion]);

  const active = activeId ? EMOTION_STATES[activeId] : null;
  const activeName = active?.name ?? WARM.name;
  const activeSubs = active?.subs ?? WARM.subs;

  const rootStyle = useMemo(() => {
    if (active) {
      return emotionCssVars({
        state: active,
        blend: null,
        coreState: null,
        intensity: 1,
        confidence: null,
        subs: active.subs,
        resting: false,
      });
    }
    return { "--e1": WARM.c1, "--e2": WARM.c2, "--e3": WARM.c3, "--e-blend": WARM.c2, "--intensity": "1" };
  }, [active]);

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

      {/* --- Nav --------------------------------------------------------- */}
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
          <span className="text-[15px] font-semibold tracking-[-.02em]">Mindlens</span>
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

      {/* --- Hero ---------------------------------------------------------- */}
      <header
        id="top"
        className="relative flex min-h-[100dvh] flex-col items-center justify-center overflow-hidden px-6 pb-[60px] pt-[120px]"
      >
        <div
          className="mb-auto flex w-full max-w-[1200px] justify-between font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]"
          style={{ color: "var(--ml-faint)" }}
        >
          <span>{"/// Mindlens"}</span>
          <span>Personal wellbeing companion</span>
        </div>

        <Reveal className="relative my-auto max-w-[1100px] text-center">
          <h1
            className="m-0 font-semibold leading-[.98] tracking-[-.045em]"
            style={{ fontSize: "clamp(58px, 9.5vw, 148px)", textWrap: "balance" }}
          >
            See what
            <span
              aria-hidden="true"
              className="mx-[.06em] inline-block h-[.55em] w-[.55em] align-baseline"
              style={{
                borderRadius: "38% 62% 55% 45% / 45% 40% 60% 55%",
                background: "linear-gradient(140deg, var(--e2), var(--e1))",
                boxShadow: "0 18px 44px -12px var(--e1)",
              }}
            />
            you feel.
          </h1>
          <p
            className="mx-auto mt-7 max-w-[560px] text-[17px] leading-[1.65]"
            style={{ color: "var(--ml-muted)", textWrap: "pretty" }}
          >
            A wise friend that reads the feeling underneath your words, remembers what matters, and helps you build the tools to steady yourself — over and over, for life.
          </p>
          <div className="mt-[34px] flex flex-wrap justify-center gap-3">
            <Magnetic>
              <Link
                href="/app"
                className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
                style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)", boxShadow: "0 18px 40px -16px var(--e1)" }}
              >
                Start a conversation
              </Link>
            </Magnetic>
            <Magnetic>
              <a
                href="#how"
                className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
                style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", backdropFilter: "blur(12px)" }}
              >
                Read how it works
              </a>
            </Magnetic>
          </div>
          <p className="mt-[22px] font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
            Free · Yours alone, not encrypted end-to-end · Not a replacement for professional care
          </p>
        </Reveal>

        <div
          className="relative mt-auto w-full max-w-[1200px] overflow-hidden"
          style={{ maskImage: "linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)", WebkitMaskImage: "linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)" }}
        >
          <div
            className="flex w-max gap-[34px] py-2"
            style={{ animation: reduceMotion ? undefined : "mlMarquee 36s linear infinite" }}
          >
            {[...EMOTION_ORDER, ...EMOTION_ORDER].map((id, i) => {
              const state = EMOTION_STATES[id];
              return (
                <span
                  key={`${id}-${i}`}
                  className="inline-flex items-center gap-2.5 whitespace-nowrap font-[family-name:var(--font-geist-mono)] text-[11px] uppercase tracking-[.12em]"
                  style={{ color: "var(--ml-muted)" }}
                >
                  <span
                    className="size-[9px] rounded-full"
                    style={{ background: `linear-gradient(140deg, ${state.c1}, ${state.c2})` }}
                  />
                  {state.name}
                </span>
              );
            })}
          </div>
        </div>
      </header>

      {/* --- Portrait band ------------------------------------------------- */}
      {/* board 7a's mockup slot here is a photo ("calm portrait / warm
       * still"). There's no real photography to drop in and no image-gen
       * tool wired into this build, and a stock photo of a stranger is the
       * wrong call for a wellbeing app's hero without the user choosing one
       * — so instead of a flat gradient standing in for a photo that isn't
       * there, this is genuine motion: the same token-driven blob technique
       * (mlBlobA/mlBlobB, tokens.css) already driving the hero background
       * above, plus one of the real companions from the app itself, cycling
       * with the palette above it. Real generative art and a real character,
       * not a fake screenshot. Swap for `next/image` the day real
       * photography exists. */}
      <section className="px-6">
        <Reveal
          className="ml-grain relative mx-auto h-[min(72vh,560px)] max-w-[1200px] overflow-hidden rounded-[30px]"
          delay={0.1}
        >
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 30%, var(--ml-canvas)), color-mix(in oklab, var(--e2) 24%, var(--ml-canvas)))",
              boxShadow: "0 34px 80px -30px color-mix(in oklab, var(--e1) 60%, rgba(36,26,14,.4))",
            }}
          />
          {!reduceMotion && (
            <>
              <span
                aria-hidden="true"
                className="absolute left-[6%] top-[10%] aspect-square w-[52%] rounded-full"
                style={{
                  background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 65%, transparent), transparent 70%)",
                  filter: "blur(60px)",
                  animation: "mlBlobA 18s ease-in-out infinite",
                }}
              />
              <span
                aria-hidden="true"
                className="absolute right-[2%] bottom-[6%] aspect-square w-[48%] rounded-full"
                style={{
                  background: "radial-gradient(circle, color-mix(in oklab, var(--e2) 60%, transparent), transparent 70%)",
                  filter: "blur(70px)",
                  animation: "mlBlobB 24s ease-in-out infinite",
                }}
              />
            </>
          )}
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(120% 90% at 50% 100%, transparent 40%, color-mix(in oklab, var(--ml-deep) 55%, transparent) 100%)",
            }}
          />
          <div className="absolute inset-0 grid place-items-center">
            <CompanionAvatar
              companionId={COMPANIONS[activeId ? EMOTION_ORDER.indexOf(activeId) % COMPANIONS.length : 0].id}
              activity="idle"
              size={200}
              withShadow
            />
          </div>
          <div
            className="absolute left-7 bottom-6 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]"
            style={{ color: "#fffdf8", textShadow: "0 1px 12px rgba(0,0,0,.35)" }}
          >
            The room is listening
          </div>
        </Reveal>
      </section>

      {/* --- Philosophy ------------------------------------------------- */}
      <section className="px-6 py-[140px]">
        <Reveal className="mx-auto max-w-[900px] text-center">
          <p className="m-0 mb-[26px] font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
            The idea Mindlens is built on
          </p>
          <p
            className="ml-display m-0"
            style={{ fontSize: "clamp(30px, 4.4vw, 52px)", lineHeight: 1.22, letterSpacing: "-.015em", fontStyle: "italic", textWrap: "balance" }}
          >
            &ldquo;Therapy did not fix me. Therapy gave me the tools to fix myself — <span style={{ color: "var(--e1)" }}>over and over again</span>, for the rest of my life.&rdquo;
          </p>
          <p className="mx-auto mt-[30px] max-w-[520px] text-[15.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
            Mindlens exists to help you build those tools: understand what you&rsquo;re feeling, regulate it, and notice yourself getting better at it.
          </p>
        </Reveal>
      </section>

      {/* --- How it works ------------------------------------------------ */}
      <section id="how" className="px-6 py-[60px] pb-[130px]">
        <div className="mx-auto max-w-[1200px]">
          <Reveal className="mb-14 flex flex-wrap items-end justify-between gap-4.5">
            <h2 className="m-0 max-w-[560px] font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
              What happens when you press send
            </h2>
            <p className="m-0 max-w-[360px] text-[14.5px] leading-[1.65]" style={{ color: "var(--ml-muted)" }}>
              Every message moves through the same careful pipeline — safety first, always, with no way around it.
            </p>
          </Reveal>
          <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
            {STEPS.map((step, i) => (
              <Reveal key={step.num} delay={i * 0.05}>
                <article
                  className="flex h-full min-h-[230px] flex-col gap-3.5 rounded-[22px] p-[22px]"
                  style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
                >
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11px]" style={{ color: "var(--e1)" }}>
                    {step.num}
                  </span>
                  <h3 className="ml-display m-0 text-[22px] font-normal tracking-[-.01em]">{step.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.65]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {step.body}
                  </p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* --- Models (dark band) ------------------------------------------ */}
      <section
        id="models"
        className="relative overflow-hidden px-6 py-[110px]"
        style={{ background: "var(--ml-deep)", color: "#f7f3ec", borderRadius: "44px 44px 0 0" }}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-[10%] -top-[30%] aspect-square w-[60vw] rounded-full"
          style={{ background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 26%, transparent), transparent 70%)", filter: "blur(90px)" }}
        />
        <div className="relative mx-auto max-w-[1200px]">
          <Reveal className="mb-[54px] flex flex-wrap items-end justify-between gap-4.5">
            <div>
              <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(247,243,236,.45)" }}>
                {"/// The read"}
              </p>
              <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
                Five small models,
                <br />
                one careful read
              </h2>
              {/* Four were fine-tuned for Mindlens; the emotion classifier is
                * a public checkpoint. Saying so here is the difference between
                * "five models" and "five models I trained". */}
              <p className="m-0 mt-4 max-w-[420px] text-[13px] leading-[1.65]" style={{ color: "rgba(247,243,236,.5)" }}>
                Four fine-tuned for Mindlens. One adopted — the emotion
                classifier is a public GoEmotions checkpoint, marked below.
              </p>
            </div>
            <a
              href={HF_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-[99px] px-[18px] py-2.5 font-[family-name:var(--font-geist-mono)] text-[11.5px] no-underline"
              style={{ border: "1px solid rgba(247,243,236,.2)", color: "#f7f3ec" }}
            >
              hf.co/AmiruMallawarachchi ↗
            </a>
          </Reveal>
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
            {MODELS.map((model, i) => (
              <Reveal key={model.id} delay={i * 0.05}>
                <article
                  className="flex h-full min-h-[200px] flex-col gap-3 rounded-[20px] p-5 transition-colors"
                  style={{ border: "1px solid rgba(247,243,236,.12)", background: "rgba(255,252,246,.04)" }}
                >
                  <span className="size-[10px] rounded-full" style={{ background: "linear-gradient(140deg, var(--e2), var(--e1))" }} />
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11.5px] break-all" style={{ color: "var(--e2)" }}>
                    {model.id}
                  </span>
                  {model.adopted && (
                    <span
                      className="w-fit rounded-[99px] px-2 py-0.5 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.1em]"
                      style={{ border: "1px solid rgba(247,243,236,.25)", color: "rgba(247,243,236,.6)" }}
                    >
                      adopted, not ours
                    </span>
                  )}
                  <h3 className="m-0 text-[16.5px] font-semibold tracking-[-.015em]">{model.title}</h3>
                  <p className="m-0 text-[12.5px] leading-[1.6]" style={{ color: "rgba(247,243,236,.55)", textWrap: "pretty" }}>
                    {model.body}
                  </p>
                </article>
              </Reveal>
            ))}
          </div>
          <Reveal delay={0.2}>
            <p className="m-0 mt-9 max-w-[640px] text-[13.5px] leading-[1.7]" style={{ color: "rgba(247,243,236,.55)" }}>
              Generation runs on Groq — Llama 3.1 8B for simple turns, Llama 3.3 70B when the moment is emotional or complex. Crisis turns use <span style={{ color: "var(--e2)" }}>zero</span> LLM calls: vetted templates only.
            </p>
          </Reveal>
        </div>
      </section>

      {/* --- Emotion lab (dark band) -------------------------------------- */}
      <section
        id="emotions"
        className="relative overflow-hidden px-6 py-[130px]"
        style={{ background: "var(--ml-deep)", color: "#f7f3ec", borderRadius: "0 0 44px 44px" }}
      >
        <div className="relative mx-auto max-w-[1200px]">
          <Reveal className="mb-[54px] text-center">
            <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(247,243,236,.45)" }}>
              {"/// One room, twelve weathers"}
            </p>
            <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,64px)" }}>
              The interface is lit
              <br />
              by what you feel
            </h2>
            <p className="mx-auto mt-5 max-w-[520px] text-[14.5px] leading-[1.65]" style={{ color: "rgba(247,243,236,.55)", textWrap: "pretty" }}>
              Tap a state. The field, the shadows and every accent on this page crossfade over 1.6 seconds — nothing ever snaps.
            </p>
          </Reveal>
          <div className="grid items-stretch gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            <Reveal className="grid content-center gap-2.5" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              {EMOTION_ORDER.map((id) => {
                const state = EMOTION_STATES[id];
                const isActive = activeId === id;
                return (
                  <button
                    key={id}
                    type="button"
                    title={state.name}
                    onClick={() => setActiveId(isActive ? null : id)}
                    className="h-[74px] cursor-pointer rounded-2xl transition-transform hover:scale-105"
                    style={{
                      border: isActive ? "2px solid #fffdf8" : "1px solid rgba(247,243,236,.15)",
                      background: `linear-gradient(140deg, ${state.c1}, ${state.c2})`,
                      opacity: isActive || activeId === null ? 1 : 0.72,
                    }}
                  >
                    <span className="sr-only">{state.name}</span>
                  </button>
                );
              })}
            </Reveal>
            <Reveal
              delay={0.1}
              className="relative flex min-h-[420px] flex-col justify-end overflow-hidden rounded-[26px] p-[26px]"
              style={{
                border: "1px solid rgba(247,243,236,.12)",
                background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 60%, var(--ml-deep)), color-mix(in oklab, var(--e3) 80%, var(--ml-deep)))",
                transition: "background 1.6s cubic-bezier(.22,.61,.36,1)",
              }}
            >
              <div className="relative">
                <p className="m-0 mb-1.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "rgba(255,253,248,.6)" }}>
                  Current read
                </p>
                <p className="ml-display m-0 text-[46px] font-light tracking-[-.02em]" style={{ color: "#fffdf8" }}>
                  {activeName}
                </p>
                <div className="mt-3.5 flex flex-wrap gap-2">
                  {activeSubs.map((sub) => (
                    <span
                      key={sub}
                      className="rounded-[99px] px-3 py-[5px] text-[11.5px]"
                      style={{ border: "1px solid rgba(255,253,248,.35)", color: "rgba(255,253,248,.85)" }}
                    >
                      {sub}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* --- Docs ---------------------------------------------------------- */}
      <section id="docs" className="px-6 py-[130px] pb-[110px]">
        <div className="mx-auto max-w-[1200px]">
          <Reveal className="mb-[50px] flex flex-wrap items-end justify-between gap-4.5">
            <div>
              <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                {"/// Built in the open"}
              </p>
              <h2 className="m-0 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,60px)" }}>
                Read the docs
              </h2>
            </div>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-[99px] px-[18px] py-2.5 font-[family-name:var(--font-geist-mono)] text-[11.5px] no-underline"
              style={{ border: "1px solid var(--ml-hairline-strong)" }}
            >
              github.com/AmiruMallawarachchi ↗
            </a>
          </Reveal>
          <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {DOCS.map((doc, i) => (
              <Reveal key={doc.file} delay={i * 0.05}>
                <a
                  href={`${REPO_URL}/blob/main/docs/${doc.file}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-full min-h-[170px] flex-col gap-3 rounded-[22px] p-6 no-underline transition-colors"
                  style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
                >
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11.5px]" style={{ color: "var(--e1)" }}>
                    {doc.file}
                  </span>
                  <h3 className="ml-display m-0 text-[22px] font-normal tracking-[-.01em]">{doc.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.6]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {doc.body}
                  </p>
                  <span className="mt-auto text-[13px] font-medium" style={{ color: "var(--e1)" }}>
                    Open →
                  </span>
                </a>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* --- Safety ---------------------------------------------------- */}
      <section id="safety" className="px-6 pb-[130px] pt-10">
        <div className="mx-auto grid max-w-[1200px] gap-10" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          <Reveal>
            <p className="m-0 mb-3.5 font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
              {"/// Safety & privacy"}
            </p>
            <h2 className="m-0 mb-5 font-semibold leading-[1.02] tracking-[-.04em]" style={{ fontSize: "clamp(36px,5vw,60px)" }}>
              The non-negotiables
            </h2>
            <p className="m-0 max-w-[420px] text-[14.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
              Mindlens is support software. It is not a clinical service, a diagnostic tool, or an emergency service — and it is built so it can never quietly pretend to be one.
            </p>
            <div
              className="mt-[26px] rounded-[18px] px-[18px] py-4"
              style={{ border: "1px solid color-mix(in oklab, #ff6941 45%, transparent)", background: "color-mix(in oklab, #ff6941 8%, transparent)" }}
            >
              <p className="m-0 text-[13px] leading-[1.65]">
                <strong className="font-semibold">In immediate danger?</strong> Contact your local emergency services. Mindlens always surfaces real human resources first, before anything else.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.1} className="flex flex-col">
            {RULES.map((rule) => (
              <div key={rule.num} className="flex gap-4 py-[18px]" style={{ borderBottom: "1px solid var(--ml-hairline)" }}>
                <span className="whitespace-nowrap pt-[3px] font-[family-name:var(--font-geist-mono)] text-[11px]" style={{ color: "var(--e1)" }}>
                  {rule.num}
                </span>
                <div>
                  <h3 className="m-0 mb-1 text-[15.5px] font-semibold tracking-[-.01em]">{rule.title}</h3>
                  <p className="m-0 text-[13px] leading-[1.6]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                    {rule.body}
                  </p>
                </div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* --- Footer -------------------------------------------------------- */}
      {/* A hairline alone made the page's last section the one place that
        * never arrived with the rest — every other section reveals on
        * scroll; this didn't. The gradient border ties the close of the
        * page back into the same living palette driving everything above
        * it, rather than reading as a flat, separate zone underneath. */}
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
                <span className="text-[15px] font-semibold tracking-[-.02em]">Mindlens</span>
              </div>
              <p className="m-0 text-[12.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                Mindlens is support software — not a clinical service, diagnostic tool, or replacement for professional care. If you are in crisis, please reach a human: local emergency services or a crisis line near you.
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
                <FooterLink href={HF_URL} external>Hugging Face</FooterLink>
                <FooterLink href="#docs">Documentation</FooterLink>
              </Reveal>
            </div>
          </div>
          <div
            className="mt-[54px] pt-5"
            style={{ borderTop: "1px solid var(--ml-hairline)" }}
          >
            <p className="m-0 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
              A final-year project by Amiru Mallawa Arachchi · Cardiff Metropolitan University · 2026
            </p>
          </div>
        </div>
      </footer>
    </div>
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

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4" />
    </svg>
  );
}
