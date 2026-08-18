"use client";

/**
 * The music panel — the right rail, and now only that.
 *
 * It used to be a permanent "inspector" holding a companion hero, a 12-swatch
 * emotion picker, a 24h mood strip and a list of what we'd worked on. Three
 * of those are gone:
 *
 * - The emotion picker was never a mood logger. DESIGN.md §5.3 said so
 *   outright and open item #4 required it be "gated or converted to a
 *   'correct the read' feedback control before production". Tapping it
 *   repainted the room but changed nothing the model believed, which is the
 *   most misleading kind of control this app can ship.
 * - Today's weather moved to Progress, which already fetches the same mood
 *   logs for its 7-day chart.
 * - What we worked on was deleted. It mapped agent names through a 13-entry
 *   label table that silently dropped any agent missing from it and listed
 *   several — cbt, dbt, act, mi, narrative, planning — that are not agents
 *   and never run. The reasoning trail reports the real per-turn agent list.
 *
 * What's left has one job: hold the track when there is one. The panel is
 * mounted only when a music payload exists, so it is not a panel the user
 * has to close.
 */

import { Lock } from "lucide-react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import type { EmotionReading } from "@/lib/emotion";
import type { MusicPayload } from "@/lib/types";
import { MusicCard } from "./music-card";

export function Inspector({
  reading,
  music,
  companionId,
  companionName,
}: {
  reading: EmotionReading;
  music: MusicPayload;
  companionId: string;
  companionName: string;
}) {
  return (
    <aside
      className="ml-glass flex h-full w-[336px] shrink-0 flex-col gap-4 overflow-y-auto rounded-[var(--r-22)] p-4"
      aria-label="Music"
    >
      <CompanionCard reading={reading} companionId={companionId} companionName={companionName} />

      <MusicCard music={music} />

      <p
        className="mt-auto flex items-start gap-2 pt-2 text-[10.5px] leading-[1.6]"
        style={{ color: "var(--ml-faint)" }}
      >
        <Lock size={12} strokeWidth={1.7} className="mt-[1px] shrink-0" />
        Everything here stays yours. The people, topics and coping strategies
        Mindlens picks up show up in Memory, where you can delete them.
      </p>
    </aside>
  );
}

function CompanionCard({
  reading,
  companionId,
  companionName,
}: {
  reading: EmotionReading;
  companionId: string;
  companionName: string;
}) {
  return (
    <div
      className="rounded-[var(--r-18)] p-4 text-center"
      style={{
        background:
          "linear-gradient(160deg, color-mix(in oklab, var(--e1) 13%, transparent), transparent)",
        border: "1px solid var(--ml-hairline)",
      }}
    >
      <div className="grid place-items-center">
        <CompanionAvatar companionId={companionId} size={92} withShadow />
      </div>
      <p
        className="ml-display mt-2 text-[15.5px] leading-[1.5]"
        style={{ color: "var(--ml-ink)" }}
      >
        {reading.resting ? (
          <>
            {companionName} is <em>here</em> when you are
          </>
        ) : (
          <>
            {companionName} is{" "}
            <em style={{ color: "color-mix(in oklab, var(--e1) 75%, var(--ml-ink))" }}>
              {reading.state.name.toLowerCase()}
            </em>{" "}
            with you
          </>
        )}
      </p>
    </div>
  );
}
