"use client";

import { motion } from "motion/react";
import { BodyProps, Stage, Eyes, Fx, shadowFilter } from "./companion-avatar-primitives";

export function EmberBody({ st, still, transition, size, withShadow }: BodyProps) {
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
