import { ChartCard } from 'design-system';
import { ALL_GAS_TAG } from '../../lib/climateCopy';
import { ALL_GAS_ANCHOR, type AllGas } from '../../lib/allGas';
import { BaselineChip } from '../climate/BaselineChip';
import { PurposeLine } from '../climate/PurposeLine';
import { ClimateScatter } from '../landing/ClimateScatter';

const card = { background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, padding: '14px 16px' } as const;

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{k}</dt>
      <dd className="__s9cmpx-body3" style={{ margin: 0, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{v}</dd>
    </>
  );
}

// The caveats that belong beside this chart; the licences, sources and file-vintage notes live with the methodology (Step 9).
const NEAR_CHART = /short window|time|CO2-equivalent|incomplete/i;

/**
 * The recent all-gas relationship (ENHANCEMENTS.md decision 65; requirements §1.3.1): PRIMAP-hist national total greenhouse gases in CO₂-equivalent,
 * 1970 onward, against the temperature anomaly. A recent co-movement over a short window, tagged "not TCRE": it is never given that name and never
 * compared with the AR6 range or the long-run CO₂ slope. Every figure and sentence about the fit is the API's.
 */
export function AllGasRelationship({ allGas }: { allGas: AllGas }) {
  const { slope, ciLow, ciHigh, rSquared, start, end, nYears, bootstrap, stabilitySummary, caveats, omittedYears } = allGas;
  const near = caveats.filter((c) => NEAR_CHART.test(c));
  return (
    <section id={ALL_GAS_ANCHOR} aria-labelledby="all-gas-heading" style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 12px', margin: '0 0 12px' }}>
        <h3 id="all-gas-heading" className="__s9cmpx-headline6" style={{ margin: 0 }}>Recent all-gas relationship, {start} onward</h3>
        <span className="__s9cmpx-label4" style={{ padding: '2px 8px', borderRadius: 3, background: 'var(--__s9cmpx-static-background-strong, rgba(127,127,127,0.18))' }}>{ALL_GAS_TAG}</span>
      </div>
      <div className="module-relationship-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <ChartCard title={`Temperature anomaly vs cumulative all-gas emissions, ${start}–${end}`} headingLevel={4}>
          <PurposeLine>show the recent co-movement of all greenhouse gases with warming. It is a separate, shorter view, not the long-run CO₂ relationship above.</PurposeLine>
          <div className="climate-chart-panel">
            <ClimateScatter signal={allGas} xTitle="Cumulative greenhouse gases, national totals (GtCO₂e)" xQuantity="cumulative greenhouse-gas emissions" xUnit="GtCO₂e" xStep={250} xMin={Math.floor(allGas.points[0].gt / 250) * 250} />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
            <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
            <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
              {allGas.xName}. Each dot is one year; the dashed line is the least-squares fit.
            </span>
          </div>
        </ChartCard>

        <div style={card}>
          <div className="__s9cmpx-label3">{allGas.label}</div>
          <div className="__s9cmpx-headline3" style={{ fontVariantNumeric: 'tabular-nums', margin: '4px 0 8px' }}>{slope.toFixed(3)} <span className="__s9cmpx-body3">{allGas.unit}</span></div>
          <dl style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px', margin: 0 }}>
            <Row k="95% CI (Newey–West HAC)" v={`${ciLow.toFixed(3)}–${ciHigh.toFixed(3)}`} />
            {bootstrap && <Row k={`Bootstrap interval (${bootstrap.blockYears}-year blocks)`} v={`${bootstrap.low.toFixed(3)}–${bootstrap.high.toFixed(3)}`} />}
            <Row k="R²" v={rSquared.toFixed(2)} />
            <Row k="Years" v={`${start}–${end} (${nYears})`} />
            {/* Only when the pair itself lists some: PRIMAP's incomplete latest year is dropped upstream and stated in the caveats below, so "None" would contradict it. */}
            {omittedYears.length > 0 && <Row k="Excluded years" v={omittedYears.join(', ')} />}
          </dl>
          <p className="__s9cmpx-body4" style={{ margin: '10px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
            Not TCRE and not compared with the IPCC range: it covers a short window, leaves out land-use change and international aviation and shipping, and a steadily rising cumulative
            series is strongly correlated with time. It describes a recent co-movement, not a cause.
          </p>
          {(stabilitySummary || near.length > 0) && (
            <details style={{ marginTop: 8 }}>
              <summary className="__s9cmpx-body4" style={{ cursor: 'pointer' }}>How stable is this, and what to keep in mind</summary>
              {stabilitySummary && <p className="__s9cmpx-body4" style={{ margin: '6px 0 0' }}>{stabilitySummary}</p>}
              {near.length > 0 && (
                <ul className="__s9cmpx-body4" style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                  {near.map((c) => <li key={c}>{c}</li>)}
                </ul>
              )}
            </details>
          )}
        </div>
      </div>
    </section>
  );
}
