"use client";

import type { CSSProperties, ReactNode } from "react";
import type { Transition } from "motion/react";
import type { CompanionActivity } from "@/lib/companions";

const EYE = "#1b1430";

export interface BodyProps {
  st: CompanionActivity;
  still: boolean;
  transition: Transition;
  size: number;
  withShadow: boolean;
}

export function shadowFilter(size: number): string {
  return `drop-shadow(0 ${Math.round(size * 0.16)}px ${Math.round(size * 0.32)}px -${Math.round(size * 0.1)}px var(--e1))`;
}

/**
 * A fixed design-space canvas scaled down to `size` — the mockup's own
 * technique — so every child keeps its exact approved pixel geometry rather
 * than being recomputed against a variable container size.
 */
export function Stage({
  size,
  width,
  height,
  children,
}: {
  size: number;
  width: number;
  height: number;
  children: ReactNode;
}) {
  const scale = size / Math.max(width, height);
  return (
    <div className="relative shrink-0" style={{ width: width * scale, height: height * scale }}>
      <div style={{ position: "absolute", left: 0, top: 0, width, height, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        {children}
      </div>
    </div>
  );
}

/**
 * Two blinking eyes. Split into an outer wrapper (the state-driven pose —
 * drift while thinking, widen while listening, curve into a smile while
 * celebrating — eased with a plain CSS transition) and an inner dot (the
 * blink keyframe loop) so the blink animation's own `transform` never
 * overwrites the pose transform, or vice versa.
 */
export function Eyes({
  top,
  dx,
  w,
  h,
  blink,
  st,
  still,
  color = EYE,
}: {
  top: number;
  dx: number;
  w: number;
  h: number;
  blink: number;
  st: CompanionActivity;
  still: boolean;
  color?: string;
}) {
  const curved = st === "celebrating";
  const wrapH = curved ? Math.round(h * 0.42) : h;
  const wrapTop = curved ? top + 2 : top;
  const wrapRadius = curved ? "99px 99px 2px 2px" : "99px";
  const pose = st === "thinking" ? "translateX(3px)" : st === "listening" ? "scaleY(1.18)" : "none";

  const wrapperStyle = (side: "left" | "right"): CSSProperties => ({
    position: "absolute",
    top: wrapTop,
    [side]: dx,
    width: w,
    height: wrapH,
    borderRadius: wrapRadius,
    transform: pose,
    transition: "transform .5s cubic-bezier(.2,.9,.2,1), height .4s ease, top .4s ease",
  });

  const dot: CSSProperties = {
    display: "block",
    width: "100%",
    height: "100%",
    borderRadius: "inherit",
    background: color,
    animation: still ? undefined : `coBlink ${blink}s ease-in-out infinite`,
  };

  return (
    <>
      <span aria-hidden="true" style={wrapperStyle("left")}>
        <span style={dot} />
      </span>
      <span aria-hidden="true" style={wrapperStyle("right")}>
        <span style={dot} />
      </span>
    </>
  );
}

/** The per-state overlay: a "?" that blooms while asking, a spark lifting
 * off while sending, an orbiting mote while thinking, sparkles scattering
 * while celebrating. Nothing renders while still (crisis / reduced motion). */
export function Fx({ st, still, qTop = -6, sparkTop = 14 }: { st: CompanionActivity; still: boolean; qTop?: number; sparkTop?: number }) {
  if (still) return null;

  if (st === "asking") {
    return (
      <span
        aria-hidden="true"
        className="absolute font-[family-name:var(--font-newsreader)] font-light"
        style={{
          top: qTop,
          left: "50%",
          marginLeft: 14,
          fontSize: 26,
          color: "var(--e1)",
          textShadow: "0 0 18px var(--e1)",
          animation: "coQBloom 2.6s ease-in-out infinite",
        }}
      >
        ?
      </span>
    );
  }

  if (st === "sending") {
    return (
      <span
        aria-hidden="true"
        className="absolute rounded-full"
        style={{
          top: sparkTop,
          left: "50%",
          width: 6,
          height: 6,
          marginLeft: -3,
          background: "#fff",
          boxShadow: "0 0 14px 3px var(--e1)",
          animation: "coSparkUp 1.2s ease-out infinite",
        }}
      />
    );
  }

  if (st === "thinking") {
    return (
      <span aria-hidden="true" className="absolute" style={{ inset: -8, borderRadius: "50%", animation: "coOrbit 3.4s linear infinite" }}>
        <span
          style={{
            position: "absolute",
            top: 0,
            left: "50%",
            width: 5,
            height: 5,
            marginLeft: -2.5,
            borderRadius: "50%",
            background: "var(--e2)",
            boxShadow: "0 0 12px var(--e2)",
          }}
        />
      </span>
    );
  }

  if (st === "celebrating") {
    const points: Array<[number, number]> = [
      [-34, -26],
      [30, -30],
      [-26, 22],
      [34, 16],
      [0, -40],
    ];
    return (
      <>
        {points.map(([dx, dy], i) => (
          <span
            key={i}
            aria-hidden="true"
            className="absolute rounded-full"
            style={
              {
                top: "50%",
                left: "50%",
                width: 5,
                height: 5,
                background: i % 2 ? "var(--e2)" : "#fff",
                boxShadow: "0 0 10px var(--e1)",
                "--dx": `${dx}px`,
                "--dy": `${dy}px`,
                animation: `coScatter 1.6s ease-out ${i * 0.16}s infinite`,
              } as CSSProperties
            }
          />
        ))}
      </>
    );
  }

  return null;
}
