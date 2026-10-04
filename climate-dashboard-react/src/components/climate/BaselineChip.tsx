/** The per-figure baseline chip every Area 2 chart and KPI carries (requirements §2.5), e.g.
 * "Baseline 1990 · OWID". Mono 11px, neutral chip surface. */
export function BaselineChip({ baseline, source }: { baseline: string; source?: string }) {
  return (
    <span
      className="baseline-chip"
      style={{
        display: 'inline-block',
        padding: '3px 6px',
        borderRadius: 3,
        fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)',
        fontSize: 11,
        background: 'var(--__s9cmpx-static-background-strong, rgba(127,127,127,0.18))',
        color: 'var(--__s9cmpx-static-text-weak)',
      }}
    >
      {`Baseline ${baseline}`}
      {source ? ` · ${source}` : ''}
    </span>
  );
}
