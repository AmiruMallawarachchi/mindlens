"use client";

// Route-segment error boundary — catches crashes within a page while
// layout.tsx (and its CSS) stays intact, so this can safely use the real
// design tokens rather than global-error.tsx's inline-only fallback.

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main
      className="ml-root grid min-h-screen place-items-center p-6 text-center"
      style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}
    >
      <div>
        <p className="ml-eyebrow mb-3">Something went wrong</p>
        <h1 className="ml-display mb-6 text-[28px]">Mindlens hit a snag.</h1>
        <button
          type="button"
          onClick={reset}
          className="rounded-[99px] px-5 py-2.5 text-[13px] font-medium"
          style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
        >
          Try again
        </button>
      </div>
    </main>
  );
}
