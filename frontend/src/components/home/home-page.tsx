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
import { useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";
import { MindlensMark } from "@/components/brand/wordmark";
import { useGrade } from "@/lib/use-grade";
import {
  EMOTION_ORDER,
  EMOTION_STATES,
  emotionCssVars,
  type EmotionId,
} from "@/lib/emotion";
import { Reveal } from "./reveal";

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
    body: "A team of agents drafts a reply in the voice of a wise coaching friend: practical, warm, 4–5 sentences, always ending in a choice — music, breathing, journaling, or just talking.",
  },
  {
    num: "05",
    title: "The record",
    body: "Moods, progress and breakthroughs are logged to your private memory — so next week's Mindlens knows what this week's you worked through.",
  },
];

const MODELS = [
  { id: "mindlens-emotion", title: "Emotion classifier", body: "28 emotion classes (GoEmotions), folded into the 12 named states that light the interface." },
  { id: "mindlens-mh", title: "Mental-health signal", body: "Screens longer messages for anxiety, depression and stress signals — quietly, in context." },
  { id: "mindlens-crisis", title: "Crisis detector", body: "Deterministic screening that runs before every single turn. The one model that can stop everything." },
  { id: "mindlens-reranker", title: "RAG reranker", body: "Re-orders passages retrieved from a curated therapy corpus so the most relevant guidance wins." },
  { id: "mindlens-distortion", title: "Distortion classifier", body: "Spots thinking traps — catastrophizing, all-or-nothing, mind-reading — so they can be named gently." },
];

const DOCS = [
  { file: "SYSTEM.md", title: "The single source of truth", body: "Architecture, the five models, agent behavior, safety rules — everything that is non-negotiable, in one file." },
  { file: "API.md", title: "HTTP & WebSocket contract", body: "Every endpoint, the streaming chat protocol, and how agent activity reaches the client in real time." },
  { file: "DEPLOYMENT.md", title: "Render & Vercel runbook", body: "How the backend, persistent vector store and web client ship — and how production fails closed." },
];

const RULES = [
  { num: "01", title: "Crisis answers are template-only", body: "Zero LLM calls when it matters most. Every crisis response is written and vetted by humans." },
  { num: "02", title: "The safety gate runs first, every turn", body: "No agent, prompt or feature can skip it. Safety overrides convenience — by design." },
  { num: "03", title: "Your words stay yours", body: "JWT in httpOnly cookies, every database query scoped to you, rate limits everywhere." },
  { num: "04", title: "Memory is visible", body: "Nothing is remembered without appearing in your Memory first — you can see and delete all of it." },
  { num: "05", title: "Never a diagnosis", body: "Mindlens names feelings in plain language, with the confidence beside it. It never labels you." },
];

const GITHUB_URL = "https://github.com/AmiruMallawarachchi";
const HF_URL = "https://huggingface.co/AmiruMallawarachchi";

export function HomePage() {
  const { isDay, toggleGrade } = useGrade();
  const [activeId, setActiveId] = useState<EmotionId | null>(null);
  const reduceMotion = useReducedMotion();

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
          <span
            className="absolute left-[8%] top-[12%] aspect-square w-[44vw] rounded-full"
            style={{
              background: "radial-gradient(circle, color-mix(in oklab, var(--e1) 55%, transparent), transparent 70%)",
              filter: "blur(70px)",
              animation: "mlBlobA 16s ease-in-out infinite",
            }}
          />
          <span
            className="absolute right-[4%] top-[30%] aspect-square w-[38vw] rounded-full"
            style={{
              background: "radial-gradient(circle, color-mix(in oklab, var(--e2) 55%, transparent), transparent 70%)",
              filter: "blur(80px)",
              animation: "mlBlobB 20s ease-in-out infinite",
            }}
          />
        </div>
      )}

      {/* --- Nav --------------------------------------------------------- */}
      <nav
        className="fixed left-1/2 top-4 z-[60] flex w-max max-w-[calc(100vw-32px)] -translate-x-1/2 items-center gap-6 whitespace-nowrap rounded-[99px] py-2.5 pl-[18px] pr-3"
        style={{
          background: "var(--ml-panel)",
          backdropFilter: "blur(20px) saturate(1.2)",
          border: "1px solid var(--ml-hairline)",
          boxShadow: "0 12px 40px -18px rgba(36,26,14,.25)",
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
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-[99px] px-4 py-[9px] text-[12.5px] font-medium no-underline"
          style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
        >
          Open the app <span className="text-[14px] leading-none">→</span>
        </Link>
      </nav>

      {/* --- Hero ---------------------------------------------------------- */}
      <header
        id="top"
        className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pb-[60px] pt-[120px]"
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
            <Link
              href="/app"
              className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
              style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)", boxShadow: "0 18px 40px -16px var(--e1)" }}
            >
              Start a conversation
            </Link>
            <a
              href="#how"
              className="inline-flex items-center gap-2 rounded-[99px] px-7 py-[15px] text-[14.5px] font-medium no-underline"
              style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline-strong)", backdropFilter: "blur(12px)" }}
            >
              Read how it works
            </a>
          </div>
          <p className="mt-[22px] font-[family-name:var(--font-geist-mono)] text-[10.5px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
            Free · Private · Not a replacement for professional care
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
      <section className="px-6">
        <Reveal
          className="relative mx-auto h-[min(72vh,560px)] max-w-[1200px] overflow-hidden rounded-[30px]"
          delay={0.1}
        >
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 45%, var(--ml-canvas)), color-mix(in oklab, var(--e2) 35%, var(--ml-canvas)))",
              boxShadow: "0 34px 80px -30px color-mix(in oklab, var(--e1) 60%, rgba(36,26,14,.4))",
            }}
          />
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
                  <span className="font-[family-name:var(--font-geist-mono)] text-[11.5px]" style={{ color: "var(--e2)" }}>
                    {model.id}
                  </span>
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
                  href={GITHUB_URL}
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
      <footer className="px-6 pb-10 pt-[70px]" style={{ borderTop: "1px solid var(--ml-hairline)" }}>
        <div className="mx-auto max-w-[1200px]">
          <div className="flex flex-wrap items-start justify-between gap-[30px]">
            <div className="max-w-[420px]">
              <div className="mb-3.5 flex items-center gap-2">
                <MindlensMark size={20} />
                <span className="text-[15px] font-semibold tracking-[-.02em]">Mindlens</span>
              </div>
              <p className="m-0 text-[12.5px] leading-[1.7]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
                Mindlens is support software — not a clinical service, diagnostic tool, or replacement for professional care. If you are in crisis, please reach a human: local emergency services or a crisis line near you.
              </p>
            </div>
            <div className="flex flex-wrap gap-11 text-[13px]">
              <div className="flex flex-col gap-2.5">
                <span className="font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                  Product
                </span>
                <Link href="/app" style={{ color: "var(--ml-muted)" }}>Open the app</Link>
                <a href="#emotions" style={{ color: "var(--ml-muted)" }}>Emotion system</a>
              </div>
              <div className="flex flex-col gap-2.5">
                <span className="font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.14em]" style={{ color: "var(--ml-faint)" }}>
                  Open source
                </span>
                <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" style={{ color: "var(--ml-muted)" }}>GitHub</a>
                <a href={HF_URL} target="_blank" rel="noopener noreferrer" style={{ color: "var(--ml-muted)" }}>Hugging Face</a>
                <a href="#docs" style={{ color: "var(--ml-muted)" }}>Documentation</a>
              </div>
            </div>
          </div>
          <p className="m-0 mt-[54px] font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[.13em]" style={{ color: "var(--ml-faint)" }}>
            A final-year project by Amiru Mallawa Arachchi · Cardiff Metropolitan University · 2026
          </p>
        </div>
      </footer>
    </div>
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
