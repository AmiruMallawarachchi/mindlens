"use client";

import type { CSSProperties } from "react";
import { motion } from "motion/react";
import { BodyProps, Stage, Eyes, Fx, shadowFilter } from "./companion-avatar-primitives";

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

export function FernBody({ st, still, transition, size, withShadow }: BodyProps) {
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
