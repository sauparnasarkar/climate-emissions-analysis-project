import type {
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
  ScenarioCumulativeResponse,
  ScenarioTimeseriesResponse,
} from './types';
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

export const api = {
  overview: () => get<OverviewResponse>('/overview'),

  historicalTimeseries: (countries: string[], gas: string) => {
    const params = new URLSearchParams();
    countries.forEach((c) => params.append('countries', c));
    params.set('gas', gas);
    return get<HistoricalTimeseriesResponse>(`/historical/timeseries?${params}`);
  },

  historicalDecadeComposition: () => get<HistoricalDecadeCompositionResponse>('/historical/decade-composition'),

  countryProfile: (country: string) => get<CountryProfileResponse>(`/countries/${encodeURIComponent(country)}/profile`),

  forecast: (country: string) => get<ForecastCountryResponse>(`/forecasts/${encodeURIComponent(country)}`),

  forecastSummary: () => get<ForecastSummaryResponse>('/forecasts/summary'),

  modelComparison: () => get<ModelComparisonResponse>('/forecasts/model-comparison'),

  etsParameters: () => get<EtsParametersResponse>('/forecasts/ets-parameters'),

  featureImportance: () => get<FeatureImportanceResponse>('/forecasts/feature-importance'),

  scenarioTimeseries: (view: 'single' | 'global', country?: string) => {
    const params = new URLSearchParams({ view });
    if (country) params.set('country', country);
    return get<ScenarioTimeseriesResponse>(`/scenarios/timeseries?${params}`);
  },

  scenarioCumulative: (sortBy: string) => get<ScenarioCumulativeResponse>(`/scenarios/cumulative?sort_by=${encodeURIComponent(sortBy)}`),

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
};
