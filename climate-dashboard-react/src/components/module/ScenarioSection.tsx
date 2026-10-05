import { ChartCard, SyChart } from 'design-system';
import { SCENARIO_LABEL } from '../../lib/climateCopy';
import type { PathwayName } from '../../lib/pathways';
import { SCENARIOS_ANCHOR, type ScenarioView } from '../../lib/scenarioView';
import { BaselineChip } from '../climate/BaselineChip';
import { PurposeLine } from '../climate/PurposeLine';

const ON_DARK: Record<PathwayName, string> = { BAU: '#FFB54D', Moderate: '#5FD8F7', Aggressive: '#8BD17C' };
const OBSERVED = '#94B4C0';
const TEMP_ANNUAL = 'rgba(234, 91, 98, 0.45)';
const TEMP_MEAN = '#EA5B62';

const panel = { background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8 } as const;

/**
 * Implied temperature by scenario (requirements §1.3.5; ENHANCEMENTS.md decision 66): the three emissions pathways beside the history they continue,
 * and the temperature they imply, with the API's own reading of the output. Illustrative throughout -- a translation of the pathways with the headline
 * slope, not a climate model and not a projection -- and labelled with the wording the requirements prescribe, which the API supplies. The observed
 * emissions are OWID's World fossil + cement total, the pathways' own basis.
 */
export function ScenarioSection({ view }: { view: ScenarioView }) {
  const { startYear, horizon, pathways, observedEmissions, observedTemperature, observedMean5y, anchor, horizonGapC, readingNote, labels, assumptions } = view;
  const last = (xs: Array<{ year: number; value: number }>) => xs[xs.length - 1];
  // Described from what is actually drawn, so a missing or early-ending history is not announced as present.
  const span = (xs: Array<{ year: number }>) => `${xs[0].year} to ${xs[xs.length - 1].year}`;
  const a = assumptions;
  const basis = [
    a.slope !== null ? `Slope ${a.slope.toFixed(3)}${a.slopeUnit ? ` ${a.slopeUnit}` : ''}${a.slopeLabel ? ` (${a.slopeLabel})` : ''}` : null,
    a.restOfWorldPct !== null ? `rest of world held at ${a.restOfWorldPct.toFixed(1)}% of the global total${a.restOfWorldYear !== null ? ` as of ${a.restOfWorldYear}` : ''}` : null,
    a.landUseGt !== null ? `land-use CO₂ held flat at ${a.landUseGt.toFixed(1)} Gt a year${a.landUseWindow ? ` (${a.landUseWindow[0]}–${a.landUseWindow[1]} mean)` : ''}` : null,
  ].filter((s): s is string => s !== null);

  return (
    <section id={SCENARIOS_ANCHOR} aria-labelledby="scenarios-heading" style={{ marginBottom: 24 }}>
      <style>{'@media (max-width: 1200px) { .module-scenario-grid { grid-template-columns: minmax(0, 1fr) !important; } }'}</style>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 12px', margin: '0 0 12px' }}>
        <h2 id="scenarios-heading" className="__s9cmpx-headline5" style={{ margin: 0 }}>Implied temperature by scenario, {startYear}–{horizon}</h2>
        <span className="__s9cmpx-label4" style={{ padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase', letterSpacing: '.04em', background: 'var(--__s9cmpx-static-background-warning, rgba(176,122,16,0.16))', color: 'var(--__s9cmpx-static-text-warning, #8A5A00)' }}>
          {SCENARIO_LABEL}
        </span>
      </div>
      <div className="module-scenario-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr) 290px', gap: 16, alignItems: 'start' }}>
        <ChartCard title="1 · Annual emissions" headingLevel={3}>
          <PurposeLine>show how far apart the pathways are in emissions, from where the record leaves off.</PurposeLine>
          <SyChart
            height={300}
            yTitle="GtCO₂ a year"
            referenceX={{ value: startYear, label: `${startYear} start` }}
            ariaLabel={`Line chart of annual global CO₂ in GtCO₂, ${observedEmissions.length ? `observed ${span(observedEmissions)} and ` : ''}three pathways from ${startYear} to ${horizon}. In ${horizon}: ${pathways.map((p) => `${p.label} ${last(p.emissions).value.toFixed(1)}`).join(', ')}.`}
            series={[
              ...(observedEmissions.length ? [{ name: 'Observed', x: observedEmissions.map((p) => p.year), y: observedEmissions.map((p) => p.value), kind: 'line' as const, color: OBSERVED, showMarkers: false }] : []),
              ...pathways.map((p) => ({ name: p.label, x: p.emissions.map((r) => r.year), y: p.emissions.map((r) => r.value), kind: 'line' as const, color: ON_DARK[p.name], dashed: true, showMarkers: false })),
            ]}
          />
          <div style={{ marginTop: 8 }}>
            <BaselineChip baseline="none · annual level" source="OWID World" />
          </div>
        </ChartCard>

        <ChartCard title="2 · Implied temperature" headingLevel={3}>
          <PurposeLine>show what those pathways would mean for the temperature anomaly: far apart in emissions, close in temperature.</PurposeLine>
          <SyChart
            height={300}
            yTitle="°C above 1850–1900"
            referenceX={[{ value: startYear, label: `${startYear} start` }, ...(horizonGapC !== null ? [{ value: horizon, label: `${horizonGapC.toFixed(2)} °C apart` }] : [])]}
            ariaLabel={[
              'Line chart of the temperature anomaly in °C above the 1850 to 1900 mean.',
              observedTemperature.length ? `Observed annual ${span(observedTemperature)}${observedMean5y.length ? `, with its 5-year mean ${span(observedMean5y)}` : ''}.` : null,
              anchor ? `Anchored at ${anchor.value.toFixed(2)} °C in ${anchor.year}.` : null,
              `Implied level of each pathway, ${startYear} to ${horizon}.`,
              `In ${horizon}: ${pathways.map((p) => `${p.label} ${last(p.temperature).value.toFixed(2)} °C`).join(', ')}${horizonGapC !== null ? `; the pathways are ${horizonGapC.toFixed(2)} °C apart` : ''}.`,
            ].filter((s): s is string => s !== null).join(' ')}
            series={[
              ...(observedTemperature.length ? [{ name: 'Observed (annual)', x: observedTemperature.map((p) => p.year), y: observedTemperature.map((p) => p.value), kind: 'line' as const, color: TEMP_ANNUAL, showMarkers: false }] : []),
              ...(observedMean5y.length ? [{ name: '5-year mean', x: observedMean5y.map((p) => p.year), y: observedMean5y.map((p) => p.value), kind: 'line' as const, color: TEMP_MEAN, showMarkers: false }] : []),
              ...pathways.map((p) => ({ name: p.label, x: p.temperature.map((r) => r.year), y: p.temperature.map((r) => r.value), kind: 'line' as const, color: ON_DARK[p.name], dashed: true, showMarkers: false })),
              ...(anchor ? [{ name: `${anchor.value.toFixed(2)} °C anchor`, x: [anchor.year], y: [anchor.value], kind: 'line' as const, color: '#ffffff', showMarkers: true }] : []),
            ]}
          />
          <div style={{ marginTop: 8 }}>
            <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
          </div>
        </ChartCard>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {readingNote && (
            <div style={{ ...panel, borderTop: `3px solid ${ON_DARK.BAU}`, padding: '12px 14px' }}>
              <div className="__s9cmpx-label3" style={{ marginBottom: 6 }}>Reading note · generated from the output</div>
              <p className="__s9cmpx-body3" style={{ margin: 0 }}>{readingNote}</p>
            </div>
          )}
          <table style={{ ...panel, width: '100%', borderCollapse: 'collapse', fontVariantNumeric: 'tabular-nums', padding: 8 }}>
            <caption className="__s9cmpx-body4" style={{ textAlign: 'left', color: 'var(--__s9cmpx-static-text-weak)', padding: '0 0 4px' }}>{horizon} at a glance</caption>
            <thead>
              <tr className="__s9cmpx-label4" style={{ textAlign: 'right', color: 'var(--__s9cmpx-static-text-weak)' }}>
                <th scope="col" style={{ textAlign: 'left', fontWeight: 600, padding: '4px 8px' }}>Pathway</th>
                <th scope="col" style={{ fontWeight: 600, padding: '4px 8px' }}>GtCO₂ a year</th>
                <th scope="col" style={{ fontWeight: 600, padding: '4px 8px' }}>°C</th>
              </tr>
            </thead>
            <tbody>
              {pathways.map((p) => (
                <tr key={p.name} className="__s9cmpx-body3" style={{ textAlign: 'right' }}>
                  <th scope="row" style={{ textAlign: 'left', fontWeight: 400, padding: '4px 8px' }}>
                    <span aria-hidden style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: ON_DARK[p.name], marginRight: 8 }} />
                    {p.label}
                  </th>
                  <td style={{ padding: '4px 8px' }}>{p.emissions.length ? last(p.emissions).value.toFixed(1) : '—'}</td>
                  <td style={{ padding: '4px 8px' }}>{last(p.temperature).value.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="__s9cmpx-body4" style={{ marginTop: 10, color: 'var(--__s9cmpx-static-text-weak)' }}>
        {labels.length > 0 && <p style={{ margin: '0 0 4px' }}>{labels.join(' · ')}.</p>}
        {basis.length > 0 && <p style={{ margin: 0 }}>{basis.join('; ')}.</p>}
      </div>
    </section>
  );
}
