"use client";

import { motion } from "motion/react";
import { BodyProps, Stage, Fx, shadowFilter } from "./companion-avatar-primitives";

export function LensBody({ st, still, transition, size, withShadow }: BodyProps) {
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
