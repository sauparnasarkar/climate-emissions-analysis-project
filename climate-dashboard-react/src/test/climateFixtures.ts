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
    { id: 'temperature_anomaly_annual', source: 'Berkeley Earth Land/Ocean global temperature (annual)', license: "CC BY-NC 4.0 International (Berkeley Earth's data page: 'in general ... for non-commercial use only'; commercial use needs a licence from admin@berkeleyearth.org). Attribution to Berkeley Earth, including a reference to www.berkeleyearth.org. Cite Rohde & Hausfather 2020, ESSD 12, 3469-3479, doi:10.5194/essd-12-3469-2020.", coverage: [1850, 2024], retrieved_at: '2026-10-02T03:33:28+00:00', source_release: { http_last_modified: '2025-01-10T04:48:46+00:00' } },
  ],
  baselines: {}, temperature_offset: { derivation: 'Mean of the annual anomaly over 1850-1900.', reference_period: [1850, 1900], std_c: 0.1252, value_c: -0.3062, years: 51 },
  // the API's TWO_GLOBAL_TOTALS constant (api/routers/correlation.py), word for word
  two_global_totals: "Two different global totals are used on purpose. The emissions-temperature regression's X-variable is OWID's full World row, which includes international aviation and shipping (they are real atmospheric loading, so excluding them would understate cumulative CO2). The country-share denominator is the sum of national emissions, which excludes those bunkers, so country shares sum to 100% of territorial emissions. The two totals therefore differ by the international transport line, published as its own indicator.",
  source_baseline_matrix: [], indicators: [], outputs: {}, pipeline_last_run: null, endpoints: [], freshness: {},
} as unknown as import('../api/correlationTypes').CorrelationMetaResponse;

/** The headline `/emissions-temperature` response with the real `fit_context` (values as the API serves them for the 1850–2024 total-CO₂ fit). */
export const HEADLINE_PAIR = {
  ...PAIR,
  x: { id: 'owid_total_co2_world_cumulative_mt', name: 'World cumulative total anthropogenic CO2 since 1850', unit: 'Mt CO2', kind: 'cumulative', decimals: 0, description: "Running total of total anthropogenic CO2 (fossil + cement + land-use) from 1850, the first year of the land-use series: the headline TCRE-style regression's X-variable (decision 40). Not comparable to the 1750-based fossil cumulative; a regression slope is unaffected by the choice of start year." },
  y: { id: 'temperature_anomaly_1850_1900_c', name: 'Global temperature anomaly (vs 1850-1900)', unit: '°C', kind: 'anomaly', decimals: 2, description: 'Berkeley Earth land+ocean annual anomaly relative to the computed 1850-1900 mean.' },
  fit: { start: 1850, end: 2024, n_years: 175, slope: 0.5195877622595872, ci95_hac: [0.480074110455886, 0.5591014140632885], r_squared: 0.9034656057333824, maxlags: 8, unit: '°C per 1,000 GtCO2', label: 'Total anthropogenic CO2 (fossil + cement + land-use change)' },
  fit_context: {
    definition: 'total anthropogenic CO2 since 1850',
    method: 'OLS with intercept; Newey-West (HAC) standard errors',
    methodology: "Derived from OWID cumulative CO2 from fossil fuels, cement and land-use change (Global Carbon Project), regressed against the Berkeley Earth anomaly. A simplified, data-driven analog to the IPCC's TCRE (AR6 best estimate about 0.45 °C per 1,000 GtCO2, very likely range 0.27-0.63), not a restatement of it: this regression also absorbs warming from non-CO2 gases and aerosols that varies with CO2, uses one observed climate history rather than a multi-model ensemble, and depends on land-use emission estimates that are themselves uncertain.",
    fit: { slope: 0.5195877622595872, intercept: -0.09861679576048252, r_squared: 0.9034656057333824, n: 175, se_ols: 0.012912819729073084, se_hac: 0.0201603968824835, ci95_hac: [0.480074110455886, 0.5591014140632885], maxlags: 8, residual_lag1_autocorrelation: 0.5501525115901242, durbin_watson: 0.8870370587990891, slope_per_1000_gtc: 1.9037996694098889, rule: 'maxlags = floor(1.5 * n^(1/3)); Bartlett kernel; 95% CI from the HAC standard error (normal)' },
    hac_sensitivity: [
      { maxlags: 4, se_hac: 0.017728010719128807, ci95_hac: [0.48484149973255475, 0.5543340247866198] },
      { maxlags: 8, se_hac: 0.0201603968824835, ci95_hac: [0.480074110455886, 0.5591014140632885] },
      { maxlags: 16, se_hac: 0.022919020147949144, ci95_hac: [0.47466730820865904, 0.5645082163105154] },
    ],
    land_use_sensitivity: [{ land_use_scale: 0.7, slope: 0.5825373490288306 }, { land_use_scale: 1.0, slope: 0.5195877622595872 }, { land_use_scale: 1.3, slope: 0.46815075945103013 }],
    land_use_weight_scan: {
      definition: 'x = cumulative fossil + cement CO2 + weight * cumulative land-use CO2 (weight 0 = the fossil-only variant, 1 = the headline)',
      weights: [
        { land_use_weight: 0.0, slope: 0.7973293983385148, r_squared: 0.908501512844093, holdout_split_year: 2000, holdout_train_slope: 0.848673053689585, holdout_rmse_c: 0.1262039938991461 },
        { land_use_weight: 1.0, slope: 0.5195877622595872, r_squared: 0.9034656057333824, holdout_split_year: 2000, holdout_train_slope: 0.4663116454206641, holdout_rmse_c: 0.1739057396500447 },
      ],
      note: 'Shows how the out-of-sample error responds to the weight given to land-use CO2. It is published to show the shape of the trade-off, not to choose a weight: a weight picked to minimise this error would be tuned to the holdout.',
    },
    vs_ar6: { within_very_likely_range: true, ci_overlaps_range: true, ratio_to_best_estimate: 1.1546394716879715 },
    ar6_reference: { unit: '°C per 1,000 GtCO2', best_estimate: 0.45, very_likely_range: [0.27, 0.63], as_per_1000_gtc: { best_estimate: 1.65, very_likely_range: [1.0, 2.3] }, source: 'IPCC AR6 WGI: transient climate response to cumulative CO2 emissions (very likely range 1.0-2.3 °C per 1,000 GtC, best estimate 1.65).', note: "Derived from CO2-only forcing in Earth-system models with land-use emissions included; this platform's figure is a simplified, data-driven analog, not a restatement." },
    fit_quality_note: { text: 'HELD FOR THE OWNER (decision 41): must never be rendered' },
    stability: {
      method: 'moving-block bootstrap of the regression residuals with the predictor held fixed (distinct from the HAC standard errors), plus decade holdouts',
      seed: 20261002, resamples: 2000, primary_block_years: 10,
      bootstrap: { block_years: 10, ci95: [0.47284201673187126, 0.5676873314864159], median: 0.5191847640712342 },
      block_length_sensitivity: [
        { block_years: 5, ci95: [0.48076602480369246, 0.5596083822887195], median: 0.5193817467836532 },
        { block_years: 10, ci95: [0.47284201673187126, 0.5676873314864159], median: 0.5191847640712342 },
      ],
      block_length_unavailable: [], hac_ci95: [0.480074110455886, 0.5591014140632885], bootstrap_vs_hac_width_ratio: 1.2001588112600172,
      holdouts: [
        { split_year: 1980, train_range: [1850, 1979], test_range: [1980, 2024], n_train: 130, n_test: 45, train_slope: 0.4072975757205395, rmse_c: 0.22878953625771423, mae_c: 0.19151331778034567, mean_error_c: 0.18647397438103566, baseline_rmse_train_mean_c: 0.854753533023203 },
        { split_year: 2010, train_range: [1850, 2009], test_range: [2010, 2024], n_train: 160, n_test: 15, train_slope: 0.4897501707762177, rmse_c: 0.16404416870528904, mae_c: 0.12270106778260922, mean_error_c: 0.11285156366925797, baseline_rmse_train_mean_c: 1.0205161979858834 },
      ],
      summary: "Resampling the model's residuals in 10-year blocks (2,000 resamples, seed 20261002) gives a 95% interval for the slope of 0.473 to 0.568, against 0.480 to 0.559 from the Newey-West standard errors; across block lengths of 5 to 30 years the interval's lower bound stays between 0.462 and 0.481 and its upper bound between 0.560 and 0.579. Estimated from later start years (1850, 1900, 1950, 1970) the slope ranges from 0.520 to 0.638. Fitting only on years before 2000 and predicting 2000-2024 gives a slope of 0.466 and an out-of-sample error (RMSE) of 0.174 °C, against 0.956 °C for simply predicting the earlier average.",
      note: 'These are published as measured; no pass/fail judgement is made.',
    },
  },
  attribution: [
    { series: 'owid_world_co2_annual', source: 'Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)', license: "CC BY 4.0 for OWID's compilation (OWID's README). Cite OWID and the Global Carbon Budget.", citations: ['Our World in Data, CO2 and Greenhouse Gas Emissions (https://github.com/owid/co2-data), CC BY 4.0.', 'Friedlingstein, P. et al., Global Carbon Budget (Global Carbon Project), the source of the fossil CO2 and land-use-change CO2 data.'], required_citation_format: 'Global Carbon Project. (<year>). Supplemental data of Global Carbon Budget <year> (Version <n>) [Data set]. Global Carbon Project.', land_use_license_note: "Land-use CO2 data originates from the Global Carbon Project via OWID. No formal license (e.g., CC BY) is stated on the Global Carbon Project's data page; use is conditional on citing the original source per their stated terms." },
    { series: 'temperature_anomaly_annual', source: 'Berkeley Earth Land/Ocean global temperature (annual)', license: "CC BY-NC 4.0 International (Berkeley Earth's data page: 'in general ... for non-commercial use only'; commercial use needs a licence from admin@berkeleyearth.org). Attribution to Berkeley Earth, including a reference to www.berkeleyearth.org. Cite Rohde & Hausfather 2020, ESSD 12, 3469-3479, doi:10.5194/essd-12-3469-2020." },
  ],
} as unknown as CorrelationEmissionsTemperatureResponse;
