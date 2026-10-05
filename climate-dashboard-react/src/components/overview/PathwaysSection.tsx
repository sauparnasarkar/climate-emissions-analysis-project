import { Link } from 'react-router-dom';
import { FORECAST_END_YEAR } from '../../constants';
import { SCENARIO_LABEL } from '../../lib/climateCopy';
import { fmtInt } from '../../lib/landingData';
import { PATHWAYS_ANCHOR, type Pathways } from '../../lib/pathways';

const panel = { background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8 } as const;

/**
 * "Where today's patterns lead": the Overview's closing block (requirements §2.2 block 5; ENHANCEMENTS.md decision 63). The three scenario
 * pathways' emissions and *implied* temperature in the horizon year, labelled illustrative throughout, with links on to the full views. It does not
 * follow the page year -- the pathways run 2025 onward.
 */
export function PathwaysSection({ pathways }: { pathways: Pathways }) {
  const { year, cards, summary, startYear, lastObservedYear, restOfWorldYear, startOffsetPct } = pathways;
  // The pathways are fitted to history and begin one step on from it, so their first year is near -- not equal to -- the last observed total.
  const start =
    startOffsetPct === null
      ? `Pathways start in ${startYear}`
      : `Pathways start in ${startYear}, ${Math.abs(startOffsetPct).toFixed(1)}% ${startOffsetPct >= 0 ? 'above' : 'below'} the ${lastObservedYear} observed total of the covered countries`;
  return (
    <section id={PATHWAYS_ANCHOR} aria-labelledby="pathways-heading" style={{ marginTop: 24, marginBottom: 16 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 12px', marginBottom: 8 }}>
        <h2 id="pathways-heading" className="__s9cmpx-headline6" style={{ margin: 0 }}>Where today&apos;s patterns lead</h2>
        <span className="__s9cmpx-label4" style={{ padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase', letterSpacing: '.04em', background: 'var(--__s9cmpx-static-background-warning, rgba(176,122,16,0.16))', color: 'var(--__s9cmpx-static-text-warning, #8A5A00)' }}>
          {SCENARIO_LABEL}
        </span>
      </div>
      {summary && <p className="__s9cmpx-body2" style={{ margin: '0 0 12px' }}>{summary}</p>}
      <div className="pathways-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        {cards.map((c) => (
          <div key={c.name} style={{ ...panel, borderTop: `3px solid ${c.color}`, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div className="__s9cmpx-label3">{c.label}</div>
            <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{c.method}</div>
            <div className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums', marginTop: 4 }}>{c.levelC.toFixed(2)} °C</div>
            <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>implied, {year}</div>
            <div className="__s9cmpx-body3" style={{ fontVariantNumeric: 'tabular-nums', marginTop: 4 }}>{fmtInt(c.emissionsMt)} Mt a year</div>
          </div>
        ))}
      </div>
      <p className="__s9cmpx-body4" style={{ margin: '10px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
        Implied temperature = the observed 5-year-mean anchor plus the long-run slope × the emissions still to come; it is a translation of the pathways, not a climate model or a projection. {start}, and hold the rest of the world at its {restOfWorldYear} share.
      </p>
      <p className="__s9cmpx-body3" style={{ margin: '8px 0 0', display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
        <Link to="/forecasts">Forecasts to {FORECAST_END_YEAR} →</Link>
        <Link to="/scenarios">Scenario Comparison →</Link>
        <Link to="/climate-correlation">Implied temperature in the Correlation module →</Link>
      </p>
    </section>
  );
}
