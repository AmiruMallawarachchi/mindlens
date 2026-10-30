"use client";

import { CompanionAvatar } from "@/components/companion/companion-avatar";
import { Settings2, ShieldCheck } from "lucide-react";
import type { ChatSidebarProps } from "./chat-sidebar-types";

export function ChatSidebarFooter({ mood, user, companionId, companionActivity, onNavigate }: Pick<ChatSidebarProps, "mood" | "user" | "companionId" | "companionActivity" | "onNavigate">) {
  return (
    <>
      {/* The companion's resting place. It used to float over the
        * conversation on a fixed right-hand pixel offset that assumed a
        * right-hand rail was always mounted — once that assumption broke,
        * the offset pointed into the middle of the transcript and the
        * companion sat on top of the user's own text while they typed.
        * A stable home in the sidebar cannot collide with anything. */}
      {companionId && (
        <div className="flex justify-center pb-1 pt-2">
          <CompanionAvatar
            companionId={companionId}
            size={54}
            mood={mood}
            activity={companionActivity}
            withShadow
          />
        </div>
      )}

      <div className="p-3">
        <button
          type="button"
          onClick={() => onNavigate("settings")}
          aria-label="Open settings"
          className="flex w-full items-center gap-2.5 rounded-[var(--r-13)] p-3 text-left transition-colors hover:bg-white/[0.04]"
          style={{
            background: "var(--ml-panel-strong)",
            border: "1px solid var(--ml-hairline)",
          }}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12.5px]" style={{ color: "var(--ml-ink)" }}>
              {user?.nickname || user?.name || "Signed in"}
            </span>
            <span
              className="mt-1 flex items-center gap-1.5 text-[10.5px]"
              style={{ color: "var(--ml-faint)" }}
            >
              {/* Not "end-to-end", and not "only you" either: the server must
                * read every message for the classifiers to run, and Groq
                * reads it to write the reply — so "only you" is a stronger,
                * false claim, not a weaker safe one. An accurate promise is
                * worth more here than an impressive one that doesn't survive
                * being checked. */}
              <ShieldCheck size={12} strokeWidth={1.7} />
              Private · not end-to-end encrypted
            </span>
          </span>
          <Settings2 size={15} strokeWidth={1.7} className="shrink-0" style={{ color: "var(--ml-faint)" }} />
        </button>

        {/* §4.1's disclaimer. It used to sit under the composer on every
          * turn; it lives here now so the chat column stays quiet. This is
          * the desktop home for it only — below 780px this whole sidebar is
          * a drawer behind a hamburger, and a safety disclaimer that has to
          * be opened is not "always present", so the composer keeps a
          * compact copy at those widths. */}
        <p
          className="mt-2.5 px-1 text-[10.5px] leading-[1.55]"
          style={{ color: "var(--ml-faint)" }}
        >
          MindLens is a wellbeing companion — not emergency or medical care.{" "}
          <a
            href="https://findahelpline.com"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2 transition-colors hover:text-[var(--ml-muted)]"
          >
            Reach a human
          </a>
        </p>
      </div>
    </>
  );
}
