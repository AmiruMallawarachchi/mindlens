import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 writes frontend/AGENTS.md and a frontend/CLAUDE.md containing
  // "@AGENTS.md" on every dev boot. This repo's agent rules live in the root
  // CLAUDE.md, and a second CLAUDE.md one directory down shadows them for
  // anything working inside frontend/ — so the generated pair is actively
  // misleading here rather than merely redundant.
  agentRules: false,
};

export default nextConfig;
