"use client";

/**
 * The field — design.md §2.
 *
 * ShaderGradient (React Three Fiber) fed the active state's c1/c2/c3 plus an
 * intensity and a temperament, where temperament maps to uSpeed/uStrength.
 *
 * Three layers, back to front:
 *  1. a CSS wash reading --e1/--e2/--e3 — always present. Because those
 *     properties are @property-registered (tokens.css), this layer is what
 *     actually delivers §2's 1.6s crossfade; three.js would otherwise swap
 *     colours on a frame boundary.
 *  2. the ShaderGradient canvas — lazy, client-only, skipped entirely on
 *     reduced-motion or low-power devices.
 *  3. grain (§1.3).
 *
 * Fallback note: an earlier build used a bespoke six-mood shader component
 * for this role; it couldn't express the twelve real states, so the
 * fallback here is a static frame built from the actual emotion tokens
 * instead — same role, correct colours, and it's what every screen uses now
 * that all four secondary pages have been rebuilt against this design system.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import { TEMPERAMENT_MOTION, type EmotionReading } from "@/lib/emotion";

const ShaderGradientCanvas = dynamic(
  () => import("shadergradient").then((m) => m.ShaderGradientCanvas),
  { ssr: false },
);
const ShaderGradient = dynamic(
  () => import("shadergradient").then((m) => m.ShaderGradient),
  { ssr: false },
);

/**
 * Cheap, honest capability check. We are deciding whether to hand a phone a
 * continuously-animating WebGL surface, so we err toward "no".
 */
function useCanRenderField(): boolean {
  const [capable, setCapable] = useState(false);

  useEffect(() => {
    const cores = navigator.hardwareConcurrency ?? 4;
    const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
    if (cores < 4 || memory < 4) return;

    // If WebGL can't be acquired at all, the canvas would mount and render
    // nothing — worse than the static frame.
    const probe = document.createElement("canvas");
    const gl =
      probe.getContext("webgl2") ?? probe.getContext("webgl");
    if (!gl) return;
    // Release the probe context immediately; some drivers cap live contexts.
    const lose = gl.getExtension("WEBGL_lose_context");
    lose?.loseContext();

    setCapable(true);
  }, []);

  return capable;
}

export function EmotionField({ reading }: { reading: EmotionReading }) {
  const reduceMotion = useReducedMotion();
  const capable = useCanRenderField();
  const motionParams = TEMPERAMENT_MOTION[reading.state.temperament];

  // §6: reduced motion gets a static frame, and the layout is identical.
  const animate = capable && !reduceMotion;

  return (
    <div
      aria-hidden="true"
      className="ml-grain pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      style={{ background: "var(--ml-canvas)" }}
    >
      {/* Layer 1 — the crossfading wash. Opacity tracks intensity so that at
       * 0.2 the room is barely tinted and at 1.0 everything agrees (§2). */}
      <div
        className="absolute inset-0"
        style={{
          opacity: 0.28 + 0.52 * reading.intensity,
          transition: "opacity 1600ms var(--ml-ease)",
          background: `
            radial-gradient(120% 90% at 18% 8%, color-mix(in oklab, var(--e1) 62%, transparent) 0%, transparent 62%),
            radial-gradient(100% 80% at 84% 22%, color-mix(in oklab, var(--e2) 54%, transparent) 0%, transparent 58%),
            radial-gradient(140% 110% at 50% 108%, color-mix(in oklab, var(--e3) 88%, transparent) 0%, transparent 70%)
          `,
        }}
      />

      {/* Layer 2 — the shader field. */}
      {animate && (
        <div
          className="absolute inset-0"
          style={{
            opacity: 0.2 + 0.3 * reading.intensity,
            transition: "opacity 1600ms var(--ml-ease)",
            mixBlendMode: "screen",
          }}
        >
          <ShaderGradientCanvas
            style={{ width: "100%", height: "100%" }}
            pixelDensity={1}
            fov={40}
          >
            <ShaderGradient
              control="props"
              type="waterPlane"
              animate="on"
              enableTransition
              color1={reading.state.c1}
              color2={reading.state.c2}
              color3={reading.state.c3}
              uSpeed={motionParams.speed}
              uStrength={motionParams.strength}
              uDensity={1.3}
              uFrequency={5.5}
              uAmplitude={0}
              cDistance={2.9}
              cPolarAngle={125}
              cAzimuthAngle={180}
              cameraZoom={9.1}
              positionX={0}
              positionY={0}
              positionZ={0}
              rotationX={50}
              rotationY={0}
              rotationZ={-60}
              brightness={1.1}
              lightType="3d"
              grain="off"
              zoomOut={false}
            />
          </ShaderGradientCanvas>
        </div>
      )}

      {/* Layer 3 — vignette back to the canvas colour. Without it the field
       * lifts the edges of the screen and the dark canvas of §1.3 stops
       * reading as dark; the room should glow from the middle, not the rim. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 100% at 50% 45%, transparent 30%, color-mix(in oklab, var(--ml-canvas) 88%, transparent) 100%)",
        }}
      />
    </div>
  );
}
