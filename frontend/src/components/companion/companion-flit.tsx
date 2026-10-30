"use client";

import { motion } from "motion/react";
import { BodyProps, Stage, Eyes, Fx, shadowFilter } from "./companion-avatar-primitives";

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

export function FlitBody({ st, still, transition, size, withShadow }: BodyProps) {
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
