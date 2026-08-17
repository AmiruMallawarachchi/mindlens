"use client";

/**
 * Inspector — design.md §4.1, fixed 336px, collapsible, hidden below 981px.
 *
 * Companion hero card, the emotion picker, today's weather, what we worked on,
 * and the privacy note pinned to the bottom.
 */

import { useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { fetchMoodLogs } from "@/lib/api";
import {
  EMOTION_ORDER,
  EMOTION_STATES,
  resolveEmotion,
  type EmotionId,
  type EmotionReading,
} from "@/lib/emotion";
import { PREVIEW_MODE } from "@/lib/preview";
import type { ChatMessage, MoodLogEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Inspector({
  reading,
  messages,
  onPickEmotion,
  manualEmotion,
  companionId,
  companionName,
}: {
  reading: EmotionReading;
  messages: ChatMessage[];
  onPickEmotion: (id: EmotionId | null) => void;
  manualEmotion: EmotionId | null;
  companionId: string;
  companionName: string;
}) {
  return (
    <aside
      className="ml-glass flex h-full w-[336px] shrink-0 flex-col gap-4 overflow-y-auto rounded-[var(--r-22)] p-4"
      aria-label="Session inspector"
    >
      <CompanionCard reading={reading} companionId={companionId} companionName={companionName} />
      <EmotionPicker
        active={manualEmotion ?? reading.state.id}
        manual={manualEmotion}
        onPick={onPickEmotion}
      />
      <TodaysWeather reading={reading} />
      <WorkedOn messages={messages} />

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
      className="flex flex-col items-center rounded-[var(--r-18)] p-4 text-center"
      style={{
        background:
          "linear-gradient(160deg, color-mix(in oklab, var(--e1) 14%, transparent), transparent)",
        border: "1px solid var(--ml-hairline)",
      }}
    >
      <CompanionAvatar companionId={companionId} size={112} mood={reading.state.id} withShadow />
      <p className="ml-display mt-2 text-[16px]" style={{ color: "var(--ml-ink)" }}>
        {reading.resting ? (
          <>
            {companionName} is <em className="italic">here</em> when you are
          </>
        ) : (
          <>
            {companionName} is holding{" "}
            <em className="italic">{reading.state.name.toLowerCase()}</em> with
            you
          </>
        )}
      </p>
    </div>
  );
}

/** §4.1 — "The field — tap to feel it". This is also the only route to the
 * states the classifier can't produce, so a user can name a feeling the model
 * has no label for. */
function EmotionPicker({
  active,
  manual,
  onPick,
}: {
  active: EmotionId;
  manual: EmotionId | null;
  onPick: (id: EmotionId | null) => void;
}) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <p className="ml-eyebrow">The field — tap to feel it</p>
        {manual && (
          <button
            type="button"
            onClick={() => onPick(null)}
            className="ml-eyebrow transition-opacity hover:opacity-70"
            style={{ color: "var(--e1)" }}
          >
            reset
          </button>
        )}
      </div>
      <div className="grid grid-cols-6 gap-1.5">
        {EMOTION_ORDER.map((id) => {
          const state = EMOTION_STATES[id];
          const isActive = active === id;
          return (
            <button
              key={id}
              type="button"
              title={state.name}
              aria-label={state.name}
              aria-pressed={isActive}
              onClick={() => onPick(id === manual ? null : id)}
              className={cn(
                "h-9 rounded-[var(--r-7)] transition-transform hover:scale-110",
                isActive && "scale-110",
              )}
              style={{
                background: `linear-gradient(140deg, ${state.c1}, ${state.c2})`,
                border: isActive
                  ? "1.5px solid var(--ml-ink)"
                  : "1px solid transparent",
                opacity: isActive ? 1 : 0.62,
              }}
            />
          );
        })}
      </div>
    </section>
  );
}

/** Today's weather — the real mood log for the last 24h. Renders an empty
 * state rather than a placeholder shape when there's nothing logged. */
function TodaysWeather({ reading }: { reading: EmotionReading }) {
  const [moods, setMoods] = useState<MoodLogEntry[] | null>(null);

  useEffect(() => {
    if (PREVIEW_MODE) return;
    let cancelled = false;
    fetchMoodLogs(40)
      .then((entries) => {
        if (!cancelled) setMoods(entries);
      })
      .catch(() => {
        if (!cancelled) setMoods([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const today = useMemo(() => {
    if (!moods) return [];
    const cutoff = Date.now() - 86_400_000;
    return moods
      .filter((m) => new Date(m.timestamp).getTime() >= cutoff)
      .slice(-24);
  }, [moods]);

  return (
    <section>
      <p className="ml-eyebrow mb-2">Today&rsquo;s weather</p>
      <div
        className="rounded-[var(--r-13)] p-3"
        style={{ border: "1px solid var(--ml-hairline)" }}
      >
        {today.length === 0 ? (
          <p className="text-[11.5px]" style={{ color: "var(--ml-faint)" }}>
            {PREVIEW_MODE
              ? "Mood history needs the backend running."
              : "Nothing logged yet today."}
          </p>
        ) : (
          <div className="flex h-10 items-end gap-[3px]">
            {today.map((entry, index) => {
              const state =
                resolveEmotion({
                  surface_emotion: entry.surface_emotion ?? undefined,
                  distress_level: entry.distress_level ?? undefined,
                }).state;
              const height = 20 + 80 * (entry.distress_level ?? 0.4);
              return (
                <span
                  key={`${entry.timestamp}-${index}`}
                  className="flex-1 rounded-[2px]"
                  style={{
                    height: `${height}%`,
                    background: state.c1,
                    opacity: 0.8,
                  }}
                  title={`${state.name} · ${new Date(entry.timestamp).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`}
                />
              );
            })}
          </div>
        )}
        {reading.blend && (
          <p className="mt-2 text-[11px]" style={{ color: "var(--e-blend)" }}>
            Right now: {reading.blend.name.toLowerCase()}
          </p>
        )}
      </div>
    </section>
  );
}

/** Derived from the agents the pipeline actually reported for this session —
 * not a curated list. */
const AGENT_LABELS: Record<string, string> = {
  empathy: "Sitting with it",
  cbt: "Looking at the thought",
  dbt: "Steadying the intensity",
  act: "Making room for it",
  mindfulness: "Slowing down",
  mi: "Finding what you want",
  narrative: "Retelling it",
  music: "Something to listen to",
  planning: "A next step",
  progress: "How this compares",
  distortion: "The shape of the thinking",
  memory: "Worth remembering",
  checkin: "Following up",
};

function WorkedOn({ messages }: { messages: ChatMessage[] }) {
  const worked = useMemo(() => {
    const seen = new Set<string>();
    for (const message of messages) {
      for (const agent of message.agentsUsed ?? []) {
        const label = AGENT_LABELS[agent.replace(/_agent$/, "")];
        if (label) seen.add(label);
      }
    }
    return [...seen];
  }, [messages]);

  return (
    <section>
      <p className="ml-eyebrow mb-2">What we worked on</p>
      {worked.length === 0 ? (
        <p className="text-[11.5px]" style={{ color: "var(--ml-faint)" }}>
          Nothing yet — this fills in as you talk.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {worked.map((label) => (
            <li
              key={label}
              className="flex items-center gap-2 text-[12px]"
              style={{ color: "var(--ml-muted)" }}
            >
              <span
                aria-hidden="true"
                className="size-[5px] shrink-0 rounded-full"
                style={{ background: "var(--e1)" }}
              />
              {label}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
