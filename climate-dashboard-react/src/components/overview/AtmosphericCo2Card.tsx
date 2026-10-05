import { fmtPct } from '../../lib/landingData';
import type { YearValue } from '../../lib/climateSignal';
import { SERIES_STYLES } from '../climate/seriesStyles';
import { Sparkline } from '../landing/Sparkline';

export interface ConcentrationContext {
  /** Annual mean CO₂, ppm */
  series: YearValue[];
  /** First year of NOAA's direct measurements (the ice core before it) */
  spliceYear: number | null;
  /** Pre-industrial reference, ppm */
  ppm1850: number | null;
}

/** The map's side card (Area 2, requirements §2.2/§2.6): atmospheric CO₂ for the SAME year the map shows. A stock, not a flow, so it is one
 * global figure that does not change with the Absolute/Cumulative mode and is never split by country (says so). Everything from the API. */
export function AtmosphericCo2Card({ year, concentration }: { year: number; concentration: ConcentrationContext }) {
  const { series, spliceYear, ppm1850 } = concentration;
  const now = series.find((p) => p.year === year);
  const since = series.filter((p) => p.year >= 1850);
  const delta = now && ppm1850 ? now.value - ppm1850 : null;
  return (
    <div className="series--concentration" style={{ background: 'var(--__s9cmpx-static-background-weak)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, padding: '10px 12px' }}>
      <style>{SERIES_STYLES}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span className="__s9cmpx-label3">{`Atmospheric CO₂ · ${year}`}</span>
        <span style={{ fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)', fontSize: 10, letterSpacing: '.08em', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>GLOBAL</span>
      </div>
      <div className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums' }}>{now ? `${now.value.toFixed(1)} ppm` : '—'}</div>
      {delta != null && ppm1850 != null && (
        <div className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
          {`${delta >= 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)} ppm (${fmtPct((delta / ppm1850) * 100)}) since 1850`}
        </div>
      )}
      <div className="series-spark" style={{ margin: '6px 0 2px' }}><Sparkline values={since} markerYear={spliceYear} highlightYear={year} /></div>
      <div className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
        {spliceYear != null ? `Law Dome ice core to ${spliceYear - 1} · NOAA Mauna Loa from ${spliceYear}. ` : ''}One global value: concentration is not split by country.
      </div>
    </div>
  );
}
