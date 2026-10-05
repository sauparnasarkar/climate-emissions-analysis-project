import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChartCard, SegmentedControl, SyChart } from 'design-system';
import { fmtAnomaly, type ClimateSignal, type YearValue } from '../../lib/climateSignal';
import { SERIES_ON_DARK } from '../../lib/climateColors';
import { NOT_A_CLIMATE_MODEL, RELATIONSHIP_ANCHOR } from '../../lib/climateCopy';
import { BaselineChip } from '../climate/BaselineChip';
import { CHART_PANEL_STYLES } from '../climate/chartPanel';
import { PurposeLine } from '../climate/PurposeLine';
import { SourceNote } from '../climate/SourceNote';
import { ClimateScatter, ScatterLegend } from '../landing/ClimateScatter';

// The Overview's "relationship" block (Area 2, requirements §2.2 block 2): the primary explanatory chart comparing emissions with
// the temperature anomaly -- over time (two axes) or against cumulative CO₂ -- plus the compact "Why emissions matter" card.
// It illustrates long-term co-movement as context; it never says one year's emissions set that year's temperature.

type View = 'time' | 'cumulative';
const VIEW_ITEMS = [{ value: 'time', label: 'Over time' }, { value: 'cumulative', label: 'Against cumulative CO₂' }];

/** Same treatment as the page's existing "Since 1990" card: standard surface, hairline border, accent-secondary top rule. */
const CARD_STYLE = {
  background: 'var(--__s9cmpx-static-background-standard)', padding: '12px 16px', border: '1px solid var(--__s9cmpx-static-divider-weak)',
  borderTop: '3px solid var(--__s9cmpx-accent-secondary, transparent)', borderRadius: 8,
} as const;

function WhyEmissionsMatter({ signal }: { signal: ClimateSignal }) {
  const { concentration, temperature } = signal;
  return (
    <section style={CARD_STYLE} aria-labelledby="why-emissions-matter">
      <span id="why-emissions-matter" className="__s9cmpx-label3" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>Why emissions matter</span>
      <p className="__s9cmpx-body2" style={{ margin: '4px 0 0' }}>
        Emissions raise the <strong>concentration</strong> of CO₂ in the atmosphere (now {concentration.value.toFixed(1)} ppm). What accumulates increases <strong>radiative
        forcing</strong>, the extra heat the atmosphere holds, and that warming is observed as the <strong>temperature anomaly</strong>: {fmtAnomaly(temperature.value)} in {temperature.year}.
      </p>
      <p className="__s9cmpx-body3" style={{ margin: '8px 0 0', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
        Temperature reflects accumulated global forcing and the response of the ocean and climate system, not only this year’s emissions.
      </p>
      <p className="__s9cmpx-body3" style={{ margin: '8px 0 0', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
        These are global figures. The sections below explore emissions by country; they do not assign warming to any country.
      </p>
      <p className="__s9cmpx-body3" style={{ margin: '8px 0 0' }}>
        <Link className="area2-link" to="/climate-correlation" style={{ fontWeight: 600 }}>Open the Temperature &amp; GHG Correlation module →</Link>
      </p>
    </section>
  );
}

export function RelationshipSection({ signal, emissionsSeries }: { signal: ClimateSignal; emissionsSeries: YearValue[] }) {
  const [view, setView] = useState<View>('time');
  const first = emissionsSeries[0]?.year;
  const last = emissionsSeries[emissionsSeries.length - 1]?.year;

  const over = useMemo(() => {
    const temps = new Map(signal.series.temperature.map((p) => [p.year, p.value]));
    return {
      x: emissionsSeries.map((p) => String(p.year)),
      emissions: emissionsSeries.map((p) => p.value / 1000), // GtCO₂ a year
      temperature: emissionsSeries.map((p) => temps.get(p.year) ?? null),
    };
  }, [signal, emissionsSeries]);

  const title = view === 'time'
    ? `CO₂ emissions and temperature anomaly, ${first}–${last}`
    : `Temperature anomaly vs cumulative CO₂, ${signal.fit.start}–${signal.fit.end}`;

  return (
    <section id={RELATIONSHIP_ANCHOR} aria-labelledby="relationship-heading" style={{ marginBottom: 16 }}>
      <style>{CHART_PANEL_STYLES + '@media (max-width: 1100px) { .overview-relationship-grid { grid-template-columns: 1fr !important; } }'}</style>
      <h2 id="relationship-heading" className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>Why the trend matters</h2>
      <div className="overview-relationship-grid" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, alignItems: 'start' }}>
        <ChartCard
          title={title}
          headingLevel={3}
          actions={<SegmentedControl name="relationship-view" items={VIEW_ITEMS} value={view} onChange={(v) => setView(v as View)} size="small" />}
        >
          <PurposeLine>
            {view === 'time'
              ? 'show how annual emissions and the temperature anomaly have moved over the same years.'
              : 'show how warming tracks the total CO₂ emitted so far, rather than any single year.'}
          </PurposeLine>
          {view === 'time' ? (
            <SyChart
              height={300}
              yTitle="GtCO₂ a year"
              y2Title="°C above 1850–1900"
              y2TickFormat=".1f"
              ariaLabel={`Bars: annual CO₂ emissions in GtCO₂, ${first} to ${last}, left axis. Line: temperature anomaly in °C above 1850–1900, right axis.`}
              series={[
                { name: 'CO₂ emissions (GtCO₂)', x: over.x, y: over.emissions, kind: 'bar', color: SERIES_ON_DARK.emissions },
                { name: 'Temperature anomaly (°C)', x: over.x, y: over.temperature, kind: 'line', yAxis: 'y2', color: SERIES_ON_DARK.temperature, showMarkers: false },
              ]}
            />
          ) : (
            <div className="climate-chart-panel">
              <ScatterLegend />
              <ClimateScatter signal={signal} />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
            {/* The only baselined series in either view is the temperature anomaly (1850–1900); emissions are plain levels. The window is in the title. */}
            <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
            <span className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
              Long-term co-movement, shown as context. No single factor or year explains warming.
            </span>
          </div>
          <details style={{ marginTop: 8 }}>
            <summary className="__s9cmpx-body4" style={{ cursor: 'pointer' }}>Sources &amp; method</summary>
            <SourceNote sources={['OWID + Global Carbon Project (emissions)', 'Berkeley Earth (temperature)', 'NOAA GML + Law Dome (CO₂ concentration)']}>
              {NOT_A_CLIMATE_MODEL} {signal.vintageCaveat ?? ''}{' '}
              <Link className="area2-link" to="/climate-correlation#methodology" style={{ fontWeight: 600 }}>Full methodology →</Link>
            </SourceNote>
          </details>
        </ChartCard>
        <WhyEmissionsMatter signal={signal} />
      </div>
    </section>
  );
}
