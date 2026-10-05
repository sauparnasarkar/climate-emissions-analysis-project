/**
 * The per-figure baseline chip every Area 2 chart and KPI carries (requirements §2.5), e.g. "Baseline 1990 · OWID". Mono 11px, neutral chip surface.
 * `inChartPanel`: the chip sits inside a chart panel, which stays dark in every theme, so it takes the design system's chart-surface muted colour and a
 * light translucent surface instead of the page's chip colours (dark text on the dark panel would fall to ~2.7:1 in the bright theme).
 */
export function BaselineChip({ baseline, source, inChartPanel = false }: { baseline: string; source?: string; inChartPanel?: boolean }) {
  return (
    <span
      className="baseline-chip"
      style={{
        display: 'inline-block',
        padding: '3px 6px',
        borderRadius: 3,
        fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)',
        fontSize: 11,
        background: inChartPanel ? 'rgba(255, 255, 255, 0.12)' : 'var(--__s9cmpx-static-background-strong, rgba(127,127,127,0.18))',
        color: inChartPanel ? 'var(--__s9cmpx-chart-surface-text-weak)' : 'var(--__s9cmpx-static-text-weak)',
      }}
    >
      {`Baseline ${baseline}`}
      {source ? ` · ${source}` : ''}
    </span>
  );
}
