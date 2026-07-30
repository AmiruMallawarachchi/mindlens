"use client";

/**
 * Settings > Memory. The memory manager already exists as a full page
 * (components/pages/memory-page.tsx) and is the same thing a user wants
 * here, so this reuses it rather than growing a second, drifting copy.
 */

import { MemoryPage } from "@/components/pages/memory-page";
import { SettingsHeading } from "../ui";

export function MemorySection() {
  return (
    <>
      <SettingsHeading>Memory</SettingsHeading>
      <p className="mb-6 text-[12.5px] leading-[1.6]" style={{ color: "var(--ml-muted)" }}>
        Everything Mindlens has kept about you, and the controls to change or
        remove any of it.
      </p>
      <MemoryPage />
    </>
  );
}
