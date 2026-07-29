"use client";

/**
 * Progress — design.md §4.2: "Your rhythm, not a score". Three metric
 * cards, a real 7-day emotion-coloured bar chart from mood logs, and the
 * weekly insight card backed by GET /api/v1/dashboard/insight (only
 * available at >= 7 sessions — the honest placeholder shows the count
 * needed otherwise, never a fabricated insight).
 */

import { useEffect, useMemo, useState } from "react";
import { fetchMoodLogs, fetchProgressInsight } from "@/lib/api";
import { resolveEmotion } from "@/lib/emotion";
import type { MoodLogEntry, ProgressInsight } from "@/lib/types";

function distressToMoodScore(distress: number): number {
  return Math.round((1 - distress) * 100) / 10;
}

const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

export function ProgressPage() {
  const [moods, setMoods] = useState<MoodLogEntry[] | null>(null);
  const [insight, setInsight] = useState<ProgressInsight | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMoodLogs(90), fetchProgressInsight()])
      .then(([moodData, insightData]) => {
        if (cancelled) return;
        setMoods(moodData);
        setInsight(insightData);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Couldn't load your progress right now.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const averageMood = useMemo(() => {
    if (!moods || moods.length === 0) return null;
    const withDistress = moods.filter((m) => typeof m.distress_level === "number");
    if (withDistress.length === 0) return null;
    const avgDistress =
      withDistress.reduce((sum, m) => sum + (m.distress_level ?? 0), 0) / withDistress.length;
    return distressToMoodScore(avgDistress);
  }, [moods]);

  const distressTrend = useMemo(() => {
    if (!moods || moods.length < 2) return null;
    const recent = moods.slice(0, Math.min(7, moods.length));
    const older = moods.slice(Math.min(7, moods.length), Math.min(14, moods.length));
    if (older.length === 0) return null;
    const avg = (arr: MoodLogEntry[]) =>
      arr.reduce((sum, m) => sum + (m.distress_level ?? 0.5), 0) / arr.length;
    const delta = avg(recent) - avg(older);
    if (Math.abs(delta) < 0.03) return "steady";
    return delta < 0 ? "easing" : "rising";
  }, [moods]);

  const days = useMemo(() => {
    const today = new Date();
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today);
      d.setDate(today.getDate() - (6 - i));
      d.setHours(0, 0, 0, 0);
      return d;
    });
  }, []);

  const dayScores = useMemo(() => {
    if (!moods) return days.map(() => null);
    return days.map((day) => {
      const next = new Date(day);
      next.setDate(day.getDate() + 1);
      const entries = moods.filter((m) => {
        const t = new Date(m.timestamp).getTime();
        return t >= day.getTime() && t < next.getTime() && typeof m.distress_level === "number";
      });
      if (entries.length === 0) return null;
      const avgDistress = entries.reduce((s, m) => s + (m.distress_level ?? 0.5), 0) / entries.length;
      const dominant = entries[entries.length - 1];
      return { score: 1 - avgDistress, emotion: dominant.surface_emotion };
    });
  }, [moods, days]);

  if (loadError) {
    return <EmptyState text={loadError} />;
  }

  return (
    <div className="flex flex-col gap-9">
      <div>
        <p className="ml-eyebrow">Your rhythm, not a score</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard
          label="Average mood"
          value={averageMood !== null ? averageMood.toFixed(1) : "—"}
          suffix={averageMood !== null ? "/ 10" : undefined}
        />
        <MetricCard label="Sessions logged" value={moods ? String(new Set(moods.map((m) => m.timestamp.slice(0, 10))).size) : "—"} />
        <MetricCard
          label="Distress trend"
          value={distressTrend ?? "—"}
          capitalize
        />
      </div>

      <section>
        <p className="ml-eyebrow mb-3">Last 7 days</p>
        <div
          className="rounded-[var(--r-18)] p-5"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          <div className="flex h-[120px] items-end gap-3">
            {dayScores.map((entry, i) => {
              const state = entry ? resolveEmotion({ surface_emotion: entry.emotion ?? undefined }).state : null;
              const heightPct = entry ? Math.max(8, entry.score * 100) : 0;
              return (
                <div key={i} className="flex flex-1 flex-col items-center gap-2">
                  <div className="flex h-full w-full items-end">
                    {entry ? (
                      <div
                        className="w-full rounded-[6px]"
                        style={{
                          height: `${heightPct}%`,
                          background: `linear-gradient(180deg, ${state?.c1}, ${state?.c2})`,
                          opacity: 0.85,
                        }}
                        title={state?.name}
                      />
                    ) : (
                      <div className="w-full rounded-[6px]" style={{ height: "4px", background: "var(--ml-hairline)" }} />
                    )}
                  </div>
                  <span className="ml-eyebrow">{WEEKDAY_LABELS[days[i].getDay()]}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section>
        <p className="ml-eyebrow mb-3">Weekly insight</p>
        {insight === null ? (
          <div className="rounded-[var(--r-18)] p-5" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
          </div>
        ) : !insight.available ? (
          <div className="rounded-[var(--r-18)] p-5" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
            <p className="text-[13.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
              {insight.sessions_needed ?? 7} more {insight.sessions_needed === 1 ? "session" : "sessions"} to unlock your first weekly insight.
            </p>
          </div>
        ) : insight.insight ? (
          <div
            className="rounded-[var(--r-18)] p-6"
            style={{
              background: "linear-gradient(160deg, color-mix(in oklab, var(--e1) 12%, transparent), transparent)",
              border: "1px solid var(--ml-hairline)",
            }}
          >
            <p className="ml-display text-[16px] leading-[1.65]" style={{ color: "var(--ml-ink)", textWrap: "pretty" }}>
              {insight.insight}
            </p>
          </div>
        ) : (
          <div className="rounded-[var(--r-18)] p-5" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>
              {insight.error ?? "Couldn't generate an insight right now."}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  suffix,
  capitalize = false,
}: {
  label: string;
  value: string;
  suffix?: string;
  capitalize?: boolean;
}) {
  return (
    <div
      className="rounded-[var(--r-18)] p-5"
      style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
    >
      <p className="ml-eyebrow mb-2">{label}</p>
      <p
        className="ml-num ml-display text-[32px]"
        style={{ color: "var(--ml-ink)", textTransform: capitalize ? "capitalize" : undefined }}
      >
        {value}
        {suffix && (
          <span className="ml-2 text-[15px]" style={{ color: "var(--ml-faint)" }}>
            {suffix}
          </span>
        )}
      </p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-20 text-center">
      <p className="text-[14px]" style={{ color: "var(--ml-muted)" }}>{text}</p>
    </div>
  );
}
