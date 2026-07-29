"use client";

/**
 * Nimbus — the Mindlens companion.
 *
 * Ported from the approved mockup (design project "Mindlens UI Mockups" →
 * Mindlens Chat.dc.html), which is the real source of truth here — an
 * earlier build attempted a 4-shape "cloud" from design.md's prose
 * description (§3) and got Nimbus's actual construction wrong. The real
 * Nimbus is a single blob: a radial-gradient circle whose `border-radius`
 * continuously morphs through organic shapes (`nimbusMorph`, tokens.css),
 * with two blinking eye-pills, a mouth drawn as a partial border arc, and
 * two soft blush blurs — all positioned with percentages of the blob's own
 * box, which is why the exact px values below (tuned for an 88px hero) scale
 * correctly at any size.
 *
 * The mockup itself only renders full per-emotion expression detail at the
 * ~88-112px inspector hero size; the 30px message avatar is just two
 * blinking dots, and mobile's 26-36px avatars are a plain blob. Below a
 * detail threshold, expression detail would be illegible anyway, so this
 * component follows the same graduated fidelity rather than forcing a full
 * face onto a 24px dot.
 */

import { useId } from "react";
import { motion, useReducedMotion, type Transition } from "motion/react";
import type { EmotionId } from "@/lib/emotion";
import { cn } from "@/lib/utils";

export type NimbusActivity = "idle" | "listening" | "thinking" | "sending";

export interface NimbusProps {
  mood?: EmotionId;
  activity?: NimbusActivity;
  size?: number;
  className?: string;
  /** The inspector hero renders eyes+mouth+blush; smaller placements don't. */
  withShadow?: boolean;
}

/** Verbatim from Mindlens Chat.dc.html's EXPRESSIONS table (tuned for an
 * 88px hero blob) — eyes narrow or widen, the mouth turns, per emotion. */
const EXPRESSIONS: Record<
  EmotionId,
  { eyeTop: number; eyeH: number; mouthTop: number; mouthW: number; mouthH: number; mouthRadius: string; blushTop: number }
> = {
  calm: { eyeTop: 38, eyeH: 3, mouthTop: 56, mouthW: 20, mouthH: 9, mouthRadius: "0 0 99px 99px", blushTop: 48 },
  hopeful: { eyeTop: 34, eyeH: 9, mouthTop: 56, mouthW: 22, mouthH: 11, mouthRadius: "0 0 99px 99px", blushTop: 48 },
  joyful: { eyeTop: 34, eyeH: 4, mouthTop: 54, mouthW: 26, mouthH: 14, mouthRadius: "0 0 99px 99px", blushTop: 46 },
  tender: { eyeTop: 36, eyeH: 4, mouthTop: 56, mouthW: 18, mouthH: 9, mouthRadius: "0 0 99px 99px", blushTop: 48 },
  balanced: { eyeTop: 36, eyeH: 8, mouthTop: 57, mouthW: 16, mouthH: 7, mouthRadius: "0 0 99px 99px", blushTop: 49 },
  anxious: { eyeTop: 33, eyeH: 12, mouthTop: 58, mouthW: 11, mouthH: 5, mouthRadius: "0 0 99px 99px", blushTop: 50 },
  low: { eyeTop: 39, eyeH: 6, mouthTop: 62, mouthW: 18, mouthH: 9, mouthRadius: "99px 99px 0 0", blushTop: 52 },
  grief: { eyeTop: 41, eyeH: 3, mouthTop: 63, mouthW: 14, mouthH: 8, mouthRadius: "99px 99px 0 0", blushTop: 53 },
  angry: { eyeTop: 35, eyeH: 7, mouthTop: 61, mouthW: 16, mouthH: 8, mouthRadius: "99px 99px 0 0", blushTop: 51 },
  envious: { eyeTop: 36, eyeH: 6, mouthTop: 60, mouthW: 13, mouthH: 6, mouthRadius: "99px 99px 0 0", blushTop: 50 },
  ashamed: { eyeTop: 42, eyeH: 3, mouthTop: 62, mouthW: 12, mouthH: 7, mouthRadius: "99px 99px 0 0", blushTop: 53 },
  flat: { eyeTop: 38, eyeH: 3, mouthTop: 59, mouthW: 16, mouthH: 2, mouthRadius: "0", blushTop: 50 },
};

/** The px values in EXPRESSIONS were tuned against this reference size. */
const REFERENCE_SIZE = 88;
/** Below this, a mouth/blush would be illegible — match the mockup's own
 * graduated fidelity rather than forcing full detail onto a tiny dot. */
const DETAIL_THRESHOLD = 60;
/** Below this, even the blinking eyes drop out (mobile's plain blob). */
const EYES_THRESHOLD = 24;

const SPRING: Transition = { type: "spring", stiffness: 140, damping: 16 };

export function Nimbus({
  mood = "balanced",
  activity = "idle",
  size = 88,
  className,
  withShadow = false,
}: NimbusProps) {
  const uid = useId().replace(/:/g, "");
  const reduceMotion = useReducedMotion();
  const expr = EXPRESSIONS[mood];
  const scale = size / REFERENCE_SIZE;

  const showFace = size >= DETAIL_THRESHOLD;
  const showEyes = size >= EYES_THRESHOLD;

  // Activity layers on top of the mockup's baseline float/morph rather than
  // replacing it — send squishes, listening leans, thinking pulses faster.
  const activityAnimate = (() => {
    if (reduceMotion) return {};
    switch (activity) {
      case "sending":
        return { scaleX: 1.08, scaleY: 0.92 };
      case "listening":
        return { rotate: -4, y: 2 };
      default:
        return { rotate: 0, y: 0, scaleX: 1, scaleY: 1 };
    }
  })();
  const activityTransition: Transition =
    activity === "sending" || activity === "listening" ? SPRING : { duration: 0.4 };

  const morphDuration = activity === "thinking" ? 6 : 9;
  const floatDuration = activity === "thinking" ? 3 : 5;

  return (
    <motion.div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      animate={activityAnimate}
      transition={activityTransition}
    >
      <motion.div
        aria-label={`Nimbus, your companion, feeling ${mood}`}
        role="img"
        className="absolute inset-0"
        style={{
          background: `radial-gradient(circle at 34% 26%, color-mix(in oklab, var(--e2) 82%, white), var(--e1) 75%)`,
          boxShadow: withShadow
            ? `0 ${Math.round(18 * scale)}px ${Math.round(40 * scale)}px -${Math.round(12 * scale)}px var(--e1), inset 0 -${Math.round(8 * scale)}px ${Math.round(18 * scale)}px -${Math.round(8 * scale)}px rgba(0,0,0,.18)`
            : `0 ${Math.max(4, Math.round(6 * scale))}px ${Math.max(10, Math.round(16 * scale))}px -${Math.max(3, Math.round(6 * scale))}px var(--e1)`,
          transition: "background 1.6s, box-shadow 1.6s",
        }}
        animate={
          reduceMotion
            ? undefined
            : {
                borderRadius: [
                  "48% 52% 55% 45% / 52% 48% 52% 48%",
                  "55% 45% 48% 52% / 45% 55% 45% 55%",
                  "45% 55% 52% 48% / 55% 45% 55% 45%",
                  "48% 52% 55% 45% / 52% 48% 52% 48%",
                ],
                y: [0, -5 * scale, 0],
              }
        }
        transition={
          reduceMotion
            ? undefined
            : {
                borderRadius: { duration: morphDuration, repeat: Infinity, ease: "easeInOut" },
                y: { duration: floatDuration, repeat: Infinity, ease: "easeInOut" },
              }
        }
      >
        {showEyes && (
          <NimbusEyes uid={uid} scale={scale} expr={showFace ? expr : null} reduceMotion={!!reduceMotion} />
        )}
        {showFace && <NimbusMouthAndBlush scale={scale} expr={expr} />}
      </motion.div>

      {withShadow && !reduceMotion && (
        <>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 rounded-full"
            style={{
              border: "1px solid color-mix(in oklab, var(--e1) 55%, transparent)",
              animation: "nimbusHalo 4.5s ease-in-out infinite",
            }}
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute rounded-full"
            style={{
              right: size * 0.05,
              top: size * 0.07,
              width: size * 0.1,
              height: size * 0.1,
              background: "radial-gradient(circle, #fffdf8, transparent 65%)",
              animation: "nimbusSparkle 3.2s ease-in-out infinite",
            }}
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute rounded-full"
            style={{
              left: size * 0.09,
              bottom: size * 0.14,
              width: size * 0.07,
              height: size * 0.07,
              background: "radial-gradient(circle, #fffdf8, transparent 65%)",
              animation: "nimbusSparkle 3.8s ease-in-out .6s infinite",
            }}
          />
        </>
      )}
    </motion.div>
  );
}

function NimbusEyes({
  uid,
  scale,
  expr,
  reduceMotion,
}: {
  uid: string;
  scale: number;
  expr: (typeof EXPRESSIONS)[EmotionId] | null;
  reduceMotion: boolean;
}) {
  // The 30px message avatar has no per-emotion expression — just two fixed
  // blinking dots, matching the mockup exactly.
  const eyeTop = expr ? `${expr.eyeTop}%` : `${(12 / 30) * 100}%`;
  const eyeH = expr ? Math.max(2, expr.eyeH * scale) : 4.5 * scale;
  const eyeW = expr ? Math.max(2, 9 * scale) : 3.5 * scale;
  const leftPos = expr ? "24%" : `${(8 / 30) * 100}%`;
  const rightPos = expr ? "24%" : `${(8 / 30) * 100}%`;

  const blinkStyle = (delay: number): React.CSSProperties => ({
    position: "absolute",
    top: eyeTop,
    width: eyeW,
    height: eyeH,
    borderRadius: 99,
    background: "rgba(26,20,14,.78)",
    transformOrigin: "center",
    animation: reduceMotion ? undefined : `nimbusBlink 6s ease-in-out ${delay}s infinite`,
  });

  return (
    <>
      <span aria-hidden="true" style={{ ...blinkStyle(0), left: leftPos }} key={`${uid}-eye-l`} />
      <span aria-hidden="true" style={{ ...blinkStyle(0.1), right: rightPos }} key={`${uid}-eye-r`} />
    </>
  );
}

function NimbusMouthAndBlush({
  scale,
  expr,
}: {
  scale: number;
  expr: (typeof EXPRESSIONS)[EmotionId];
}) {
  return (
    <>
      {/* Mouth is a partial border arc: three sides transparent, only the
       * bottom traces the curve — the same trick the mockup uses. A downturn
       * (99px 99px 0 0) flips which edge is visible via the radius alone. */}
      <span
        aria-hidden="true"
        className="absolute -translate-x-1/2"
        style={{
          left: "50%",
          top: `${expr.mouthTop}%`,
          width: expr.mouthW * scale,
          height: expr.mouthH * scale,
          border: `${Math.max(1, 1.6 * scale)}px solid rgba(26,20,14,.6)`,
          borderTopColor: "transparent",
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderRadius: expr.mouthRadius,
          transition: "all .6s",
        }}
      />
      <span
        aria-hidden="true"
        className="absolute rounded-full"
        style={{
          left: "14%",
          top: `${expr.blushTop}%`,
          width: 11 * scale,
          height: 6 * scale,
          background: "rgba(255,255,255,.4)",
          filter: `blur(${2 * scale}px)`,
        }}
      />
      <span
        aria-hidden="true"
        className="absolute rounded-full"
        style={{
          right: "14%",
          top: `${expr.blushTop}%`,
          width: 11 * scale,
          height: 6 * scale,
          background: "rgba(255,255,255,.4)",
          filter: `blur(${2 * scale}px)`,
        }}
      />
    </>
  );
}
