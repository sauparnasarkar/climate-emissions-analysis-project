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
  it('overview() fetches /api/overview', async () => {
    mockFetchOnce({ latest_year: 2024 });
    await api.overview();
    expect(fetch).toHaveBeenCalledWith('/api/overview');
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
