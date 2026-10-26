"use client";

import { CompanionAvatar } from "@/components/companion/companion-avatar";
import type { EmotionId } from "@/lib/emotion";
import type { MindLensClient } from "@/lib/use-mindlens-client";
export function StatusPill({ status }: { status: MindLensClient["connectionStatus"] }) {
  const label =
    status === "open"
      ? "Live"
      : status === "connecting"
        ? "Connecting"
        : status === "reconnecting"
          ? "Reconnecting"
          : status === "closed"
            ? "Offline"
            : "Idle";

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[var(--r-pill)] px-2.5 py-1 text-[11px]"
      style={{
        border: "1px solid var(--ml-hairline)",
        color: "var(--ml-muted)",
      }}
    >
      <span
        aria-hidden="true"
        className="size-[6px] rounded-full"
        style={{
          background: status === "open" ? "var(--e1)" : "var(--ml-faint)",
          boxShadow: status === "open" ? "0 0 8px var(--e1)" : undefined,
        }}
      />
      {label}
    </span>
  );
}

export function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

export function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4" />
    </svg>
  );
}

export function EmptyRoom({
  mood,
  companionId,
  companionName,
}: {
  mood: EmotionId;
  companionId: string;
  companionName: string;
}) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <CompanionAvatar companionId={companionId} size={150} mood={mood} withShadow />
      <h2 className="ml-display text-[26px]" style={{ color: "var(--ml-ink)" }}>
        Come as you are.
      </h2>
      <p
        className="max-w-[38ch] text-[14px] leading-[1.65]"
        style={{ color: "var(--ml-muted)" }}
      >
        Start anywhere — the middle of the thought is fine. {companionName} will catch up.
      </p>
    </div>
  );
}

