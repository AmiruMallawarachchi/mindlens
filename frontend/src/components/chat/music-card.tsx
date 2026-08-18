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
 * clip. When a track has no preview (iTunes doesn't guarantee one), it falls
 * back to opening the track's Apple Music page; only if neither exists does
 * it say so honestly rather than rendering a button that does nothing.
 *
 * Playback is AI Elements' AudioPlayer (media-chrome) rather than a
 * hand-rolled play button. That replaced a decorative 42-bar "waveform"
 * which hardcoded 28% of its bars as played and never moved — a progress
 * indicator that showed a position unrelated to the audio, on a card whose
 * whole job is playing it. A real scrubber, elapsed time and duration are
 * both more useful and the only version that isn't quietly lying.
 */

import type { MusicPayload } from "@/lib/types";
import {
  AudioPlayer,
  AudioPlayerControlBar,
  AudioPlayerDurationDisplay,
  AudioPlayerElement,
  AudioPlayerMuteButton,
  AudioPlayerPlayButton,
  AudioPlayerTimeDisplay,
  AudioPlayerTimeRange,
} from "@/components/ai-elements/audio-player";

export function MusicCard({ music }: { music: MusicPayload }) {
  const track = music.tracks[0];

  const eyebrow = music.emotion ? `Because you're ${music.emotion}` : "For right now";
  const title = track?.name ?? "Something to listen to";
  const subtitle = track?.artist ?? "";

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

      <div className="mt-auto pt-4">
        {track?.preview_url ? (
          <AudioPlayer
            className="w-full overflow-hidden rounded-[14px] border"
            style={{
              borderColor: "var(--ml-hairline-strong)",
              background: "var(--ml-panel)",
              // media-chrome themes off its own custom properties; point the
              // ones that carry colour at the emotion tokens so the player
              // crossfades with the room instead of sitting outside it.
              "--media-primary-color": "var(--e1)",
              "--media-range-bar-color": "var(--e1)",
              "--media-text-color": "var(--ml-ink)",
              "--media-icon-color": "var(--ml-ink)",
              "--media-control-hover-background":
                "color-mix(in oklab, var(--ml-ink) 6%, transparent)",
            } as React.CSSProperties}
          >
            <AudioPlayerElement src={track.preview_url} preload="none" />
            <AudioPlayerControlBar className="flex w-full items-center gap-1 px-1.5 py-1">
              <AudioPlayerPlayButton aria-label={`Play ${title}`} />
              <AudioPlayerTimeDisplay />
              <AudioPlayerTimeRange className="min-w-0 flex-1" />
              <AudioPlayerDurationDisplay />
              <AudioPlayerMuteButton />
            </AudioPlayerControlBar>
          </AudioPlayer>
        ) : track?.track_url ? (
          <div className="flex justify-center">
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
          </div>
        ) : (
          <div className="flex justify-center">
            <span
              className="rounded-[99px] border px-3.5 py-2 text-[11.5px]"
              style={{ borderColor: "var(--ml-hairline-strong)", color: "var(--ml-faint)" }}
            >
              No preview available
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
