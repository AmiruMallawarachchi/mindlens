/**
 * The Mindlens brand mark — your actual logo (frontend/public/mindlens-logo.png),
 * not a code-drawn reinterpretation. An earlier build invented a "living dot"
 * wordmark from an older text-only design doc before the real logo file was
 * available; that's gone now that we have the real asset.
 *
 * Day/night handled the same way the approved mockups do it: a fixed ink
 * icon, inverted via CSS filter for night rather than recoloured per emotion.
 */

import { cn } from "@/lib/utils";

const LOGO_ASPECT = 580 / 546;

/** Icon only. */
export function MindlensMark({
  size = 28,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- small fixed icon, next/image adds no benefit here
    <img
      src="/mindlens-logo.png"
      alt="Mindlens"
      width={Math.round(size * LOGO_ASPECT)}
      height={size}
      className={cn("shrink-0 select-none", className)}
      style={{ height: size, width: "auto", filter: "var(--ml-logo-filter, none)" }}
      draggable={false}
    />
  );
}

/** Icon + wordmark text, matching the nav/sidebar/footer lockup in the
 * approved mockups. `mood` is accepted but unused — the real logo doesn't
 * recolour with emotion; kept so call sites that pass it don't need edits. */
export function Wordmark({
  size = 21,
  className,
}: {
  mood?: string;
  size?: number;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <MindlensMark size={size * 1.05} />
      <span
        className="font-semibold leading-none"
        style={{ fontSize: size * 0.72, letterSpacing: "-0.02em", color: "var(--ml-ink)" }}
      >
        Mindlens
      </span>
    </span>
  );
}
