"use client";

/**
 * Music player card — ported from the approved mockup (Mindlens Chat.dc.html,
 * "Music player") and wired to the real `music` payload the backend now
 * sends (streaming.py::_extract_music_payload). Renders only when the music
 * agent actually ran this turn — the payload being null means no card, not
 * an empty one.
 *
 * The transport controls and waveform are presentational for now: actual
 * audio playback needs the Spotify MCP connection, which isn't wired
 * client-side yet. Tapping a track opens it on Spotify/YouTube instead —
 * a real action, not a dead button.
 */

import { useMemo } from "react";
import type { MusicPayload } from "@/lib/types";

export function MusicCard({ music }: { music: MusicPayload }) {
  const track = music.tracks[0];
  const trackUrl = track?.spotify_url || track?.youtube_url || null;

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
  const subtitle = track?.artist ?? (music.connect_prompt ? "Connect Spotify for the full picks" : "");

  return (
    <div
      className="relative flex flex-col overflow-hidden rounded-[22px] border p-4"
      style={{
        background: "var(--ml-panel-legible)",
        borderColor: "var(--ml-hairline)",
      }}
    >
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
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              className="shrink-0"
              style={{ color: "#1db954" }}
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M7.5 14.5c3-1 6.5-.8 9 .8M7 11c3.5-1.2 8-.8 10.5 1.2M7.5 7.8c4-1.3 9-.7 11.5 1.5" />
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
        {trackUrl ? (
          <a
            href={trackUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open ${title} ${track?.spotify_url ? "on Spotify" : "on YouTube"}`}
            className="grid size-11 place-items-center rounded-full transition-transform hover:scale-105"
            style={{
              background: "linear-gradient(135deg, var(--e1), var(--e2))",
              color: "#fffdf8",
              boxShadow: "0 10px 22px -12px var(--e1)",
              transition: "background 1.6s, transform .2s",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M7 4v16l13-8Z" />
            </svg>
          </a>
        ) : (
          <span
            className="rounded-[99px] border px-3.5 py-2 text-[11.5px]"
            style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-faint)" }}
          >
            Connect Spotify to play
          </span>
        )}
      </div>
    </div>
  );
}
