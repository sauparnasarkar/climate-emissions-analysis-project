import type { CorrelationConcentrationResponse, CorrelationEmissionsTemperatureResponse, CorrelationTemperatureResponse, SeriesPoint } from '../api/correlationTypes';

// Small, hand-checkable correlation-API responses for page tests (the real shapes, minimal content).
const env = { schema_version: 1, generated_at: null, note: '', caveats: [], attribution: [], source_vintage: null };
export const sp = (year: number, value: number | null): SeriesPoint => ({ year, month: null, value, uncertainty: null, deseasonalized: null });
const indicator = { id: 'i', name: 'i', unit: 'u', kind: 'level', decimals: null, description: null };

export const PAIR: CorrelationEmissionsTemperatureResponse = {
  ...env, source: 'owid_co2', variant: 'total', baseline: 'preindustrial', window: [1850, 2024], x: indicator, y: indicator, n_years: 175,
  points: [{ year: 1850, cumulative_emissions: 2_910, temperature: -0.13 }, { year: 1950, cumulative_emissions: 900_000, temperature: 0.1 }, { year: 2024, cumulative_emissions: 2_751_504, temperature: 1.62 }],
  omitted_years: [], fit: { slope: 0.5196, ci95_hac: [0.48, 0.559], r_squared: 0.9, n_years: 175, start: 1850, end: 2024, unit: '°C per 1,000 GtCO2' }, fit_context: {}, warnings: [], notes: [],
  source_vintage: { reconciled: false, caveat: 'Based on Berkeley Earth file vintage 2025-01-10; a possible ~0.1 °C discrepancy is not yet reconciled.' },
};

export const series = (points: SeriesPoint[], details: Record<string, unknown> = {}): CorrelationTemperatureResponse & CorrelationConcentrationResponse => ({
  ...env, indicator, view: 'level', baseline: null, resolution: 'annual', start_year: null, end_year: null, coverage: null, points, notes: [], details,
});

export const TEMPERATURE = series([sp(2022, 1.4), sp(2023, 1.5), sp(2024, 1.617)]);
export const TEMPERATURE_MEAN5Y = series([sp(2023, 1.35), sp(2024, 1.39)]);
export const CONCENTRATION = series([sp(1850, 286.8), sp(1959, 315.9), sp(2024, 424.6)], { splice: { splice_year: 1959 } });
