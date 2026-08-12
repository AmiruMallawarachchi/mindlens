"use client";

/**
 * Breathe player — ported from the approved mockup (Mindlens Chat.dc.html,
 * "Breathe player"). A gradient panel in the emotion colours with a live
 * waveform, the 4·7·8 phase readout, volume/pace rows, and transport
 * controls. Entirely client-side — the exercise is the content.
 *
 * Faithful-to-mockup details: the 26 viz bars pause (not hide) when idle,
 * the countdown renders as a strip ("4 · 3 · 2 …"), the clock counts total
 * elapsed seconds, and the pace transport genuinely changes the phase
 * lengths (slower = 5·8·9, faster = 3·6·7) rather than being decorative.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

const BASE_PHASES = [
  { label: "Breathe in", seconds: 4 },
  { label: "Hold", seconds: 7 },
  { label: "Breathe out", seconds: 8 },
] as const;

/** -1 = slower, 0 = 4·7·8, +1 = faster. */
type Pace = -1 | 0 | 1;

function phasesForPace(pace: Pace) {
  return BASE_PHASES.map((p) => ({ ...p, seconds: Math.max(2, p.seconds - pace) }));
}

function paceLabel(pace: Pace): string {
  return phasesForPace(pace).map((p) => p.seconds).join("·");
}

function fmt(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function BreatheCard() {
  const [breathing, setBreathing] = useState(false);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [remaining, setRemaining] = useState<number>(BASE_PHASES[0].seconds);
  const [cycles, setCycles] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [pace, setPace] = useState<Pace>(0);
  const reduceMotion = useReducedMotion();
  const phaseRef = useRef(0);

  const phases = useMemo(() => phasesForPace(pace), [pace]);

  useEffect(() => {
    if (!breathing) return;
    const tick = setInterval(() => {
      setElapsed((e) => e + 1);
      setRemaining((left) => {
        if (left > 1) return left - 1;
        const next = (phaseRef.current + 1) % 3;
        phaseRef.current = next;
        setPhaseIndex(next);
        if (next === 0) setCycles((c) => c + 1);
        return phases[next].seconds;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [breathing, phases]);

  const shiftPace = (direction: -1 | 1) => {
    setPace((current) => {
      const next = Math.min(1, Math.max(-1, current + direction)) as Pace;
      if (next !== current) {
        // Restart the current phase at the new pace so count and label agree.
        setRemaining(phasesForPace(next)[phaseRef.current].seconds);
      }
      return next;
    });
  };

  const phase = phases[phaseIndex];
  const countdown = breathing
    ? Array.from({ length: Math.min(remaining, 5) }, (_, i) => remaining - i).join(" · ") +
      (remaining > 5 ? " …" : "")
    : paceLabel(pace).split("·").join(" · ");

  // Mockup's deterministic pseudo-random bar field.
  const lines = useMemo(
    () =>
      Array.from({ length: 26 }, (_, i) => ({
        h: 26 + Math.round(20 * Math.abs(Math.sin(i * 0.7))),
        o: (0.4 + 0.5 * Math.abs(Math.cos(i * 0.5))).toFixed(2),
        dur: (2.4 + (i % 5) * 0.4).toFixed(1),
        delay: (i * 0.07).toFixed(2),
      })),
    [],
  );

  return (
    <div
      className="relative overflow-hidden rounded-[22px] p-4"
      style={{
        background:
          "linear-gradient(158deg, color-mix(in oklab, var(--e1) 52%, #120e0a), color-mix(in oklab, var(--e2) 40%, #120e0a))",
        boxShadow: "0 20px 44px -22px var(--e1)",
        transition: "background 1.6s",
      }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-[14%] -top-[30%] aspect-square w-[62%] rounded-full"
        style={{
          background:
            "radial-gradient(circle, color-mix(in oklab, var(--e2) 55%, transparent), transparent 68%)",
          filter: "blur(26px)",
        }}
      />

      <div className="relative flex items-center justify-between">
        <span
          className="rounded-[99px] border px-2.5 py-1 font-[family-name:var(--font-geist-mono)] text-[9px] uppercase tracking-[.13em]"
          style={{
            background: "rgba(255,255,255,.22)",
            borderColor: "rgba(255,255,255,.32)",
            color: "#fffdf8",
          }}
        >
          Stress relief
        </span>
        <span className="font-[family-name:var(--font-geist-mono)] text-[11px]" style={{ color: "rgba(255,253,248,.92)" }}>
          {fmt(elapsed)}
        </span>
      </div>

      <div aria-hidden="true" className="relative mx-0 mb-1 mt-4 flex h-[46px] items-center gap-1">
        {lines.map((line, i) => (
          <span
            key={i}
            className="flex-1 origin-center rounded-[2px]"
            style={{
              height: line.h,
              background: `rgba(255,253,248,${line.o})`,
              animation: reduceMotion
                ? undefined
                : `mlViz ${line.dur}s ease-in-out ${line.delay}s infinite`,
              animationPlayState: breathing ? "running" : "paused",
            }}
          />
        ))}
      </div>

      <p
        className="relative m-0 font-[family-name:var(--font-newsreader)] text-[23px] font-light tracking-[-.01em]"
        style={{ color: "#fffdf8" }}
      >
        {breathing ? phase.label : "Four in, seven held, eight out."}
      </p>
      <p
        className="relative mt-[3px] font-[family-name:var(--font-geist-mono)] text-[14px] tracking-[.18em]"
        style={{ color: "rgba(255,253,248,.9)" }}
      >
        {countdown}
      </p>

      <div className="relative mt-3.5 flex flex-col gap-2">
        <SliderRow label="Volume" percent={54} value="54" />
        <SliderRow label="Pace" percent={34 + pace * 22} value={paceLabel(pace)} />
      </div>

      <div className="relative mt-4 flex items-center justify-center gap-4">
        <TransportButton label="Slower" onClick={() => shiftPace(-1)} disabled={pace === -1}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <path d="M11 12 20 5v14zM4 5h2v14H4z" />
          </svg>
        </TransportButton>
        <button
          type="button"
          aria-label={breathing ? "Pause" : "Start"}
          onClick={() => setBreathing((b) => !b)}
          className="grid size-12 cursor-pointer place-items-center rounded-full border-none transition-transform hover:scale-105"
          style={{
            background: "#fffdf8",
            color: "#171310",
            boxShadow: "0 10px 24px -10px rgba(0,0,0,.45)",
          }}
        >
          {breathing ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 5h4v14H7zM13 5h4v14h-4z" />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 4v16l13-8Z" />
            </svg>
          )}
        </button>
        <TransportButton label="Faster" onClick={() => shiftPace(1)} disabled={pace === 1}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <path d="M13 12 4 5v14zM18 5h2v14h-2z" />
          </svg>
        </TransportButton>
      </div>

      <p className="relative mt-3 text-center text-[11px]" style={{ color: "rgba(255,253,248,.82)" }}>
        {cycles > 0
          ? `${cycles} ${cycles === 1 ? "round" : "rounds"} done`
          : "Three rounds is usually enough to feel it."}
      </p>
    </div>
  );
}

function SliderRow({ label, percent, value }: { label: string; percent: number; value: string }) {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <div className="flex items-center gap-2.5">
      <span
        className="w-[52px] font-[family-name:var(--font-geist-mono)] text-[9px] uppercase tracking-[.12em]"
        style={{ color: "rgba(255,253,248,.82)" }}
      >
        {label}
      </span>
      <span className="relative h-[3px] flex-1 rounded-[2px]" style={{ background: "rgba(255,253,248,.28)" }}>
        <span
          className="absolute bottom-0 left-0 top-0 rounded-[2px]"
          style={{ width: `${clamped}%`, background: "#fffdf8", transition: "width .4s" }}
        />
        <span
          className="absolute top-1/2 size-[9px] rounded-full"
          style={{
            left: `${clamped}%`,
            margin: "-4.5px 0 0 -4.5px",
            background: "#fffdf8",
            boxShadow: "0 2px 6px rgba(0,0,0,.25)",
            transition: "left .4s",
          }}
        />
      </span>
      <span className="font-[family-name:var(--font-geist-mono)] text-[10.5px]" style={{ color: "rgba(255,253,248,.92)" }}>
        {value}
      </span>
    </div>
  );
}

function TransportButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="grid size-8 cursor-pointer place-items-center rounded-full border-none transition-colors disabled:cursor-default disabled:opacity-40"
      style={{ background: "rgba(255,253,248,.16)", color: "#fffdf8" }}
    >
      {children}
    </button>
  );
}
