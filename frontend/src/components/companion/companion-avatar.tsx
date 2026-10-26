"use client";

import type { Transition } from "motion/react";
import { useReducedMotion } from "motion/react";
import { getCompanion, type CompanionActivity, type CompanionId } from "@/lib/companions";
import { cn } from "@/lib/utils";
import type { EmotionId } from "@/lib/emotion";
import type { BodyProps } from "./companion-avatar-primitives";
import { EmberBody } from "./companion-ember";
import { FlitBody } from "./companion-flit";
import { FernBody } from "./companion-fern";
import { LensBody } from "./companion-lens";
import { TideBody } from "./companion-tide";

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
