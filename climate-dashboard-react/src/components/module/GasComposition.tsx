import { useState } from 'react';
import { useSectionIds } from './useSectionIds';
import { ChartCard, Slider, SyChart, useReducedMotion } from 'design-system';
import { fmtInt } from '../../lib/landingData';
import { GAS_COMPOSITION_ANCHOR, type Composition } from '../../lib/gasComposition';
import { fmtShare } from '../../lib/shareBars';
import { BaselineChip } from '../climate/BaselineChip';
import { PurposeLine } from '../climate/PurposeLine';
import { ShareBar } from '../overview/ShareSection';

/**
 * How the mix of greenhouse gases has changed (requirements §1.3.3; ENHANCEMENTS.md decision 66): a 100%-stacked area of CO₂, CH₄, N₂O and
 * fluorinated gases in CO₂-equivalent, and the same split for one chosen year. National totals on the stated GWP basis -- they exclude land use and
 * international aviation and shipping -- and everything about the basis comes from the API.
 */
export function GasComposition({ composition, embedded }: { composition: Composition; embedded?: boolean }) {
  const ids = useSectionIds(embedded, GAS_COMPOSITION_ANCHOR, 'gas-composition-heading');
  const { years, gases, mt, shares, residualPct, reconciliation, basis, units, excludedIncompleteYears, caveats } = composition;
  const first = years[0];
  const last = years[years.length - 1];
  const [picked, setPicked] = useState<number | null>(null);
  // A year with a gap in the data is skipped (see buildComposition), so a slider position lands on the nearest year that has the full split.
  const year = picked === null ? last : years.reduce((best, y) => (Math.abs(y - picked) < Math.abs(best - picked) ? y : best), years[0]);
  const yi = years.indexOf(year);
  // The slider speaks in calendar years, but not every year has the full split. A step (or a drag) that lands on a missing year goes to the nearest
  // available year *in the direction of travel*; snapping back to the current year would leave a keyboard user unable to cross the gap.
  const move = (v: number) => {
    if (v === year) return;
    const ahead = years.filter((y) => (v > year ? y > year : y < year));
    if (ahead.length === 0) return;
    setPicked(ahead.reduce((best, y) => (Math.abs(y - v) < Math.abs(best - v) ? y : best), ahead[0]));
  };
  const reduceMotion = useReducedMotion();
  const order = gases.map((g) => ({ code: g.short, name: g.name, color: g.color }));

  return (
    <section id={ids.sectionId} aria-labelledby={ids.headingId} style={{ marginBottom: 24 }}>
      <h3 id={ids.headingId} className="__s9cmpx-headline6" style={{ margin: '0 0 12px' }}>Gas composition, {first} onward</h3>
      <ChartCard title={`Share of greenhouse-gas emissions by gas, ${first}–${last}`} headingLevel={4}>
        <PurposeLine>show how the mix of gases behind the all-gas total has shifted, and where CO₂ sits within it.</PurposeLine>
        <SyChart
          height={300}
          yTitle="Share of CO₂-equivalent (%)"
          stackedAreaMode="percent"
          ariaLabel={`Stacked area chart of the share of each greenhouse gas in CO₂-equivalent, ${first} to ${last}. In ${last}: ${gases.map((g, i) => `${g.name} ${fmtShare(shares[years.length - 1][i])}`).join(', ')}.`}
          series={gases.map((g, i) => ({ name: g.name, x: years, y: mt[i], kind: 'area' as const, color: g.color }))}
        />
        <div style={{ margin: '12px 0 4px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
          <span className="__s9cmpx-label3">{year}</span>
          <div style={{ flex: '1 1 220px' }}>
            <Slider label="Year" min={first} max={last} step={1} value={year} onChange={move} showValue={false} showRangeLabels showThumbValue />
          </div>
        </div>
        <ShareBar title="Gas split" subtitle={String(year)} order={order} values={shares[yi]} tween={!reduceMotion} />
        <table style={{ width: '100%', maxWidth: 560, marginTop: 10, borderCollapse: 'collapse', fontVariantNumeric: 'tabular-nums' }}>
          <caption className="__s9cmpx-body4" style={{ textAlign: 'left', color: 'var(--__s9cmpx-static-text-weak)', paddingBottom: 4 }}>Greenhouse gases by share, {year}</caption>
          <thead>
            <tr className="__s9cmpx-label4" style={{ textAlign: 'right', color: 'var(--__s9cmpx-static-text-weak)' }}>
              <th scope="col" style={{ textAlign: 'left', fontWeight: 600 }}>Gas</th>
              <th scope="col" style={{ fontWeight: 600 }}>Share</th>
              <th scope="col" style={{ fontWeight: 600 }}>MtCO₂e</th>
            </tr>
          </thead>
          <tbody>
            {gases.map((g, i) => (
              <tr key={g.id} className="__s9cmpx-body3" style={{ textAlign: 'right' }}>
                <th scope="row" style={{ textAlign: 'left', fontWeight: 400 }}>
                  <span aria-hidden style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: g.color, marginRight: 8 }} />
                  {g.name}
                </th>
                <td>{fmtShare(shares[yi][i])}</td>
                <td>{fmtInt(mt[i][yi])}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {residualPct[yi] !== null && (
          <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
            Shares are of the four gases listed. Together they sit {Math.abs(residualPct[yi] as number).toFixed(2)}% {(residualPct[yi] as number) >= 0 ? 'above' : 'below'} PRIMAP-hist&apos;s own national total for {year}
            {reconciliation ? ` (largest gap in any year ${reconciliation.maxAbsResidualPct.toFixed(2)}%, held to within ${reconciliation.tolerancePct}%)` : ''}.
          </p>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }}>
          <BaselineChip baseline="none · shares of each year" source={`${first}–${last}`} />
          <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
            {basis} ({units}).{excludedIncompleteYears.length > 0 ? ` Incomplete trailing year${excludedIncompleteYears.length > 1 ? 's' : ''} left out: ${excludedIncompleteYears.join(', ')}.` : ''}
          </span>
        </div>
        {caveats.length > 0 && (
          <details style={{ marginTop: 8 }}>
            <summary className="__s9cmpx-body4" style={{ cursor: 'pointer' }}>What this covers, and what it leaves out</summary>
            <ul className="__s9cmpx-body4" style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              {caveats.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </details>
        )}
      </ChartCard>
    </section>
  );
}
