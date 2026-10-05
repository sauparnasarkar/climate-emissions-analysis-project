import type {
  CountriesResponse,
  CountryProfileResponse,
  EtsParametersResponse,
  ExplorerDataResponse,
  ExplorerMetaResponse,
  FeatureImportanceResponse,
  ForecastCountryResponse,
  ForecastSummaryResponse,
  HistoricalDecadeCompositionResponse,
  HistoricalTimeseriesResponse,
  ModelComparisonResponse,
  OverviewResponse,
  ScenarioCompareResponse,
  ScenarioCumulativeResponse,
  ScenarioTimeseriesResponse,
  WorldMapTimeSeries,
} from './types';
import type {
  ConcentrationView,
  CorrelationConcentrationResponse,
  CorrelationCountryShareResponse,
  CorrelationEmissionsTemperatureResponse,
  CorrelationGhgCompositionResponse,
  CorrelationMetaResponse,
  CorrelationScenarioTemperatureResponse,
  CorrelationTemperatureResponse,
  IndexBaseline,
  PairSource,
  PairVariant,
  ScenarioLine,
  ScenarioName,
  SeriesResolution,
  TemperatureBaseline,
  TemperatureView,
} from './correlationTypes';
import { ApiError } from './types';

async function get<T>(path: string): Promise<T> {
  // BASE_URL is "/" locally and "/ghg-emissions-analysis/" in the tunnel deployment
  // (see vite.config.ts DEPLOY_BASE_PATH) — Cloudflare Tunnel forwards the full
  // request path to the origin, so /api must be nested under it in production.
  const res = await fetch(`${import.meta.env.BASE_URL}api${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

function buildExplorerParams(countries: string[], yearMin: number | null, yearMax: number | null, columns: string[]): URLSearchParams {
  const params = new URLSearchParams();
  countries.forEach((c) => params.append('countries', c));
  if (yearMin !== null) params.set('year_min', String(yearMin));
  if (yearMax !== null) params.set('year_max', String(yearMax));
  columns.forEach((c) => params.append('columns', c));
  return params;
}

/** Appends only the params the caller set, so an omitted one falls to the endpoint's own default. */
function withParams(path: string, entries: Array<[string, string | number | undefined]>): string {
  const params = new URLSearchParams();
  for (const [k, v] of entries) if (v !== undefined) params.set(k, String(v));
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export const api = {
  overview: (countries?: string[]) => {
    if (!countries || countries.length === 0) return get<OverviewResponse>('/overview');
    const params = new URLSearchParams();
    countries.forEach((c) => params.append('countries', c));
    return get<OverviewResponse>(`/overview?${params}`);
  },

  // Selection-invariant -- no `countries` param. Fetched once regardless of how many times
  // the user changes their country selection (SPEC.md §5.17.1).
  // `startYear` defaults server-side to 1990; the Area 2 globe asks for 1970 (requirements §2.6). Same response shape.
  worldMapSeries: (startYear?: number) => get<WorldMapTimeSeries>(startYear === undefined ? '/overview/world-map-series' : `/overview/world-map-series?start_year=${startYear}`),

  listCountries: () => get<CountriesResponse>('/countries'),

  historicalTimeseries: (countries: string[], gas: string) => {
    const params = new URLSearchParams();
    countries.forEach((c) => params.append('countries', c));
    params.set('gas', gas);
    return get<HistoricalTimeseriesResponse>(`/historical/timeseries?${params}`);
  },

  historicalDecadeComposition: (countries: string[]) => {
    const params = new URLSearchParams();
    countries.forEach((c) => params.append('countries', c));
    return get<HistoricalDecadeCompositionResponse>(`/historical/decade-composition?${params}`);
  },

  countryProfile: (country: string) => get<CountryProfileResponse>(`/countries/${encodeURIComponent(country)}/profile`),

  forecast: (country: string) => get<ForecastCountryResponse>(`/forecasts/${encodeURIComponent(country)}`),

  forecastSummary: (scope: 'featured' | 'expanded' = 'featured') =>
    get<ForecastSummaryResponse>(`/forecasts/summary?scope=${scope}`),

  modelComparison: () => get<ModelComparisonResponse>('/forecasts/model-comparison'),

  etsParameters: () => get<EtsParametersResponse>('/forecasts/ets-parameters'),

  featureImportance: () => get<FeatureImportanceResponse>('/forecasts/feature-importance'),

  scenarioTimeseries: (view: 'single' | 'global', country?: string) => {
    const params = new URLSearchParams({ view });
    if (country) params.set('country', country);
    return get<ScenarioTimeseriesResponse>(`/scenarios/timeseries?${params}`);
  },

  scenarioCumulative: (sortBy: string) => get<ScenarioCumulativeResponse>(`/scenarios/cumulative?sort_by=${encodeURIComponent(sortBy)}`),

  scenarioCompare: (countries: string[]) => {
    const params = new URLSearchParams();
    countries.forEach((c) => params.append('countries', c));
    return get<ScenarioCompareResponse>(`/scenarios/compare?${params}`);
  },

  explorerMeta: () => get<ExplorerMetaResponse>('/explorer/meta'),

  explorerData: (
    countries: string[],
    yearMin: number | null,
    yearMax: number | null,
    columns: string[],
    page: number,
    pageSize: number,
  ) => {
    const params = buildExplorerParams(countries, yearMin, yearMax, columns);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    return get<ExplorerDataResponse>(`/explorer/data?${params}`);
  },

  explorerSummary: (countries: string[], yearMin: number | null, yearMax: number | null, columns: string[]) =>
    get<ModelComparisonResponse>(`/explorer/summary?${buildExplorerParams(countries, yearMin, yearMax, columns)}`),

  explorerDownloadUrl: (countries: string[], yearMin: number | null, yearMax: number | null, columns: string[]) =>
    `${import.meta.env.BASE_URL}api/explorer/download?${buildExplorerParams(countries, yearMin, yearMax, columns)}`,

  // Area 2 correlation domain (ENHANCEMENTS.md Release 21). Read-only over the pipeline's outputs;
  // unsupported source/baseline combinations are rejected by the API with a 422, never substituted.
  correlationMeta: () => get<CorrelationMetaResponse>('/correlation/meta'),

  correlationConcentration: (
    opts: { view?: ConcentrationView; baseline?: IndexBaseline; resolution?: SeriesResolution; startYear?: number; endYear?: number } = {},
  ) =>
    get<CorrelationConcentrationResponse>(
      withParams('/correlation/concentration', [
        ['view', opts.view], ['baseline', opts.baseline], ['resolution', opts.resolution],
        ['start_year', opts.startYear], ['end_year', opts.endYear],
      ]),
    ),

  correlationTemperature: (opts: { view?: TemperatureView; baseline?: TemperatureBaseline; startYear?: number; endYear?: number } = {}) =>
    get<CorrelationTemperatureResponse>(
      withParams('/correlation/temperature', [
        ['view', opts.view], ['baseline', opts.baseline], ['start_year', opts.startYear], ['end_year', opts.endYear],
      ]),
    ),

  correlationEmissionsTemperature: (opts: { source?: PairSource; baseline?: IndexBaseline; variant?: PairVariant } = {}) =>
    get<CorrelationEmissionsTemperatureResponse>(
      withParams('/correlation/emissions-temperature', [['source', opts.source], ['baseline', opts.baseline], ['variant', opts.variant]]),
    ),

  correlationGhgComposition: (opts: { startYear?: number; endYear?: number; year?: number } = {}) =>
    get<CorrelationGhgCompositionResponse>(
      withParams('/correlation/ghg-composition', [['start_year', opts.startYear], ['end_year', opts.endYear], ['year', opts.year]]),
    ),

  // A ranking for one `year` (`limit` ≤ 50, or `allCountries` for every country), or a series for
  // `countries` (at most 10, optionally bounded by start/end year) -- the API rejects combining them.
  correlationCountryShare: (
    opts: { source?: string; gasScope?: string; year?: number; limit?: number; allCountries?: boolean; countries?: string[]; startYear?: number; endYear?: number } = {},
  ) => {
    const params = new URLSearchParams();
    const set = (k: string, v: string | number | undefined) => v !== undefined && params.set(k, String(v));
    set('source', opts.source); set('gas_scope', opts.gasScope); set('year', opts.year); set('limit', opts.limit);
    set('start_year', opts.startYear); set('end_year', opts.endYear);
    if (opts.allCountries) params.set('all_countries', 'true');
    opts.countries?.forEach((c) => params.append('countries', c));
    const qs = params.toString();
    return get<CorrelationCountryShareResponse>(qs ? `/correlation/country-share?${qs}` : '/correlation/country-share');
  },

  correlationScenarioTemperature: (opts: { scenarios?: ScenarioName[]; line?: ScenarioLine } = {}) => {
    const params = new URLSearchParams();
    opts.scenarios?.forEach((s) => params.append('scenario', s));
    if (opts.line) params.set('line', opts.line);
    const qs = params.toString();
    return get<CorrelationScenarioTemperatureResponse>(qs ? `/correlation/scenario-temperature?${qs}` : '/correlation/scenario-temperature');
  },
};
