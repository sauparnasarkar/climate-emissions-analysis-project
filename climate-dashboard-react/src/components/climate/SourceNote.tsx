import type { ReactNode } from 'react';

/** Source traceability under a chart or KPI (requirements §2.3): who supplied the data, plus an
 * optional caveat. `sources` come from the API's attribution/meta, not retyped copy. */
/** `onChartPanel`: the note sits on a chart panel, which stays dark in every theme, so it takes the design system's chart-surface muted colour instead of the
 * page's. */
export function SourceNote({ sources, children, onChartPanel = false }: { sources: string[]; children?: ReactNode; onChartPanel?: boolean }) {
  return (
    <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: onChartPanel ? 'var(--__s9cmpx-chart-surface-text-weak)' : 'var(--__s9cmpx-static-text-weak)' }}>
      Source: {sources.join(' · ')}
      {children ? <> — {children}</> : null}
    </p>
  );
}
