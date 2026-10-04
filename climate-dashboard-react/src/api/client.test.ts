import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { ApiError } from './types';

function mockFetchOnce(body: unknown, init: { ok?: boolean; status?: number; statusText?: string } = {}) {
  const { ok = true, status = 200, statusText = 'OK' } = init;
  const response = {
    ok,
    status,
    statusText,
    json: () => Promise.resolve(body),
  } as Response;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
  return response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('overview() with no countries fetches plain /api/overview', async () => {
    mockFetchOnce({ latest_year: 2024 });
    await api.overview();
    expect(fetch).toHaveBeenCalledWith('/api/overview');
  });

  it('overview() with an empty countries array also fetches plain /api/overview', async () => {
    mockFetchOnce({ latest_year: 2024 });
    await api.overview([]);
    expect(fetch).toHaveBeenCalledWith('/api/overview');
  });

  it('overview() with countries encodes them as repeated query params', async () => {
    mockFetchOnce({ latest_year: 2024 });
    await api.overview(['China', 'India']);
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    const [path, query] = calledUrl.split('?');
    expect(path).toBe('/api/overview');
    expect(new URLSearchParams(query).getAll('countries')).toEqual(['China', 'India']);
  });

  it('historicalTimeseries() encodes repeated countries + gas as query params', async () => {
    mockFetchOnce({ gas: 'co2', gas_label: 'CO2', series: [] });
    await api.historicalTimeseries(['China', 'United States'], 'co2');
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    const [path, query] = calledUrl.split('?');
    const params = new URLSearchParams(query);
    expect(path).toBe('/api/historical/timeseries');
    expect(params.getAll('countries')).toEqual(['China', 'United States']);
    expect(params.get('gas')).toBe('co2');
  });

  it('countryProfile() URI-encodes the country name in the path', async () => {
    mockFetchOnce({ country: 'United Kingdom' });
    await api.countryProfile('United Kingdom');
    expect(fetch).toHaveBeenCalledWith('/api/countries/United%20Kingdom/profile');
  });

  it('scenarioTimeseries() omits the country param when not provided', async () => {
    mockFetchOnce({ title_suffix: '', historical: null, scenarios: [], level_1990: null });
    await api.scenarioTimeseries('global');
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toBe('/api/scenarios/timeseries?view=global');
  });

  it('scenarioTimeseries() includes the country param when provided', async () => {
    mockFetchOnce({ title_suffix: '', historical: null, scenarios: [], level_1990: null });
    await api.scenarioTimeseries('single', 'India');
    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toBe('/api/scenarios/timeseries?view=single&country=India');
  });

  it('throws ApiError with the response detail on a non-ok response', async () => {
    mockFetchOnce({ detail: 'data/ets_forecasts.csv not found.' }, { ok: false, status: 503 });
    await expect(api.forecastSummary()).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'data/ets_forecasts.csv not found.',
    });
  });

  it('falls back to statusText when a non-ok response has no JSON body', async () => {
    const response = {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('not json')),
    } as Response;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    await expect(api.overview()).rejects.toBeInstanceOf(ApiError);
    await expect(api.overview()).rejects.toMatchObject({ message: 'Internal Server Error' });
  });
});

describe('api client — world map series', () => {
  it('asks for the default range with no query, and for an earlier start year when given one', async () => {
    mockFetchOnce({});
    await api.worldMapSeries();
    expect(fetch).toHaveBeenLastCalledWith('/api/overview/world-map-series');
    await api.worldMapSeries(1970);
    expect(fetch).toHaveBeenLastCalledWith('/api/overview/world-map-series?start_year=1970');
  });
});

describe('api client — correlation domain', () => {
  it('calls bare endpoints with no query string when no options are given', async () => {
    mockFetchOnce({});
    await api.correlationMeta();
    expect(fetch).toHaveBeenLastCalledWith('/api/correlation/meta');
    await api.correlationConcentration();
    expect(fetch).toHaveBeenLastCalledWith('/api/correlation/concentration');
    await api.correlationEmissionsTemperature();
    expect(fetch).toHaveBeenLastCalledWith('/api/correlation/emissions-temperature');
  });

  it('sends only the options that were set, using the API\'s snake_case names', async () => {
    mockFetchOnce({});
    await api.correlationConcentration({ view: 'index', baseline: '1990', startYear: 1990 });
    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    const [path, query] = url.split('?');
    expect(path).toBe('/api/correlation/concentration');
    expect(Object.fromEntries(new URLSearchParams(query))).toEqual({ view: 'index', baseline: '1990', start_year: '1990' });
  });

  it('country-share encodes countries as repeated params and a ranking as year + limit', async () => {
    mockFetchOnce({});
    await api.correlationCountryShare({ countries: ['USA', 'CHN'], startYear: 1970 });
    let query = (vi.mocked(fetch).mock.calls[0][0] as string).split('?')[1];
    expect(new URLSearchParams(query).getAll('countries')).toEqual(['USA', 'CHN']);
    mockFetchOnce({});
    await api.correlationCountryShare({ year: 2024, limit: 50, gasScope: 'co2' });
    query = (vi.mocked(fetch).mock.calls[0][0] as string).split('?')[1];
    expect(Object.fromEntries(new URLSearchParams(query))).toEqual({ year: '2024', limit: '50', gas_scope: 'co2' });
  });

  it('country-share allCountries sends all_countries=true alongside the year, and omits it when false', async () => {
    mockFetchOnce({});
    await api.correlationCountryShare({ year: 2024, allCountries: true });
    let query = (vi.mocked(fetch).mock.calls[0][0] as string).split('?')[1];
    expect(Object.fromEntries(new URLSearchParams(query))).toEqual({ year: '2024', all_countries: 'true' });
    mockFetchOnce({});
    await api.correlationCountryShare({ year: 2024, allCountries: false });
    query = (vi.mocked(fetch).mock.calls[0][0] as string).split('?')[1];
    expect(new URLSearchParams(query).has('all_countries')).toBe(false);
  });

  it('scenario-temperature sends each scenario as a repeated `scenario` param', async () => {
    mockFetchOnce({});
    await api.correlationScenarioTemperature({ scenarios: ['BAU', 'Aggressive'], line: 'headline' });
    const query = (vi.mocked(fetch).mock.calls[0][0] as string).split('?')[1];
    expect(new URLSearchParams(query).getAll('scenario')).toEqual(['BAU', 'Aggressive']);
    expect(new URLSearchParams(query).get('line')).toBe('headline');
  });

  it('surfaces a 422 validation error (unsupported source/baseline) as an ApiError with its detail', async () => {
    mockFetchOnce({ detail: 'unsupported combination' }, { ok: false, status: 422, statusText: 'Unprocessable Entity' });
    await expect(api.correlationEmissionsTemperature({ source: 'primap_ghg', baseline: 'preindustrial' })).rejects.toMatchObject({ status: 422 });
  });
});
