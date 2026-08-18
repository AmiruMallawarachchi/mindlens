"use client";

/**
 * Progress — design.md §4.2: "Your rhythm, not a score". Three metric
 * cards, a real 7-day emotion-coloured bar chart from mood logs, and the
 * weekly insight card backed by GET /api/v1/dashboard/insight (only
 * available at >= 7 sessions — the honest placeholder shows the count
 * needed otherwise, never a fabricated insight).
 */

import { useEffect, useMemo, useState } from "react";
import { Heart, MessageCircle, TrendingDown, TrendingUp } from "lucide-react";
import { fetchDashboardSummary, fetchMoodLogs, fetchProgressInsight } from "@/lib/api";
import { resolveEmotion } from "@/lib/emotion";
import type { MoodLogEntry, ProgressInsight } from "@/lib/types";

function distressToMoodScore(distress: number): number {
  return Math.round((1 - distress) * 100) / 10;
}

const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

export function ProgressPage() {
  const [moods, setMoods] = useState<MoodLogEntry[] | null>(null);
  const [moodsError, setMoodsError] = useState<string | null>(null);
  const [insight, setInsight] = useState<ProgressInsight | null>(null);
  const [insightError, setInsightError] = useState<string | null>(null);
  const [sessionCount, setSessionCount] = useState<number | null>(null);

  // Two independent data sources — a failure in one (e.g. the insight
  // endpoint's occasional LLM call timing out) must not blank out mood data
  // that loaded fine, and vice versa. Promise.all() previously coupled them:
  // either rejecting left both metric cards and the 7-day bars permanently
  // stuck showing nothing, even when the mood-log fetch had actually
  // succeeded.
  useEffect(() => {
    let cancelled = false;
    fetchMoodLogs(90)
      .then((data) => !cancelled && setMoods(data))
      .catch(() => !cancelled && setMoodsError("Couldn't load your mood history."));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchProgressInsight()
      .then((data) => !cancelled && setInsight(data))
      .catch(() => !cancelled && setInsightError("Couldn't load your weekly insight."));
    return () => {
      cancelled = true;
    };
  }, []);

  // The real session count (dashboard.py: db.sessions.count_documents),
  // not a proxy — this card used to count distinct mood-log dates, which
  // undercounts multiple sessions on the same day and is a different number
  // from what the >=7-session insight gate actually checks.
  useEffect(() => {
    let cancelled = false;
    fetchDashboardSummary()
      .then((data) => !cancelled && setSessionCount(data.session_count))
      .catch(() => {
        // Silent — the card just falls back to "—"; a third failing request
        // shouldn't add a third error banner to this page.
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
    const recentAvg = avg(recent);
    const olderAvg = avg(older);
    const percent = olderAvg === 0 ? 0 : Math.round(((recentAvg - olderAvg) / olderAvg) * 100);
    return { percent, direction: percent <= 0 ? ("down" as const) : ("up" as const) };
  }, [moods]);

  // Last 24h of logs, newest 24 points, for the Today strip below.
  const today = useMemo(() => {
    if (!moods) return [];
    const cutoff = Date.now() - 86_400_000;
    return moods
      .filter((m) => new Date(m.timestamp).getTime() >= cutoff)
      .slice(-24);
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

  return (
    <div className="flex flex-col gap-9">
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard
          icon={<Heart size={17} strokeWidth={1.7} style={{ color: "var(--e1)" }} />}
          label="Average mood"
          value={averageMood !== null ? averageMood.toFixed(1) : "—"}
          suffix={averageMood !== null ? "/ 10" : undefined}
          footnote={moods ? `From ${moods.length} check-ins` : undefined}
        />
        <MetricCard
          icon={<MessageCircle size={17} strokeWidth={1.7} style={{ color: "var(--e2)" }} />}
          label="Sessions so far"
          value={sessionCount !== null ? String(sessionCount) : "—"}
          footnote="Every conversation counts"
        />
        <MetricCard
          icon={
            distressTrend?.direction === "up" ? (
              <TrendingUp size={17} strokeWidth={1.7} style={{ color: "#e08a8a" }} />
            ) : (
              <TrendingDown size={17} strokeWidth={1.7} style={{ color: "#4fae6f" }} />
            )
          }
          label="Distress trend"
          value={distressTrend ? `${distressTrend.percent > 0 ? "+" : ""}${distressTrend.percent}` : "—"}
          suffix={distressTrend ? "%" : undefined}
          footnote={distressTrend ? "Compared to last week" : undefined}
        />
      </div>

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <div>
            <p className="ml-eyebrow">Emotional balance</p>
            <p className="ml-display mt-1 text-[16px]" style={{ color: "var(--ml-ink)" }}>Last 7 days</p>
          </div>
          {distressTrend && (
            <span className="ml-num text-[10.5px] uppercase tracking-[.12em]" style={{ color: "var(--e1)" }}>
              {distressTrend.direction === "down" ? "trending up" : "keep an eye on this"}
            </span>
          )}
        </div>
        <div
          className="rounded-[var(--r-18)] p-5"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          {moodsError && (
            <p className="mb-3 text-[12.5px]" style={{ color: "var(--ml-faint)" }}>
              {moodsError}
            </p>
          )}
          {/* items-stretch (not items-end) on the row is load-bearing: each
            * column below has no explicit height of its own, so it only
            * gets the row's 120px by being stretched to it. items-end here
            * meant every column shrank to its own content height instead —
            * h-full on the bar-wrapper below then resolved against that
            * collapsed 0px, so every bar's computed height was 0 regardless
            * of a correctly-computed heightPct. */}
          <div className="flex h-[120px] items-stretch gap-3">
            {dayScores.map((entry, i) => {
              const state = entry ? resolveEmotion({ surface_emotion: entry.emotion ?? undefined }).state : null;
              const heightPct = entry ? Math.max(8, entry.score * 100) : 0;
              return (
                <div key={i} className="flex flex-1 flex-col items-center gap-2">
                  {/* flex-1 (not h-full): fills whatever the column has left
                    * after the weekday label below, and — unlike h-full —
                    * that's a real, definite size the inner bar's height:%
                    * can resolve against. */}
                  <div className="flex min-h-0 flex-1 w-full items-end">
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

      {/* Moved here from the chat's right rail, which is a music panel now.
        * It reuses the mood logs this page already fetched rather than
        * issuing a second request for the same data. */}
      <section>
        <p className="ml-eyebrow mb-3">Today</p>
        <div
          className="rounded-[var(--r-18)] p-5"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
        >
          {moodsError ? (
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{moodsError}</p>
          ) : moods === null ? (
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
          ) : today.length === 0 ? (
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>
              Nothing logged yet today.
            </p>
          ) : (
            <div className="flex h-12 items-end gap-[3px]">
              {today.map((entry, index) => {
                const state = resolveEmotion({
                  surface_emotion: entry.surface_emotion ?? undefined,
                  distress_level: entry.distress_level ?? undefined,
                }).state;
                return (
                  <span
                    key={`${entry.timestamp}-${index}`}
                    className="flex-1 rounded-[2px]"
                    style={{
                      height: `${20 + 80 * (entry.distress_level ?? 0.4)}%`,
                      background: state.c1,
                      opacity: 0.8,
                    }}
                    title={`${state.name} · ${new Date(entry.timestamp).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`}
                  />
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section>
        <p className="ml-eyebrow mb-3">Weekly insight</p>
        {insightError ? (
          <div className="rounded-[var(--r-18)] p-5" style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}>
            <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{insightError}</p>
          </div>
        ) : insight === null ? (
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
  icon,
  label,
  value,
  suffix,
  footnote,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  suffix?: string;
  footnote?: string;
}) {
  return (
    <div
      className="rounded-[var(--r-18)] p-5"
      style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
    >
      {icon}
      <p className="ml-eyebrow mt-2.5 mb-1">{label}</p>
      <p className="ml-num ml-display text-[30px]" style={{ color: "var(--ml-ink)" }}>
        {value}
        {suffix && (
          <span className="ml-1.5 text-[15px]" style={{ color: "var(--ml-faint)" }}>
            {suffix}
          </span>
        )}
      </p>
      {footnote && (
        <p className="mt-1.5 text-[11px]" style={{ color: "var(--ml-faint)" }}>
          {footnote}
        </p>
      )}
    </div>
  );
}
