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
 * clip. There is no album or full-length playback: Apple caps every
 * unauthenticated preview at ~30 seconds, and there is no Apple Music login
 * in this app to lift that. Stated here rather than left to look like a bug
 * when the clip ends.
 *
 * Every track iTunes returned is now actually playable, not just the first.
 * The list below the hero used to be plain <li> text with no onClick — a
 * pile of song names that looked like a track list but did nothing when
 * tapped. Clicking one now makes it the active player, with the same
 * three-state honesty per track (play / open on Apple Music / no preview)
 * rather than assuming every alternate has a preview because the first did.
 *
 * Playback is AI Elements' AudioPlayer (media-chrome) rather than a
 * hand-rolled play button. That replaced a decorative 42-bar "waveform"
 * which hardcoded 28% of its bars as played and never moved — a progress
 * indicator that showed a position unrelated to the audio, on a card whose
 * whole job is playing it. A real scrubber, elapsed time, duration and 5s
 * seek buttons (dragging a 6px bar to hit a specific second of a 30s clip
 * is fiddly) are the only version that isn't quietly lying.
 */

import { useEffect, useState } from "react";
import type { MusicPayload } from "@/lib/types";
import {
  AudioPlayer,
  AudioPlayerControlBar,
  AudioPlayerDurationDisplay,
  AudioPlayerElement,
  AudioPlayerMuteButton,
  AudioPlayerPlayButton,
  AudioPlayerSeekBackwardButton,
  AudioPlayerSeekForwardButton,
  AudioPlayerTimeDisplay,
  AudioPlayerTimeRange,
} from "@/components/ai-elements/audio-player";

export function MusicCard({ music }: { music: MusicPayload }) {
  const [activeIndex, setActiveIndex] = useState(0);

  // A genuinely new turn's payload starts back at the top track — without
  // this, switching to track 3 on one message would carry that selection
  // into the next message's unrelated set of tracks.
  useEffect(() => setActiveIndex(0), [music]);

  const tracks = music.tracks;
  const track = tracks[activeIndex] ?? tracks[0];

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

      {tracks.length > 1 && (
        <ul className="m-0 mt-2 flex list-none flex-col gap-0.5 p-0">
          {tracks.slice(0, 4).map((t, i) => {
            const isActive = i === activeIndex;
            return (
              <li key={`${t.name}-${i}`}>
                <button
                  type="button"
                  onClick={() => setActiveIndex(i)}
                  aria-pressed={isActive}
                  aria-label={`Play ${t.name}${t.artist ? ` by ${t.artist}` : ""}`}
                  className="flex w-full items-baseline gap-2 rounded-[8px] px-1.5 py-1 text-left text-[11.5px] transition-colors"
                  style={{
                    background: isActive
                      ? "color-mix(in oklab, var(--e1) 12%, transparent)"
                      : "transparent",
                  }}
                >
                  <span
                    className="truncate"
                    style={{ color: isActive ? "var(--ml-ink)" : "var(--ml-muted)" }}
                  >
                    {t.name}
                  </span>
                  {t.artist && (
                    <span className="shrink-0" style={{ color: "var(--ml-faint)" }}>
                      {t.artist}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-auto pt-4">
        {track?.preview_url ? (
          <AudioPlayer
            // Forces media-chrome to fully re-initialise on a track change
            // rather than reusing the previous track's internal playback
            // state against a new src.
            key={track.preview_url}
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
              <AudioPlayerSeekBackwardButton seekOffset={5} aria-label="Back 5 seconds" />
              <AudioPlayerPlayButton aria-label={`Play ${title}`} />
              <AudioPlayerSeekForwardButton seekOffset={5} aria-label="Forward 5 seconds" />
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
