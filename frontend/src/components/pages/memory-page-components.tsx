"use client";

import { X } from "lucide-react";

export function MemoryCategory({
  title,
  icon,
  empty,
  emptyText,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  empty: boolean;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="ml-eyebrow mb-3 inline-flex items-center gap-1.5" style={{ color: icon ? "var(--ml-muted)" : undefined }}>
        {icon}
        {title}
      </p>
      {empty ? (
        <p className="text-[13px]" style={{ color: "var(--ml-faint)" }}>{emptyText}</p>
      ) : (
        <div className="flex flex-col gap-2">{children}</div>
      )}
    </section>
  );
}

export function ChipList({
  items,
  onRemove,
  isArmed,
}: {
  items: string[];
  onRemove: (value: string) => void;
  isArmed: (value: string) => boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const armed = isArmed(item);
        return (
        <span
          key={item}
          className="inline-flex items-center gap-1.5 rounded-[99px] py-1.5 pl-3 pr-2 text-[12.5px]"
          style={{ border: armed ? "1px solid #e08a8a" : "1px solid var(--ml-hairline-strong)", color: "var(--ml-ink)" }}
        >
          {item}
          <button
            type="button"
            onClick={() => onRemove(item)}
            aria-label={armed ? `Click to confirm forgetting ${item}` : `Forget ${item}`}
            style={{ color: armed ? "#e08a8a" : "var(--ml-faint)" }}
          >
            {armed ? <span className="text-[10.5px] font-medium">Confirm</span> : <X size={12} strokeWidth={2} />}
          </button>
        </span>
        );
      })}
    </div>
  );
}
