"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchDashboardSummary, fetchMoodLogs, fetchProgressInsight } from "@/lib/api";
import type { MoodLogEntry, ProgressInsight } from "@/lib/types";

function distressToMoodScore(distress: number): number {
  return Math.round((1 - distress) * 100) / 10;
}

export function useProgressPageData() {
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
  return {
    moods,
    moodsError,
    insight,
    insightError,
    sessionCount,
    averageMood,
    distressTrend,
    today,
    days,
    dayScores,
  };
}
