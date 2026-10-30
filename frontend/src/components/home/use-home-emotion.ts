import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "motion/react";
import { EMOTION_ORDER, EMOTION_STATES, emotionCssVars, type EmotionId } from "@/lib/emotion";
import { WARM } from "./home-copy";

export function useHomeEmotion() {
  const [activeId, setActiveId] = useState<EmotionId | null>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (reduceMotion) return;
    const id = window.setInterval(() => {
      setActiveId((current) => {
        const idx = current ? EMOTION_ORDER.indexOf(current) : -1;
        return EMOTION_ORDER[(idx + 1) % EMOTION_ORDER.length];
      });
    }, 5000);
    return () => window.clearInterval(id);
  }, [reduceMotion]);

  const active = activeId ? EMOTION_STATES[activeId] : null;
  const rootStyle = useMemo(() => {
    if (active) {
      return emotionCssVars({
        state: active,
        blend: null,
        coreState: null,
        intensity: 1,
        confidence: null,
        subs: active.subs,
        resting: false,
      });
    }
    return {
      "--e1": WARM.c1,
      "--e2": WARM.c2,
      "--e3": WARM.c3,
      "--e-blend": WARM.c2,
      "--intensity": "1",
    };
  }, [active]);

  return {
    activeId,
    setActiveId,
    reduceMotion,
    activeName: active?.name ?? WARM.name,
    activeSubs: active?.subs ?? WARM.subs,
    rootStyle,
  };
}
