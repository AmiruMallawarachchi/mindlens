/** One place for the public site identity, used by metadata, robots, and
 * the sitemap so they cannot drift apart. `NEXT_PUBLIC_SITE_URL` lets a
 * preview deployment advertise itself instead of the production domain. */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://mindlens-theta.vercel.app"
).replace(/\/+$/, "");

export const SITE_NAME = "MindLens";

export const SITE_DESCRIPTION =
  "A personalised wellbeing companion that helps you understand patterns and take the next kind, practical step.";

export const SITE_TAGLINE = "Think clearly. Feel fully.";
