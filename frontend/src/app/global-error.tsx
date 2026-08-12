"use client";

// Root-level error boundary — catches crashes layout.tsx itself can't
// recover from, so it renders its own <html>/<body> and avoids depending on
// globals.css even being reachable. Inline styles only, deliberately.

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#0a0b10",
          color: "#f7f6f1",
          fontFamily: "system-ui, sans-serif",
          textAlign: "center",
          padding: 24,
        }}
      >
        <div>
          <p style={{ fontSize: 13, opacity: 0.6, marginBottom: 12 }}>
            Something went wrong
          </p>
          <h1 style={{ fontSize: 24, fontWeight: 400, marginBottom: 16 }}>
            Mindlens hit a snag.
          </h1>
          <button
            type="button"
            onClick={reset}
            style={{
              background: "#f7f6f1",
              color: "#0a0b10",
              border: "none",
              borderRadius: 999,
              padding: "10px 20px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
