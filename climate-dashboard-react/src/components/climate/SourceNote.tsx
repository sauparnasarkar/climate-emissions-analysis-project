import type { ReactNode } from 'react';

/** Source traceability under a chart or KPI (requirements §2.3): who supplied the data, plus an
 * optional caveat. `sources` come from the API's attribution/meta, not retyped copy. */
export function SourceNote({ sources, children }: { sources: string[]; children?: ReactNode }) {
  return (
    <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
      Source: {sources.join(' · ')}
      {children ? <> — {children}</> : null}
    </p>
  );
}
