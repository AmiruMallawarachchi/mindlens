export function MindLensMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-lockup ${compact ? "is-compact" : ""}`}>
      <div className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      {!compact && (
        <div>
          <strong>MindLens</strong>
          <small>Think clearly. Feel fully.</small>
        </div>
      )}
    </div>
  );
}
