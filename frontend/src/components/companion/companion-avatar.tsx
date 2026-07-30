"use client";

/**
 * Renders any companion from the cast (lib/companions.ts). "nimbus" delegates
 * straight to the existing <Nimbus> — its morph/expression system stays
 * exactly as built, untouched. The other nine get a simpler shared
 * construction: a CSS shape (per companion.shape) plus the same blink/float
 * motion Nimbus uses, coloured from the live --e1/--e2 emotion tokens.
 */

import { useId } from "react";
import { useReducedMotion } from "motion/react";
import { getCompanion, type CompanionId, type CompanionShape } from "@/lib/companions";
import { Nimbus, type NimbusActivity } from "./nimbus";
import { cn } from "@/lib/utils";
import type { EmotionId } from "@/lib/emotion";

export function CompanionAvatar({
  companionId,
  mood = "balanced",
  activity = "idle",
  size = 88,
  withShadow = false,
  className,
}: {
  companionId?: CompanionId | string | null;
  mood?: EmotionId;
  activity?: NimbusActivity;
  size?: number;
  withShadow?: boolean;
  className?: string;
}) {
  const companion = getCompanion(companionId);

  if (companion.shape === "cloud") {
    return <Nimbus mood={mood} activity={activity} size={size} withShadow={withShadow} className={className} />;
  }

  return (
    <ShapeAvatar shape={companion.shape} size={size} withShadow={withShadow} className={className} name={companion.name} />
  );
}

const CLIP_PATH: Partial<Record<CompanionShape, string>> = {
  flame: "polygon(50% 0%, 80% 28%, 90% 62%, 68% 100%, 32% 100%, 10% 62%, 20% 28%)",
  star: "polygon(50% 0%, 61% 39%, 100% 50%, 61% 61%, 50% 100%, 39% 61%, 0% 50%, 39% 39%)",
};

const BORDER_RADIUS: Partial<Record<CompanionShape, string>> = {
  jelly: "50% 50% 14% 14%",
  bell: "50% 50% 20% 20%",
  square: "26%",
  sphere: "50%",
  dot: "50%",
};

/** Anchor is explicitly "colourless" — everything else follows the room. */
const GRADIENT: Partial<Record<CompanionShape, string>> = {
  square: "radial-gradient(circle at 34% 26%, #cfd3da, #9aa0ab 75%)",
};
const DEFAULT_GRADIENT =
  "radial-gradient(circle at 34% 26%, color-mix(in oklab, var(--e2) 82%, white), var(--e1) 75%)";

function ShapeAvatar({
  shape,
  size,
  withShadow,
  className,
  name,
}: {
  shape: CompanionShape;
  size: number;
  withShadow: boolean;
  className?: string;
  name: string;
}) {
  const uid = useId().replace(/:/g, "");
  const reduceMotion = useReducedMotion();
  const scale = size / 88;
  const showFace = size >= 40 && shape !== "sphere";
  const still = shape === "square";

  if (shape === "crescent") {
    return (
      <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          role="img"
          aria-label={`${name}, your companion`}
          style={{
            animation: reduceMotion ? undefined : "nimbusFloat 5s ease-in-out infinite",
            filter: withShadow ? "drop-shadow(0 10px 20px var(--e1))" : undefined,
          }}
        >
          <defs>
            <linearGradient id={`grad-${uid}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="var(--e2)" />
              <stop offset="100%" stopColor="var(--e1)" />
            </linearGradient>
            <mask id={`mask-${uid}`}>
              <rect width="100" height="100" fill="white" />
              <circle cx="62" cy="36" r="34" fill="black" />
            </mask>
          </defs>
          <circle cx="50" cy="50" r="42" fill={`url(#grad-${uid})`} mask={`url(#mask-${uid})`} />
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <div
        role="img"
        aria-label={`${name}, your companion`}
        className="absolute inset-0"
        style={{
          background: GRADIENT[shape] ?? DEFAULT_GRADIENT,
          clipPath: CLIP_PATH[shape],
          borderRadius: BORDER_RADIUS[shape],
          boxShadow: withShadow
            ? `0 ${Math.round(18 * scale)}px ${Math.round(40 * scale)}px -${Math.round(12 * scale)}px var(--e1)`
            : `0 ${Math.max(4, Math.round(6 * scale))}px ${Math.max(10, Math.round(16 * scale))}px -${Math.max(3, Math.round(6 * scale))}px var(--e1)`,
          animation: reduceMotion || still ? undefined : "nimbusFloat 5s ease-in-out infinite",
          transition: "background 1.6s",
        }}
      >
        {shape === "jelly" && <JellyTentacles scale={scale} />}
        {shape === "frond" && <FrondLeaves scale={scale} />}
        {shape === "bell" && <BellCord scale={scale} />}
        {shape === "dot" && <DotGlow />}

        {showFace && (
          <>
            <Eye left="30%" scale={scale} reduceMotion={!!reduceMotion} delay={0} />
            <Eye left="58%" scale={scale} reduceMotion={!!reduceMotion} delay={0.15} />
          </>
        )}
      </div>
    </div>
  );
}

function Eye({ left, scale, reduceMotion, delay }: { left: string; scale: number; reduceMotion: boolean; delay: number }) {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        top: "38%",
        left,
        width: Math.max(2, 6 * scale),
        height: Math.max(2, 8 * scale),
        borderRadius: 99,
        background: "rgba(26,20,14,.78)",
        animation: reduceMotion ? undefined : `nimbusBlink 6s ease-in-out ${delay}s infinite`,
      }}
    />
  );
}

function JellyTentacles({ scale }: { scale: number }) {
  return (
    <>
      {[22, 42, 62, 82].map((left, i) => (
        <span
          key={left}
          aria-hidden="true"
          style={{
            position: "absolute",
            left: `${left}%`,
            top: "78%",
            width: 1.5 * scale,
            height: 22 * scale,
            background: `linear-gradient(180deg, ${i % 2 === 0 ? "var(--e1)" : "var(--e2)"}, transparent)`,
          }}
        />
      ))}
    </>
  );
}

function FrondLeaves({ scale }: { scale: number }) {
  return (
    <>
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "50%",
          top: "20%",
          width: 1.5 * scale,
          height: "60%",
          background: "rgba(255,255,255,.5)",
          transform: "translateX(-50%)",
        }}
      />
      {[
        { top: "30%", left: "38%", rotate: -35 },
        { top: "44%", left: "60%", rotate: 35 },
        { top: "58%", left: "38%", rotate: -35 },
      ].map((leaf, i) => (
        <span
          key={i}
          aria-hidden="true"
          style={{
            position: "absolute",
            top: leaf.top,
            left: leaf.left,
            width: 16 * scale,
            height: 8 * scale,
            borderRadius: "0 99px 0 99px",
            background: "rgba(255,255,255,.4)",
            transform: `rotate(${leaf.rotate}deg)`,
          }}
        />
      ))}
    </>
  );
}

function BellCord({ scale }: { scale: number }) {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        left: "50%",
        top: "94%",
        width: 1.5 * scale,
        height: 14 * scale,
        background: "rgba(255,255,255,.5)",
        transform: "translateX(-50%)",
      }}
    />
  );
}

function DotGlow() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-[-40%] rounded-full"
      style={{
        background: "radial-gradient(circle, color-mix(in oklab, var(--e2) 60%, transparent), transparent 70%)",
        animation: "nimbusSparkle 2.4s ease-in-out infinite",
      }}
    />
  );
}
