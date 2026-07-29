import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { Instrument_Sans, Newsreader } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
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
  title: "Mindlens — Think clearly. Feel fully.",
  description:
    "A personalised, multi-agent wellbeing companion that helps you understand patterns and take the next kind, practical step.",
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
