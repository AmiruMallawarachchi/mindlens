"use client";

/**
 * Renders one of the five locked companions (lib/companions.ts) in one of
 * six states — design project "Mindlens: Emotional AI Companion", file
 * "Companion Expressions": "idle and listening matter most — they run the
 * longest. Budget your effort there." "One body" is a hard rule there too:
 * a companion deforms as a single unit, so every layer that owns a `transform`
 * animation (blink, wing-beat, flicker) is kept off any layer that also
 * carries the spring-driven state pose — otherwise a CSS `animation` silently
 * overwrites the pose `transform` while it runs.
 *
 * The state pose (translate/rotate/scale) uses real spring physics
 * (motion/react), one spring config per companion — Flit twitchy, Tide
 * liquid, Ember combustive, Fern slow and woody, Lens smooth and inertial —
 * matching lib/companions.ts's per-character `spring`. Ambient loops (flame
 * flicker, wing beat, water wave, frond sway, lens spin, blink) and the
 * per-state fx (the "?" bloom, the send spark, the thinking orbit, the
 * celebration scatter) stay CSS keyframes (tokens.css), same as the source.
 */

import type { CSSProperties, ReactNode } from "react";
import { motion, useReducedMotion, type Transition } from "motion/react";
import { getCompanion, type CompanionActivity, type CompanionId } from "@/lib/companions";
import { cn } from "@/lib/utils";
import type { EmotionId } from "@/lib/emotion";

const EYE = "#1b1430";

export function CompanionAvatar({
  companionId,
  activity = "idle",
  size = 88,
  withShadow = false,
  /** Crisis holds the companion completely still — no colour shift (handled
   * upstream: the caller passes the resting emotion reading during crisis),
   * no animation (handled here: every animation is gated on `still`). */
  frozen = false,
  className,
}: {
  companionId?: CompanionId | string | null;
  /** Accepted for callers that still read the live emotion into a mood —
   * none of the five companions carry a mood-specific face (eyes only, no
   * mouth), so it isn't consumed here. */
  mood?: EmotionId;
  activity?: CompanionActivity;
  size?: number;
  withShadow?: boolean;
  frozen?: boolean;
  className?: string;
}) {
  const companion = getCompanion(companionId);
  const reduceMotion = useReducedMotion();
  const still = !!reduceMotion || frozen;
  const st: CompanionActivity = still ? "idle" : activity;
  const transition: Transition = still
    ? { duration: 0 }
    : { type: "spring", stiffness: companion.spring.stiffness, damping: companion.spring.damping, mass: companion.spring.mass };

  const props: BodyProps = { st, still, transition, size, withShadow };

  const body = (() => {
    switch (companion.id) {
      case "flit":
        return <FlitBody {...props} />;
      case "tide":
        return <TideBody {...props} />;
      case "fern":
        return <FernBody {...props} />;
      case "lens":
        return <LensBody {...props} />;
      case "ember":
      default:
        return <EmberBody {...props} />;
    }
  })();

  return <div className={cn("shrink-0", className)}>{body}</div>;
}

interface BodyProps {
  st: CompanionActivity;
  still: boolean;
  transition: Transition;
  size: number;
  withShadow: boolean;
}

function shadowFilter(size: number): string {
  return `drop-shadow(0 ${Math.round(size * 0.16)}px ${Math.round(size * 0.32)}px -${Math.round(size * 0.1)}px var(--e1))`;
}

/**
 * A fixed design-space canvas scaled down to `size` — the mockup's own
 * technique — so every child keeps its exact approved pixel geometry rather
 * than being recomputed against a variable container size.
 */
function Stage({
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
function Eyes({
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
function Fx({ st, still, qTop = -6, sparkTop = 14 }: { st: CompanionActivity; still: boolean; qTop?: number; sparkTop?: number }) {
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

function EmberBody({ st, still, transition, size, withShadow }: BodyProps) {
  const listening = st === "listening";
  const cel = st === "celebrating";
  const squash = listening ? 1.07 : st === "sending" ? 0.9 : cel ? 1.05 : 1;

  return (
    <div role="img" aria-label="Ember, your companion" style={{ filter: withShadow ? shadowFilter(size) : undefined }}>
      <Stage size={size} width={120} height={140}>
        <motion.div
          className="relative h-full w-full"
          animate={{ y: cel ? -8 : listening ? -5 : 0, rotate: st === "asking" ? -7 : 0 }}
          transition={transition}
        >
          {/* Three layers so the squash, the 45° pin rotation and the
           * flicker never fight over the same element's transform. */}
          <motion.span
            aria-hidden="true"
            className="absolute"
            style={{ left: "50%", top: 18, width: 64, height: 64, marginLeft: -32, transformOrigin: "50% 88%" }}
            animate={{ scaleX: squash, scaleY: squash }}
            transition={transition}
          >
            <span style={{ display: "block", width: "100%", height: "100%", transform: "rotate(-45deg)" }}>
              <span
                style={{
                  display: "block",
                  width: "100%",
                  height: "100%",
                  borderRadius: "50% 50% 50% 6px",
                  background: "radial-gradient(circle at 40% 62%, #fff 2%, var(--e1) 46%, var(--e2) 100%)",
                  boxShadow: "0 22px 56px -10px var(--e1)",
                  filter: listening ? "brightness(1.22) saturate(1.1)" : undefined,
                  transition: "filter .5s ease",
                  animation: still ? undefined : `coFlicker ${listening ? 1.6 : 2.4}s ease-in-out infinite`,
                }}
              />
            </span>
          </motion.span>

          <Eyes top={45} dx={42} w={7} h={10} blink={listening ? 3.4 : 6.4} st={st} still={still} />

          <span
            aria-hidden="true"
            className="absolute"
            style={{
              left: "50%",
              bottom: 8,
              width: 66,
              height: 11,
              marginLeft: -33,
              borderRadius: "50%",
              background: "var(--e1)",
              filter: "blur(9px)",
              opacity: 0.75,
            }}
          />

          <Fx st={st} still={still} qTop={0} sparkTop={8} />
        </motion.div>
      </Stage>
    </div>
  );
}

function Wing({ side, wd, still, bodyLeft, bodyWidth, wingWidth }: { side: "l" | "r"; wd: number; still: boolean; bodyLeft: number; bodyWidth: number; wingWidth: number }) {
  const left = side === "l";
  return (
    <span
      aria-hidden="true"
      className="absolute"
      style={{
        top: FLIT_WING_TOP,
        width: wingWidth,
        height: 15,
        left: left ? bodyLeft - wingWidth : bodyLeft + bodyWidth,
        borderRadius: left ? "70% 14% 60% 10% / 88% 88% 16% 16%" : "14% 70% 10% 60% / 88% 88% 16% 16%",
        background: `linear-gradient(${left ? 100 : 80}deg, rgba(255,255,255,.10), rgba(255,255,255,.42))`,
        border: "1px solid rgba(255,255,255,.42)",
        boxShadow: "0 0 16px -4px var(--e1)",
        transformOrigin: left ? "100% 60%" : "0% 60%",
        animation: still ? undefined : `${left ? "coWing" : "coWingR"} ${wd}s ease-in-out infinite`,
      }}
    />
  );
}

/**
 * Flit's design box, tightened to hug the creature. The source mockup lays
 * it out on a 170×120 canvas with the body parked at x=88 — but `Stage`
 * normalises by the largest dimension, so that wide, mostly-empty canvas
 * rendered Flit visibly smaller than every other companion at the same
 * `size`. Same geometry, same proportions; only the surrounding whitespace
 * is gone, so `size` now means roughly the same visual mass across all five.
 */
const FLIT_W = 106;
const FLIT_H = 100;
const FLIT_BODY_L = 34;
const FLIT_BODY_W = 38;
const FLIT_WING_W = 34;
const FLIT_BODY_TOP = 31;
const FLIT_WING_TOP = 39;

function FlitBody({ st, still, transition, size, withShadow }: BodyProps) {
  const fast = st === "listening" || st === "celebrating";
  const wd = fast ? 0.22 : st === "thinking" ? 0.6 : 0.42;

  const pose = (() => {
    if (st === "listening") return { x: 10, y: -6, rotate: -10 };
    if (st === "celebrating") return { x: 0, y: -10, rotate: 0 };
    if (st === "asking") return { x: 0, y: 0, rotate: 9 };
    return { x: 0, y: 0, rotate: 0 };
  })();

  return (
    <div role="img" aria-label="Flit, your companion" style={{ filter: withShadow ? shadowFilter(size) : undefined }}>
      <Stage size={size} width={FLIT_W} height={FLIT_H}>
        <motion.div className="relative h-full w-full" animate={pose} transition={transition}>
          <Wing side="l" wd={wd} still={still} bodyLeft={FLIT_BODY_L} bodyWidth={FLIT_BODY_W} wingWidth={FLIT_WING_W} />
          <Wing side="r" wd={wd} still={still} bodyLeft={FLIT_BODY_L} bodyWidth={FLIT_BODY_W} wingWidth={FLIT_WING_W} />
          <motion.span
            aria-hidden="true"
            className="absolute rounded-full"
            style={{
              left: FLIT_BODY_L,
              top: FLIT_BODY_TOP,
              width: FLIT_BODY_W,
              height: FLIT_BODY_W,
              background: "radial-gradient(circle at 38% 32%, #fff, var(--e1) 62%, var(--e2) 100%)",
              boxShadow: `0 0 ${st === "listening" ? 58 : 40}px var(--e1)`,
              transition: "box-shadow .4s ease",
            }}
            animate={{ scale: st === "sending" ? 0.94 : 1 }}
            transition={transition}
          >
            <Eyes top={13} dx={9} w={6} h={8} blink={4.6} st={st} still={still} />
          </motion.span>
          <Fx st={st} still={still} qTop={3} sparkTop={21} />
        </motion.div>
      </Stage>
    </div>
  );
}

function TideBody({ st, still, transition, size, withShadow }: BodyProps) {
  const lvl = st === "listening" ? 82 : st === "celebrating" ? 74 : st === "thinking" ? 66 : st === "sending" ? 54 : 62;

  return (
    <div role="img" aria-label="Tide, your companion" style={{ filter: withShadow ? shadowFilter(size) : undefined }}>
      <Stage size={size} width={126} height={126}>
        <motion.div
          className="relative h-full w-full overflow-hidden"
          style={{
            borderRadius: 38,
            border: "1px solid rgba(255,255,255,.22)",
            background: "rgba(255,255,255,.03)",
            boxShadow: "inset 0 2px 20px rgba(255,255,255,.08)",
          }}
          animate={{
            rotate: st === "asking" ? -6 : 0,
            scaleX: st === "sending" ? 1.06 : 1,
            scaleY: st === "sending" ? 0.94 : 1,
          }}
          transition={transition}
        >
          <span
            aria-hidden="true"
            className="absolute"
            style={{
              left: "-14%",
              right: "-14%",
              bottom: -8,
              height: `${lvl}%`,
              borderRadius: "44% 46% 8px 8px / 32% 34% 8px 8px",
              background: "linear-gradient(180deg, var(--e1), var(--e2))",
              transition: "height .9s cubic-bezier(.3,.9,.2,1)",
              animation: still ? undefined : `coWave ${st === "listening" ? 3.2 : 5.5}s ease-in-out infinite`,
            }}
          />
          <Eyes top={56} dx={38} w={8} h={11} blink={5.8} st={st} still={still} />
          <Fx st={st} still={still} qTop={4} sparkTop={20} />
        </motion.div>
      </Stage>
    </div>
  );
}

function Frond({ side, turn, still }: { side: "l" | "r"; turn: number; still: boolean }) {
  const left = side === "l";
  const outer: CSSProperties = {
    position: "absolute",
    width: 44,
    height: 22,
    bottom: left ? 60 : 76,
    transformOrigin: left ? "100% 50%" : "0 50%",
    transform: `rotate(${left ? -turn : turn}deg)`,
    transition: "transform .8s cubic-bezier(.2,.9,.2,1)",
  };
  if (left) outer.left = 22;
  else outer.right = 22;

  return (
    <span aria-hidden="true" style={outer}>
      <span
        style={{
          display: "block",
          width: "100%",
          height: "100%",
          borderRadius: left ? "60% 8% 60% 8%" : "8% 60% 8% 60%",
          background: "linear-gradient(90deg, var(--e2), var(--e1))",
          opacity: 0.9,
          animation: still ? undefined : `coSway ${left ? 6 : 6.6}s ease-in-out ${left ? 0.3 : 0.6}s infinite`,
        }}
      />
    </span>
  );
}

function FernBody({ st, still, transition, size, withShadow }: BodyProps) {
  const turn = st === "listening" ? 16 : 0;
  const cel = st === "celebrating";

  return (
    <div role="img" aria-label="Fern, your companion" style={{ filter: withShadow ? shadowFilter(size) : undefined }}>
      <Stage size={size} width={130} height={150}>
        <motion.div
          className="relative h-full w-full"
          animate={{ scale: 0.92, y: cel ? -6 : 0, rotate: st === "asking" ? -6 : 0, scaleY: st === "sending" ? 0.92 : 1 }}
          transition={transition}
        >
          <span
            aria-hidden="true"
            className="absolute"
            style={{
              left: "50%",
              bottom: 16,
              width: 5,
              height: 76,
              marginLeft: -2.5,
              background: "linear-gradient(180deg, var(--e2), color-mix(in oklab, var(--e2) 40%, transparent))",
              borderRadius: 99,
              transformOrigin: "50% 100%",
              animation: still ? undefined : "coSway 6s ease-in-out infinite",
            }}
          />

          <Frond side="l" turn={turn} still={still} />
          <Frond side="r" turn={turn} still={still} />

          {cel && !still && (
            <motion.span
              aria-hidden="true"
              className="absolute"
              style={{
                left: 34,
                bottom: 92,
                width: 30,
                height: 15,
                borderRadius: "60% 8% 60% 8%",
                background: "var(--e2)",
                transformOrigin: "100% 50%",
                boxShadow: "0 0 18px var(--e2)",
              }}
              initial={{ rotate: 8, scale: 0.4, opacity: 0 }}
              animate={{ rotate: -34, scale: 1, opacity: 0.95 }}
              transition={transition}
            />
          )}

          <span
            aria-hidden="true"
            className="absolute"
            style={{
              left: "50%",
              top: 14,
              width: 52,
              height: 56,
              marginLeft: -26,
              borderRadius: "50% 50% 46% 46% / 62% 62% 38% 38%",
              background: "radial-gradient(circle at 36% 26%, #fff, var(--e1) 66%)",
              animation: still ? undefined : "coBlob 7.4s ease-in-out infinite",
            }}
          >
            <Eyes top={22} dx={12} w={7} h={10} blink={6.2} st={st} still={still} />
          </span>

          <Fx st={st} still={still} qTop={-2} sparkTop={6} />
        </motion.div>
      </Stage>
    </div>
  );
}

function LensBody({ st, still, transition, size, withShadow }: BodyProps) {
  const spin = st === "listening" ? 5 : st === "thinking" ? 2.2 : 22;
  const clarity = st === "listening" ? 0.95 : 0.6;

  return (
    <div role="img" aria-label="The Lens, your companion" style={{ filter: withShadow ? shadowFilter(size) : undefined }}>
      <Stage size={size} width={150} height={150}>
        <motion.div
          className="relative h-full w-full"
          animate={{ scale: st === "sending" ? 0.86 : st === "celebrating" ? 0.99 : 0.92, rotate: st === "asking" ? -5 : 0 }}
          transition={transition}
        >
          <span
            aria-hidden="true"
            className="absolute"
            style={{
              inset: 14,
              borderRadius: "50%",
              background: "conic-gradient(from 210deg, var(--e1), var(--e2), var(--e3), var(--e1))",
              filter: st === "thinking" ? "blur(20px)" : "blur(14px)",
              opacity: 0.85,
              transition: "filter .5s ease",
              animation: still ? undefined : `coSpin ${spin}s linear infinite`,
            }}
          />
          <span
            aria-hidden="true"
            className="absolute"
            style={{
              inset: 22,
              borderRadius: "50%",
              background: `radial-gradient(circle at 34% 26%, rgba(255,255,255,${clarity}), rgba(255,255,255,.06) 46%, transparent 62%)`,
              border: "1px solid rgba(255,255,255,.28)",
              boxShadow: "inset 0 -18px 40px color-mix(in oklab, var(--e1) 45%, transparent), 0 26px 60px -16px var(--e1)",
              transition: "background 1.2s ease",
              animation: still ? undefined : "coBlob 9s ease-in-out infinite",
            }}
          />
          <Fx st={st} still={still} qTop={8} sparkTop={30} />
        </motion.div>
      </Stage>
    </div>
  );
}
