import Link from "next/link";

export default function NotFound() {
  return (
    <main
      className="ml-root grid min-h-screen place-items-center p-6 text-center"
      style={{ background: "var(--ml-canvas)", color: "var(--ml-ink)" }}
    >
      <div>
        <p className="ml-eyebrow mb-3">404</p>
        <h1 className="ml-display mb-3 text-[32px]">This page isn&rsquo;t here.</h1>
        <p className="mb-6 text-[14px]" style={{ color: "var(--ml-muted)" }}>
          The link might be old, or the address might be off.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-[99px] px-5 py-2.5 text-[13px] font-medium no-underline"
          style={{ background: "var(--ml-ink)", color: "var(--ml-canvas)" }}
        >
          Back to Mindlens
        </Link>
      </div>
    </main>
  );
}
