import type {
  CountryProfileResponse,
  EtsParametersResponse,
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
  const res = await fetch(`/api${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
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
};
