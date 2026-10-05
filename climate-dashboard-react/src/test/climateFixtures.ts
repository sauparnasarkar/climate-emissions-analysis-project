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
export const CONCENTRATION = series([sp(1850, 286.8), sp(1959, 315.9), sp(1970, 325.68), sp(1980, 338.91), sp(1990, 354.45), sp(2024, 424.6)], { splice: { splice_year: 1959 } });

/** `/emissions-temperature?source=primap_ghg` shaped like the real response: 1970 onward, its own fit, stability and caveats. */
export const ALL_GAS_PAIR = {
  ...PAIR,
  source: 'primap_ghg', variant: null, baseline: '1970', window: [1970, 2024], n_years: 55,
  x: { id: 'primap_ghg_total_cumulative_mtco2e', name: 'Cumulative total GHG emissions, national (PRIMAP-hist)', unit: 'MtCO2e', kind: 'cumulative', decimals: 0, description: 'Running total of the PRIMAP-hist national total from its first year.' },
  points: [{ year: 1970, cumulative_emissions: 900_769, temperature: 0.32 }, { year: 1997, cumulative_emissions: 1_500_000, temperature: 0.62 }, { year: 2024, cumulative_emissions: 2_300_000, temperature: 1.62 }],
  fit: { start: 1970, end: 2024, n_years: 55, slope: 0.5793, ci95_hac: [0.5327, 0.6259], r_squared: 0.9165, unit: '°C per 1,000 GtCO2e', label: 'Recent all-gas relationship: all gases, national totals, 1970 onward' },
  fit_context: { stability: { bootstrap: { block_years: 10, ci95: [0.5393, 0.619], median: 0.5792 }, summary: 'Resampling the model\'s residuals in 10-year blocks gives a 95% interval of 0.539 to 0.619.' } },
  caveats: [
    'This describes a long-run statistical relationship. It is not a complete climate model.',
    'This view uses PRIMAP-hist national totals in CO2-equivalent terms. It covers a short window, and a steadily rising cumulative series is strongly correlated with time.',
    'CO2-equivalent weights use the AR5 100-year global-warming potentials; short-lived gases do not accumulate like CO2.',
    'Years excluded because PRIMAP-hist\'s reporting for them is incomplete: 2025.',
    'PRIMAP-hist licence: CC BY-NC-SA 4.0. Non-commercial use only.',
    'Based on Berkeley Earth file vintage 2025-01-10.',
  ],
  omitted_years: [{ year: 2025, reason: 'incomplete' }],
} as unknown as CorrelationEmissionsTemperatureResponse;
