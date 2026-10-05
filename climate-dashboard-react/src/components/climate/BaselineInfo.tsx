import { useEffect, useId, useRef, useState } from 'react';

/** What §2.5 requires wherever a series is indexed or compared to a reference: the baseline year or
 * period, the index formula, the source data range and any excluded years. Values come from the API. */
export interface BaselineSpec {
  /** e.g. "1990 = 100" or "1850–1900 mean" */
  baseline: string;
  reference: string;
  formula: string;
  sourceRange: string;
  /** Years left out of the series, with no reason text -- "None" when nothing was excluded. */
  excludedYears: string;
  note?: string;
}

/** The ⓘ button next to a KPI or chart title; opens a small panel listing the baseline details.
 * A disclosure (aria-expanded), closed by Escape or an outside click. */
export function BaselineInfo({ spec, label }: { spec: BaselineSpec; label: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  const rows: Array<[string, string]> = [
    ['Baseline', spec.baseline],
    ['Reference', spec.reference],
    ['Formula', spec.formula],
    ['Source range', spec.sourceRange],
    ['Excluded years', spec.excludedYears],
  ];

  return (
    <span ref={rootRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        aria-label={`Baseline details: ${label}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        style={{
          width: 20, height: 20, padding: 0, borderRadius: '50%', cursor: 'pointer', fontSize: 12, lineHeight: 1,
          border: '1px solid var(--__s9cmpx-static-divider-standard, currentColor)', background: 'transparent', color: 'inherit',
        }}
      >
        <span aria-hidden="true">ⓘ</span>
      </button>
      {open && (
        <div
          id={panelId}
          role="region"
          aria-label={`Baseline for ${label}`}
          style={{
            position: 'absolute', zIndex: 20, top: 26, right: 0, width: 280, padding: 12, borderRadius: 6, fontSize: 13,
            background: 'var(--__s9cmpx-static-background-standard)', color: 'var(--__s9cmpx-static-text-standard)',
            border: '1px solid var(--__s9cmpx-static-divider-standard, currentColor)', boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
          }}
        >
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
            {rows.map(([k, v]) => (
              <div key={k} style={{ display: 'contents' }}>
                <dt style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{k}</dt>
                <dd style={{ margin: 0 }}>{v}</dd>
              </div>
            ))}
          </dl>
          {spec.note && <p style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>{spec.note}</p>}
        </div>
      )}
    </span>
  );
}
