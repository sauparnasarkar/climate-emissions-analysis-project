import { describe, expect, it } from 'vitest';
import type { CorrelationConcentrationResponse, CorrelationEmissionsTemperatureResponse, CorrelationTemperatureResponse, SeriesPoint } from '../api/correlationTypes';
import { buildClimateSignal, eraOf, fmtAnomaly, isTemperatureAheadOfPair, latestValue, niceTicks, olsFit, pairedEndNote, pairedTemperature } from './climateSignal';

const sp = (year: number, value: number | null): SeriesPoint => ({ year, month: null, value, uncertainty: null, deseasonalized: null });
const base = { schema_version: 1, generated_at: null, note: '', caveats: [], attribution: [], source_vintage: null };

function pair(over: Partial<CorrelationEmissionsTemperatureResponse> = {}): CorrelationEmissionsTemperatureResponse {
  return {
    ...base, source: 'owid_co2', variant: 'total', baseline: 'preindustrial', window: [1850, 2024],
    x: { id: 'x', name: 'x', unit: 'Mt CO2', kind: 'cumulative', decimals: null, description: null },
    y: { id: 'y', name: 'y', unit: '°C', kind: 'anomaly', decimals: null, description: null },
    n_years: 3,
    // y = 0.5 per 1,000 Gt: temperature rises 0.5 °C for every 1,000,000 Mt
    points: [{ year: 1850, cumulative_emissions: 0, temperature: 0 }, { year: 1950, cumulative_emissions: 1_000_000, temperature: 0.5 }, { year: 2024, cumulative_emissions: 2_000_000, temperature: 1 }],
    omitted_years: [], fit: { slope: 0.52, ci95_hac: [0.48, 0.56], r_squared: 0.9, n_years: 175, start: 1850, end: 2024, unit: '°C per 1,000 GtCO2' }, fit_context: {}, warnings: [], notes: [], ...over,
  };
}
const series = (points: SeriesPoint[]): CorrelationTemperatureResponse & CorrelationConcentrationResponse => ({
  ...base, indicator: { id: 'i', name: 'i', unit: 'u', kind: 'level', decimals: null, description: null }, view: 'level', baseline: null, resolution: 'annual',
  start_year: null, end_year: null, coverage: null, points, notes: [], details: {},
});

describe('eraOf', () => {
  it('splits at 1900 and 1970', () => {
    expect([eraOf(1850), eraOf(1899), eraOf(1900), eraOf(1969), eraOf(1970), eraOf(2024)]).toEqual(['pre1900', 'pre1900', 'y1900_1969', 'y1900_1969', 'y1970plus', 'y1970plus']);
  });
});

describe('olsFit', () => {
  it('recovers an exact line and refuses degenerate input', () => {
    const f = olsFit([0, 1, 2, 3], [1, 3, 5, 7])!;
    expect(f.slope).toBeCloseTo(2);
    expect(f.intercept).toBeCloseTo(1);
    expect(olsFit([1], [1])).toBeNull();
    expect(olsFit([2, 2, 2], [1, 2, 3])).toBeNull();
  });
});

describe('latestValue', () => {
  it('skips trailing nulls and never returns a zero for a missing value', () => {
    expect(latestValue([sp(2022, 1.5), sp(2023, 1.6), sp(2024, null)])).toEqual({ value: 1.6, year: 2023 });
    expect(latestValue([sp(2024, null)])).toBeNull();
  });
});

describe('buildClimateSignal', () => {
  it('converts Mt to Gt, assigns eras, fits the line and carries the latest temperature and ppm each at its own year', () => {
    const s = buildClimateSignal(pair(), series([sp(2023, 1.4), sp(2024, 1.62)]), series([sp(2024, 424.6), sp(2025, 427.35)]))!;
    expect(s.points.map((p) => p.gt)).toEqual([0, 1000, 2000]);
    expect(s.points.map((p) => p.era)).toEqual(['pre1900', 'y1900_1969', 'y1970plus']);
    expect(s.line.y0).toBeCloseTo(0);
    expect(s.line.y1).toBeCloseTo(1);
    expect(s.fit).toMatchObject({ slope: 0.52, ciLow: 0.48, ciHigh: 0.56, nYears: 175, start: 1850, end: 2024 });
    expect(s.temperature).toEqual({ value: 1.62, year: 2024 });
    expect(s.concentration).toEqual({ value: 427.35, year: 2025 });
    expect(s.series.temperature).toEqual([{ year: 2023, value: 1.4 }, { year: 2024, value: 1.62 }]);
    expect(s.series.concentration).toEqual([{ year: 2024, value: 424.6 }, { year: 2025, value: 427.35 }]);
    expect(s.spliceYear).toBeNull();
    expect(s.ppm1850).toBeNull();
    expect(s.vintageCaveat).toBeNull();
  });

  it('carries the splice year, the 1850 concentration and the unreconciled-vintage caveat when the API provides them', () => {
    const conc = { ...series([sp(1850, 286.8), sp(2024, 424.6)]), details: { splice: { splice_year: 1959 } } };
    const s = buildClimateSignal(pair({ source_vintage: { reconciled: false, caveat: 'Based on file vintage X; unreconciled.' } }), series([sp(2024, 1.6)]), conc)!;
    expect(s.spliceYear).toBe(1959);
    expect(s.ppm1850).toBe(286.8);
    expect(s.vintageCaveat).toBe('Based on file vintage X; unreconciled.');
    // once reconciled the API's caveat is the preliminary-release note: still surfaced; with no caveat it is null
    expect(buildClimateSignal(pair({ source_vintage: { reconciled: true, caveat: 'Preliminary release.' } }), series([sp(2024, 1.6)]), conc)!.vintageCaveat).toBe('Preliminary release.');
    expect(buildClimateSignal(pair({ source_vintage: { reconciled: true, caveat: null } }), series([sp(2024, 1.6)]), conc)!.vintageCaveat).toBeNull();
  });

  it('returns null rather than a partial banner when any input is missing', () => {
    const t = series([sp(2024, 1.6)]);
    const c = series([sp(2024, 424)]);
    expect(buildClimateSignal(pair({ fit: null }), t, c)).toBeNull();
    expect(buildClimateSignal(pair({ fit: { slope: 0.5, ci95_hac: [], start: 1850, end: 2024, n_years: 3 } }), t, c)).toBeNull();
    expect(buildClimateSignal(pair(), series([sp(2024, null)]), c)).toBeNull();
    expect(buildClimateSignal(pair(), t, series([]))).toBeNull();
    expect(buildClimateSignal(pair({ points: [] }), t, c)).toBeNull();
  });
});

describe('formatting helpers', () => {
  it('formats anomalies with an explicit sign and builds axis ticks', () => {
    expect(fmtAnomaly(1.617)).toBe('+1.62 °C');
    expect(fmtAnomaly(-0.13)).toBe('−0.13 °C');
    expect(niceTicks(1.6, 0.5, -0.4)).toEqual([0, 0.5, 1, 1.5]);
    expect(niceTicks(2700, 500)).toEqual([0, 500, 1000, 1500, 2000, 2500]);
  });
});

describe('temperature newer than the paired chart (decision 86)', () => {
  const conc = series([sp(2025, 427.4)]);
  it('says so when the latest temperature year is after the pair ends (emissions data ends first)', () => {
    const s = buildClimateSignal(pair(), series([sp(2024, 1.55), sp(2025, 1.45)]), conc)!;
    expect(isTemperatureAheadOfPair(s)).toBe(true);
    expect(pairedEndNote(s)).toBe('The chart ends at 2024, the last year with CO₂ emissions data; the latest temperature (2025, +1.45 °C) has no emissions to pair with.');
  });
  it('is silent when temperature and the pair end in the same year', () => {
    const s = buildClimateSignal(pair(), series([sp(2023, 1.4), sp(2024, 1.55)]), conc)!;
    expect(isTemperatureAheadOfPair(s)).toBe(false);
    expect(pairedEndNote(s)).toBeNull();
  });
});

describe('pairedTemperature (decision 86)', () => {
  it('is the chart\'s own last point, not the latest temperature in the series', () => {
    const s = buildClimateSignal(pair(), series([sp(2024, 1.55), sp(2025, 1.45)]), series([sp(2025, 427.4)]))!;
    expect(s.temperature).toEqual({ value: 1.45, year: 2025 });
    expect(pairedTemperature(s)).toEqual({ value: 1, year: 2024 }); // pair() ends 2024 at y = 1
  });
});
