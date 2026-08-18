"use client";

/**
 * Music player card — ported from the approved mockup (Mindlens Chat.dc.html,
 * "Music player") and wired to the real `music` payload the backend sends
 * (streaming.py::_extract_music_payload). Renders only when the music agent
 * actually ran this turn — the payload being null means no card, not an
 * empty one.
 *
 * Tracks come from Apple's iTunes Search API (music_agent.py) — no
 * connection step, no OAuth. Most tracks carry a real 30-second preview
 * clip, which this card now actually plays via a plain <audio> element.
 * When a track has no preview (iTunes doesn't guarantee one), it falls back
 * to opening the track's Apple Music page; only if neither exists does it
 * say so honestly rather than rendering a button that does nothing.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { MusicPayload } from "@/lib/types";

export function MusicCard({ music }: { music: MusicPayload }) {
  const track = music.tracks[0];
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // A new turn can bring a new track while the old preview is still
  // playing — stop it rather than leave two clips implicitly stacked.
  useEffect(() => {
    setPlaying(false);
    audioRef.current?.pause();
  }, [track?.preview_url]);

  const wave = useMemo(
    () =>
      Array.from({ length: 42 }, (_, i) => {
        const played = i / 42 < 0.28;
        const h = 6 + Math.round(24 * Math.abs(Math.sin(i * 0.55) * Math.cos(i * 0.21)));
        return { h, played };
      }),
    [],
  );

  const eyebrow = music.emotion ? `Because you're ${music.emotion}` : "For right now";
  const title = track?.name ?? "Something to listen to";
  const subtitle = track?.artist ?? "";

  const togglePlayback = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
    } else {
      audio.play().catch(() => setPlaying(false));
    }
    setPlaying((p) => !p);
  };

  return (
    <div
      className="relative flex flex-col overflow-hidden rounded-[22px] border p-4"
      style={{
        background: "var(--ml-panel-legible)",
        borderColor: "var(--ml-hairline)",
      }}
    >
      {track?.preview_url && (
        <audio
          ref={audioRef}
          src={track.preview_url}
          onEnded={() => setPlaying(false)}
          preload="none"
        />
      )}
      <div className="flex items-start gap-3">
        <div
          className="relative size-[70px] shrink-0 overflow-hidden rounded-2xl"
          style={{
            background:
              "linear-gradient(150deg, color-mix(in oklab, var(--e2) 88%, white), color-mix(in oklab, var(--e1) 85%, black 6%))",
            boxShadow: "0 12px 26px -14px var(--e1)",
            transition: "background 1.6s",
          }}
        >
          <span
            aria-hidden="true"
            className="absolute -left-[30%] -top-[40%] aspect-square w-[90%] rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(255,255,255,.55), transparent 65%)",
              filter: "blur(10px)",
            }}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {/* A plain note, not a branded mark — this card has no
              * partnership with any platform to imply. */}
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="shrink-0"
              style={{ color: "var(--e1)" }}
              aria-hidden="true"
            >
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
            <p className="ml-eyebrow m-0 text-[9px]">{eyebrow}</p>
          </div>
          <p
            className="m-0 mt-1 truncate font-[family-name:var(--font-newsreader)] text-[21px] font-light tracking-[-.01em]"
            style={{ color: "var(--ml-ink)" }}
          >
            {title}
          </p>
          {subtitle && (
            <p className="m-0 mt-0.5 truncate text-[11.5px]" style={{ color: "var(--ml-muted)" }}>
              {subtitle}
            </p>
          )}
        </div>
      </div>

      {music.message && (
        <p className="m-0 mt-3 text-[12.5px] leading-[1.55]" style={{ color: "var(--ml-muted)", textWrap: "pretty" }}>
          {music.message}
        </p>
      )}

      <div aria-hidden="true" className="mb-1.5 mt-4 flex h-8 items-center gap-[2.5px]">
        {wave.map((bar, i) => (
          <span
            key={i}
            className="flex-1 rounded-[2px]"
            style={{
              height: bar.h,
              background: bar.played
                ? "var(--e1)"
                : "color-mix(in oklab, var(--ml-ink) 16%, transparent)",
            }}
          />
        ))}
      </div>

      {music.tracks.length > 1 && (
        <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
          {music.tracks.slice(1, 4).map((t, i) => (
            <li key={`${t.name}-${i}`} className="flex items-baseline gap-2 text-[11.5px]">
              <span className="truncate" style={{ color: "var(--ml-muted)" }}>
                {t.name}
              </span>
              {t.artist && (
                <span className="shrink-0" style={{ color: "var(--ml-faint)" }}>
                  {t.artist}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex items-center justify-center gap-4 pt-4">
        {track?.preview_url ? (
          <button
            type="button"
            onClick={togglePlayback}
            aria-label={playing ? `Pause ${title}` : `Play ${title}`}
            className="grid size-11 place-items-center rounded-full transition-transform hover:scale-105"
            style={{
              background: "linear-gradient(135deg, var(--e1), var(--e2))",
              color: "#fffdf8",
              boxShadow: "0 10px 22px -12px var(--e1)",
              transition: "background 1.6s, transform .2s",
            }}
          >
            {playing ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M7 4v16l13-8Z" />
              </svg>
            )}
          </button>
        ) : track?.track_url ? (
          <a
            href={track.track_url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open ${title} on Apple Music`}
            className="rounded-[99px] border px-3.5 py-2 text-[11.5px] transition-colors hover:border-[var(--ml-hairline-strong)]"
            style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-muted)" }}
          >
            Open on Apple Music
          </a>
        ) : (
          <span
            className="rounded-[99px] border px-3.5 py-2 text-[11.5px]"
            style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-faint)" }}
          >
            No preview available
          </span>
        )}
      </div>
    </div>
  );
}
