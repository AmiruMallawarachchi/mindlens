"use client";

import { motion } from "motion/react";
import { BodyProps, Stage, Eyes, Fx, shadowFilter } from "./companion-avatar-primitives";

export function TideBody({ st, still, transition, size, withShadow }: BodyProps) {
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
