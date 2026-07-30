"use client";

/**
 * Settings — the Claude-style modal the user asked for: a left nav of
 * sections, a scrolling content pane, one close button. Replaces the old
 * "Your Mindlens" page, which had grown into a settings screen wearing a
 * page's clothes.
 *
 * Sections are registered in SECTIONS below. Only sections that are actually
 * wired appear — this file never renders a nav item that leads to a stub.
 */

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MindLensClient } from "@/lib/use-mindlens-client";
import { GeneralSection } from "./sections/general";
import { AccountSection } from "./sections/account";
import { PrivacySection } from "./sections/privacy";
import { AppearanceSection } from "./sections/appearance";
import { MemorySection } from "./sections/memory";
import { SETTINGS_NAV, type SettingsSectionId } from "./nav";

export function SettingsModal({
  client,
  open,
  onClose,
  initialSection = "general",
}: {
  client: MindLensClient;
  open: boolean;
  onClose: () => void;
  initialSection?: SettingsSectionId;
}) {
  const [section, setSection] = useState<SettingsSectionId>(initialSection);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const groups = SETTINGS_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) =>
      query.trim() ? item.label.toLowerCase().includes(query.trim().toLowerCase()) : true,
    ),
  })).filter((group) => group.items.length > 0);

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <button
        type="button"
        aria-label="Close settings"
        onClick={onClose}
        className="absolute inset-0 cursor-default border-none bg-black/45 backdrop-blur-[2px]"
      />

      <div
        className="ml-glass relative flex h-[min(760px,92vh)] w-full max-w-[1040px] overflow-hidden rounded-[var(--r-22)]"
        style={{ background: "var(--ml-panel-legible)", border: "1px solid var(--ml-hairline)" }}
      >
        {/* --- Left nav ---------------------------------------------------- */}
        <aside
          className="flex w-[248px] shrink-0 flex-col gap-3 overflow-y-auto p-4"
          style={{ borderRight: "1px solid var(--ml-hairline)" }}
        >
          <label
            className="flex items-center gap-2 rounded-[var(--r-11)] px-3 py-2"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <Search size={14} strokeWidth={1.8} style={{ color: "var(--ml-faint)" }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search"
              className="min-w-0 flex-1 bg-transparent text-[13px] outline-none"
              style={{ color: "var(--ml-ink)" }}
            />
          </label>

          {groups.map((group) => (
            <div key={group.label}>
              <p className="ml-eyebrow px-2 pb-1.5">{group.label}</p>
              <div className="flex flex-col gap-0.5">
                {group.items.map(({ id, label, icon: Icon }) => {
                  const active = section === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setSection(id)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-[var(--r-11)] px-3 py-2 text-left text-[13px] transition-colors",
                        active ? "font-medium" : "hover:bg-white/[0.04]",
                      )}
                      style={{
                        background: active ? "var(--ml-panel-strong)" : undefined,
                        border: active ? "1px solid var(--ml-hairline)" : "1px solid transparent",
                        color: active ? "var(--ml-ink)" : "var(--ml-muted)",
                      }}
                    >
                      <Icon size={15} strokeWidth={1.7} />
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </aside>

        {/* --- Content ----------------------------------------------------- */}
        <div className="relative min-w-0 flex-1 overflow-y-auto">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="absolute right-4 top-4 z-10 grid size-8 place-items-center rounded-full transition-colors hover:bg-[color-mix(in_oklab,var(--ml-ink)_8%,transparent)]"
            style={{ color: "var(--ml-muted)" }}
          >
            <X size={16} strokeWidth={1.8} />
          </button>

          {/* pb-2 leaves the sticky SaveBar somewhere to land without
            * clipping the last row of whatever section is open. */}
          <div className="px-8 pb-2 pt-7">
            {section === "general" && <GeneralSection client={client} />}
            {section === "account" && <AccountSection client={client} />}
            {section === "privacy" && <PrivacySection client={client} />}
            {section === "appearance" && <AppearanceSection client={client} />}
            {section === "memory" && <MemorySection />}
          </div>
        </div>
      </div>
    </div>
  );
}
