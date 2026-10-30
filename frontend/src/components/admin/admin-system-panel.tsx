"use client";

import { useEffect } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import type { AdminServiceHealth, AdminSystemStatus } from "@/lib/types";

export function SystemPanel({
  status,
  error,
  loading,
  lastChecked,
  onRefresh,
}: {
  status: AdminSystemStatus | null;
  error: string | null;
  loading: boolean;
  lastChecked: Date | null;
  onRefresh: () => void;
}) {
  // Covers both ways this panel can appear: a fresh sign-in, and a reload
  // where sessionStorage already held a token so the parent mounted
  // straight into the signed-in state.
  useEffect(() => {
    onRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="ml-display text-[19px]">System</p>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-[var(--r-pill)] px-3.5 py-2 text-[12.5px] transition-colors hover:bg-white/[0.04] disabled:opacity-60"
          style={{ border: "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {loading ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <RefreshCw size={13} strokeWidth={1.8} />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div
          className="flex items-center gap-2 rounded-[var(--r-16)] p-4 text-[13px]"
          style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)", color: "#e08a8a" }}
        >
          <AlertCircle size={15} />
          {error}
        </div>
      )}

      {!status && !error && (
        <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>Loading…</p>
      )}

      {status && (
        <>
          <div
            className="rounded-[var(--r-18)] p-5"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <p className="ml-eyebrow mb-3">Environment</p>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Environment" value={status.environment} />
              <Field label="Release" value={status.release} mono />
              <Field
                label="Database"
                value={status.database}
                tone={status.database === "connected" ? "good" : "bad"}
              />
            </div>
          </div>

          <div
            className="rounded-[var(--r-18)] p-5"
            style={{ background: "var(--ml-panel)", border: "1px solid var(--ml-hairline)" }}
          >
            <p className="ml-eyebrow mb-3">Hosted services</p>
            <div className="flex flex-col gap-2">
              <ServiceRow name="Inference" service={status.inference} />
              <ServiceRow name="Vector retrieval" service={status.rag} />
              <ServiceRow name="Langfuse tracing" service={status.observability} />
            </div>
          </div>
        </>
      )}

      {lastChecked && (
        <p className="text-[11px]" style={{ color: "var(--ml-faint)" }}>
          Last checked {lastChecked.toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good" ? "#7fd8a8" : tone === "bad" ? "#e08a8a" : "var(--ml-ink)";
  return (
    <div>
      <p className="text-[10.5px]" style={{ color: "var(--ml-faint)" }}>{label}</p>
      <p className={mono ? "ml-num mt-0.5 text-[13.5px]" : "mt-0.5 text-[13.5px]"} style={{ color }}>
        {value}
      </p>
    </div>
  );
}

function ServiceRow({ name, service }: { name: string; service: AdminServiceHealth }) {
  // A model that isn't "ready", or has ever errored, is exactly what would
  // have made this week's silent all-classifiers-failing bug visible at a
  // glance instead of showing up as generic replies with no obvious cause.
  const flagged = !["ready", "configured", "connected"].includes(service.status);
  return (
    <div
      className="flex items-center justify-between rounded-[var(--r-13)] px-3.5 py-2.5"
      style={{
        background: flagged ? "color-mix(in oklab, #e08a8a 10%, transparent)" : "var(--ml-panel-strong)",
        border: `1px solid ${flagged ? "#e08a8a" : "var(--ml-hairline)"}`,
      }}
    >
      <div className="min-w-0">
        <p className="text-[13px]" style={{ color: "var(--ml-ink)" }}>{name}</p>
        <p className="ml-num mt-0.5 truncate text-[11px]" style={{ color: "var(--ml-faint)" }}>
          {service.provider}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-right">
        <span
          className="ml-num rounded-[var(--r-pill)] px-2.5 py-1 text-[11px]"
          style={{
            background: flagged ? "transparent" : "color-mix(in oklab, #7fd8a8 16%, transparent)",
            color: flagged ? "#e08a8a" : "#7fd8a8",
          }}
        >
          {service.status}
        </span>
      </div>
    </div>
  );
}
