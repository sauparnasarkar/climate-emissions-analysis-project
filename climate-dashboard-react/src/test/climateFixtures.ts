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
export const CONCENTRATION = series([sp(1850, 286.8), sp(1959, 315.9), sp(1970, 325.68), sp(1980, 338.91), sp(1990, 354.45), sp(2024, 424.6)], { splice: { splice_year: 1959, overlap_years: [1959, 2004], gap_at_splice_ppm: -0.28, max_abs_overlap_gap_ppm: 3.9, mean_overlap_gap_ppm: -2.33 } });

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

const gasValues = (co2: number, ch4: number, n2o: number, fgas: number) => {
  const total = co2 + ch4 + n2o + fgas;
  return [['co2', 'CO₂', co2], ['ch4', 'CH₄', ch4], ['n2o', 'N₂O', n2o], ['fgas', 'Fluorinated gases', fgas]].map(([gas, name, v]) => ({ gas, name, mtco2e: v, share_pct: ((v as number) / total) * 100 }));
};
const compYear = (year: number, ...v: [number, number, number, number]) => ({ year, gases_included: ['co2', 'ch4', 'n2o', 'fgas'], components_total_mtco2e: v.reduce((a, b) => a + b, 0), national_total_mtco2e: v.reduce((a, b) => a + b, 0), residual_pct: 0.052, values: gasValues(...v) });

/** `/ghg-composition` shaped like the real response: four gases, a few years, an incomplete trailing year excluded, the API's caveats. */
export const COMPOSITION = {
  ...env,
  name: 'Global greenhouse-gas composition',
  basis: 'PRIMAP-hist national total greenhouse-gas emissions in CO2-equivalent terms, IPCC AR5 100-year global-warming potentials (CH4 28, N2O 265)',
  units: 'MtCO2e (CO2 in Mt CO2)',
  gases: [{ id: 'co2', name: 'CO₂' }, { id: 'ch4', name: 'CH₄' }, { id: 'n2o', name: 'N₂O' }, { id: 'fgas', name: 'Fluorinated gases' }],
  coverage: [1750, 2024], start_year: 1970, end_year: null, year: null,
  years: [compYear(1970, 15000, 6000, 1500, 100), compYear(2000, 26000, 7500, 2500, 800), compYear(2024, 37974, 8422, 2727, 1426)],
  reconciliation: { max_abs_residual_pct: 0.213, tolerance_pct: 1.0, note: 'components vs national total' }, excluded_incomplete_years: [2025], notes: [],
  caveats: [
    'Excludes international aviation and shipping and land-use change (national totals), so the share of CO2 in particular excludes deforestation.',
    "Shares are each gas's part of the sum of the gases included for that year, so they sum to 100.",
    'PRIMAP-hist is a composite of country-reported and third-party data harmonised into one series.',
    'Trailing years that are incomplete in the no-extrapolation file (v2.8: 2025) are excluded, not extrapolated.',
    "PRIMAP-hist licence: CC BY-NC-SA 4.0. Non-commercial use only.",
  ],
} as unknown as import('../api/correlationTypes').CorrelationGhgCompositionResponse;

const shareRow = (rank: number, country: string, name: string, share: number) => ({ rank, country, name, cumulative_mt: share * 1000, share_pct: share, annual_mt: 1, annual_share_pct: 1 });
/** `/country-share?all_countries=true`: ranked rows. */
export const COUNTRY_SNAPSHOT = {
  ...env, name: 'n', method: 'm', source: 'owid_co2', gas_scope: 'co2', label: 'OWID fossil + cement CO2', unit: 'Mt CO2', mode: 'ranking', year: 2024, limit: null, start_year: null, end_year: null,
  coverage: [1850, 2024], cumulative_from: 1750, total_cumulative_mt: 1, annual_total_mt: 1, series: [], denominator: null, reconciliation: null, details: {}, notes: [],
  rows: [shareRow(1, 'USA', 'United States', 24.1), shareRow(2, 'CHN', 'China', 15.8), shareRow(3, 'RUS', 'Russia', 6.8), shareRow(4, 'DEU', 'Germany', 5.3), shareRow(5, 'GBR', 'United Kingdom', 4.4), shareRow(6, 'JPN', 'Japan', 3.9)],
} as unknown as import('../api/correlationTypes').CorrelationCountryShareResponse;

/** `/meta` shaped like the real response: dataset-level sources (two OWID rows, two PRIMAP rows, Berkeley, two NOAA/Law Dome, a derived crosswalk), baselines, offset, the totals note. */
export const META = {
  ...env, name: 'meta',
  sources: [
    { id: 'co2_concentration_annual', source: 'NOAA GML Mauna Loa (1959+) spliced to Law Dome ice-core/firn spline (pre-1959)', license: 'NOAA GML: public domain, citation requested. Law Dome: cite Etheridge et al. 2010.', coverage: [1750, 2025], retrieved_at: '2026-10-02T03:33:27+00:00', source_release: { noaa_last_modified: '2026-09-08T14:44:18+00:00' } },
    { id: 'co2_concentration_monthly_mlo', source: 'NOAA GML Mauna Loa monthly mean', license: 'NOAA GML: public domain, citation requested.', coverage: [1958, 2026], retrieved_at: '2026-10-02T03:33:27+00:00', source_release: { noaa_last_modified: '2026-09-08T14:44:18+00:00' } },
    { id: 'country_crosswalk', source: 'Derived: PRIMAP-hist area codes x OWID iso_code/country', license: 'Derived metadata', retrieved_at: '2026-10-02T13:40:57+00:00' },
    { id: 'owid_country_co2', source: 'Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)', license: "CC BY 4.0 for OWID's compilation. Cite OWID and the Global Carbon Budget.", coverage: [1750, 2024], retrieved_at: '2026-07-18T15:32:10+00:00' },
    { id: 'owid_world_co2_annual', source: 'Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)', license: "CC BY 4.0 for OWID's compilation. Cite OWID and the Global Carbon Budget.", coverage: [1750, 2024], retrieved_at: '2026-07-18T15:32:10+00:00' },
    { id: 'primap_country_annual', source: 'PRIMAP-hist v2.8 (Gütschow & Pflüger)', license: 'CC BY-NC-SA 4.0. Non-commercial use only. Upstream sources have their own terms -- not yet verified.', coverage: [1750, 2024], retrieved_at: '2026-10-02T13:40:57+00:00', source_release: { published: '2026-09-29', version: 'v2.8' } },
    { id: 'primap_global_composition_annual', source: 'PRIMAP-hist v2.8 (Gütschow & Pflüger)', license: 'CC BY-NC-SA 4.0. Non-commercial use only. Upstream sources have their own terms -- not yet verified.', coverage: [1750, 2024], retrieved_at: '2026-10-02T13:40:57+00:00', source_release: { published: '2026-09-29', version: 'v2.8' } },
    { id: 'temperature_anomaly_annual', source: 'Berkeley Earth Land/Ocean global temperature (annual)', license: 'Berkeley Earth data: CC BY 4.0 (cite Rohde & Hausfather 2020).', coverage: [1850, 2024], retrieved_at: '2026-10-02T03:33:28+00:00', source_release: { http_last_modified: '2025-01-10T04:48:46+00:00' } },
  ],
  baselines: {}, temperature_offset: { derivation: 'Mean of the annual anomaly over 1850-1900.', reference_period: [1850, 1900], std_c: 0.1252, value_c: -0.3062, years: 51 },
  two_global_totals: 'Two different global totals are used on purpose. The regression X-variable is OWID\'s full World row, which includes international aviation and shipping. The country-share denominator is the sum of national emissions, which excludes those bunkers.',
  source_baseline_matrix: [], indicators: [], outputs: {}, pipeline_last_run: null, endpoints: [], freshness: {},
} as unknown as import('../api/correlationTypes').CorrelationMetaResponse;
