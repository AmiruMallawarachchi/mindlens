"use client";

/**
 * Settings primitives. Every section composes these rather than hand-rolling
 * layout, which is what keeps the pane looking like one system instead of a
 * pile of differently-spaced forms.
 */

import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function SettingsHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="ml-display mb-5 text-[20px]" style={{ color: "var(--ml-ink)" }}>
      {children}
    </h2>
  );
}

export function SettingsGroup({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      {title && <p className="ml-eyebrow mb-3">{title}</p>}
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

/** Label + description on the left, control on the right — Claude's row. */
export function Row({
  label,
  description,
  control,
  stacked = false,
}: {
  label: string;
  description?: React.ReactNode;
  control?: React.ReactNode;
  /** Put the control on its own line below — for wide inputs and grids. */
  stacked?: boolean;
}) {
  return (
    <div
      className={cn("py-4", !stacked && "flex items-center justify-between gap-6")}
      style={{ borderBottom: "1px solid var(--ml-hairline)" }}
    >
      <div className="min-w-0">
        <p className="text-[13.5px] font-medium" style={{ color: "var(--ml-ink)" }}>
          {label}
        </p>
        {description && (
          <p className="mt-1 text-[12.5px] leading-[1.55]" style={{ color: "var(--ml-muted)" }}>
            {description}
          </p>
        )}
      </div>
      {control && <div className={cn("shrink-0", stacked && "mt-3.5 w-full")}>{control}</div>}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="relative h-[22px] w-[38px] shrink-0 rounded-full transition-colors"
      style={{
        background: checked ? "var(--e1)" : "var(--ml-hairline-strong)",
      }}
    >
      <span
        className="absolute top-[3px] size-4 rounded-full bg-white transition-[left]"
        style={{ left: checked ? 19 : 3 }}
      />
    </button>
  );
}

export function Select<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T | "";
  options: { id: T; label: string; hint?: string }[];
  onChange: (next: T) => void;
  ariaLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const selected = options.find((o) => o.id === value);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex min-w-[190px] items-center justify-between gap-2 rounded-[var(--r-11)] px-3.5 py-2 text-[13px]"
        style={{
          background: "var(--ml-panel)",
          border: "1px solid var(--ml-hairline-strong)",
          color: selected ? "var(--ml-ink)" : "var(--ml-faint)",
        }}
      >
        {selected?.label ?? "Choose…"}
        <ChevronDown size={14} strokeWidth={1.8} style={{ color: "var(--ml-faint)" }} />
      </button>

      {open && (
        <div
          role="listbox"
          className="ml-glass absolute right-0 z-20 mt-1.5 max-h-[300px] w-[280px] overflow-y-auto rounded-[var(--r-13)] p-1.5"
          style={{ background: "var(--ml-panel-legible)", border: "1px solid var(--ml-hairline-strong)" }}
        >
          {options.map((opt) => (
            <button
              key={opt.id}
              type="button"
              role="option"
              aria-selected={opt.id === value}
              onClick={() => {
                onChange(opt.id);
                setOpen(false);
              }}
              className="flex w-full items-start gap-2 rounded-[var(--r-11)] px-3 py-2 text-left transition-colors hover:bg-white/[0.05]"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[13px]" style={{ color: "var(--ml-ink)" }}>
                  {opt.label}
                </span>
                {opt.hint && (
                  <span className="mt-0.5 block text-[11.5px] leading-[1.45]" style={{ color: "var(--ml-muted)" }}>
                    {opt.hint}
                  </span>
                )}
              </span>
              {opt.id === value && (
                <Check size={14} strokeWidth={2} className="mt-0.5 shrink-0" style={{ color: "var(--e1)" }} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function TextInput({
  value,
  onChange,
  placeholder,
  maxLength,
  ariaLabel,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  maxLength?: number;
  ariaLabel: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      maxLength={maxLength}
      aria-label={ariaLabel}
      className="w-full min-w-[220px] rounded-[var(--r-11)] px-3.5 py-2 text-[13px] outline-none"
      style={{
        background: "var(--ml-panel)",
        border: "1px solid var(--ml-hairline-strong)",
        color: "var(--ml-ink)",
      }}
    />
  );
}

/** A save affordance that states what happened rather than just going quiet. */
export function SaveBar({
  onSave,
  saving,
  saved,
  dirty,
}: {
  onSave: () => void;
  saving: boolean;
  saved: boolean;
  dirty: boolean;
}) {
  return (
    // Must be fully opaque, not translucent-plus-blur. The settings modal is
    // .ml-glass, which sets backdrop-filter and so becomes a backdrop root:
    // a blur here would sample what's behind the *modal*, never the sibling
    // content scrolling underneath this bar, leaving that text legibly
    // bleeding through. Only a solid fill occludes it.
    <div
      className="sticky bottom-0 -mx-8 mt-2 flex items-center gap-3 px-8 py-4"
      style={{ background: "var(--ml-panel-solid)", borderTop: "1px solid var(--ml-hairline)" }}
    >
      <button
        type="button"
        onClick={onSave}
        disabled={saving || !dirty}
        className="rounded-[99px] px-5 py-2.5 text-[13px] font-medium transition-opacity disabled:opacity-40"
        style={{ background: "linear-gradient(135deg, var(--e1), var(--e2))", color: "#fffdf8" }}
      >
        {saving ? "Saving…" : "Save changes"}
      </button>
      {saved && !dirty && (
        <span className="text-[12.5px]" style={{ color: "var(--e1)" }}>
          Saved.
        </span>
      )}
      {dirty && !saving && (
        <span className="text-[12.5px]" style={{ color: "var(--ml-faint)" }}>
          Unsaved changes.
        </span>
      )}
    </div>
  );
}
