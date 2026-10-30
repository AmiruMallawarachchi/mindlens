import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { Instrument_Sans, Newsreader } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TAGLINE, SITE_URL } from "@/lib/site";
import "./globals.css";

/** design.md §1.2 — max three fonts, each with one job.
 * Newsreader is the display and assistant voice; its italic is the accent
 * voice. Loaded at 300 only, with italic, because nothing in the system uses
 * a heavier serif. */
const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["300"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
});

/** UI, labels and everything the user types. */
const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-instrument-sans",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — ${SITE_TAGLINE}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    url: "/",
    siteName: SITE_NAME,
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
    images: [
      {
        url: "/mindlens-logo.png",
        width: 580,
        height: 546,
        alt: SITE_NAME,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
    images: ["/mindlens-logo.png"],
  },
};

// Runs before paint, before React hydrates — sets the real grade from
// localStorage immediately so a returning night-grade visitor never sees a
// flash of the day default. suppressHydrationWarning on <html> below is what
// makes this safe: React is told not to complain that the attribute it
// server-rendered ("day") differs from what's already in the DOM.
const GRADE_INIT_SCRIPT = `(function(){try{var g=localStorage.getItem("ml-grade");if(g==="night")document.documentElement.setAttribute("data-grade","night");}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-grade="day" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: GRADE_INIT_SCRIPT }} />
      </head>
      <body
        className={`${newsreader.variable} ${instrumentSans.variable} ${GeistMono.variable} antialiased`}
      >
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
      </body>
    </html>
  );
}
