import { pathwayColor } from '../lib/pathways';
import { formatKpiValue } from './kpiFormat';
import type { Kpi } from './types';

/**
 * The answer's KPI row (design handoff: up to three cards, each labelled with its data year). Every figure comes from the agent's
 * deterministic `kpis` block, which reads it from a tool result -- nothing is typed here. A scenario card takes the pathway's own line colour
 * as a top border (3px), so it reads as the same series as the chart beneath it.
 */
export function KpiRow({ kpis }: { kpis: Kpi[] }) {
  if (kpis.length === 0) return null;
  return (
    <ul aria-label="Key figures" style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(kpis.length, 3)}, minmax(0, 1fr))`, gap: 12, margin: 0, padding: 0, listStyle: 'none' }} className="ask-kpi-row">
      {kpis.map((kpi) => {
        const accent = kpi.series ? pathwayColor(kpi.series) : undefined;
        return (
          <li
            key={`${kpi.label}-${kpi.year ?? ''}`}
            style={{
              background: 'var(--__s9cmpx-static-background-standard)',
              border: '1px solid var(--__s9cmpx-static-divider-weak)',
              borderTop: accent ? `3px solid ${accent}` : '1px solid var(--__s9cmpx-static-divider-weak)',
              borderRadius: 8,
              padding: '12px 14px',
              minWidth: 0,
            }}
          >
            <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
              {kpi.label}
              {kpi.year != null && <> · {kpi.year}</>}
            </div>
            <div style={{ fontSize: 28, fontWeight: 600, lineHeight: 1.2, fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>{formatKpiValue(kpi)}</div>
            {kpi.sub && (
              <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)', marginTop: 2 }}>
                {kpi.sub}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
