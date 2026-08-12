/**
 * The settings nav. Only sections that are genuinely wired belong here —
 * a nav item that leads to a stub is worse than no nav item, so new entries
 * land in the same commit as the section they open.
 */

import { Brain, CircleUser, Lock, Palette, SlidersHorizontal, type LucideIcon } from "lucide-react";

export type SettingsSectionId = "general" | "account" | "privacy" | "appearance" | "memory";

export const SETTINGS_NAV: {
  label: string;
  items: { id: SettingsSectionId; label: string; icon: LucideIcon }[];
}[] = [
  {
    label: "Settings",
    items: [
      { id: "general", label: "General", icon: SlidersHorizontal },
      { id: "account", label: "Account", icon: CircleUser },
      { id: "privacy", label: "Privacy & data", icon: Lock },
    ],
  },
  {
    label: "Customize",
    items: [
      { id: "appearance", label: "Appearance", icon: Palette },
      { id: "memory", label: "Memory", icon: Brain },
    ],
  },
];
