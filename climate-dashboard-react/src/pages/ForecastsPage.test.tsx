import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type {
  CountriesResponse,
  EtsParametersResponse,
  FeatureImportanceResponse,
  ForecastCountryResponse,
  ForecastSummaryResponse,
  ModelComparisonResponse,
} from '../api/types';
import ForecastsPage from './ForecastsPage';

vi.mock('../api/client', () => ({
  api: {
    listCountries: vi.fn(),
    forecast: vi.fn(),
    forecastSummary: vi.fn(),
    modelComparison: vi.fn(),
    etsParameters: vi.fn(),
    featureImportance: vi.fn(),
  },
}));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own concern.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

const COUNTRIES: CountriesResponse = { featured: ['China'], expanded: ['China', 'Vietnam'] };
const FORECAST: ForecastCountryResponse = {
  country: 'China',
  hist_years: [2018],
  hist_co2: [10000],
  holdout_years: [2019],
  holdout_co2: [10500],
  forecast_years: [2024],
  forecast_mean: [11000],
  ci_upper: [11500],
  ci_lower: [10500],
};
const SUMMARY: ForecastSummaryResponse = { rows: [{ country: 'China', forecast_2030: 1, forecast_2035: 2, forecast_2040: 3, actual_2020: 4, pct_change_2020_2040: 5 }] };
const MODEL_COMPARISON: ModelComparisonResponse = { columns: ['model', 'mae'], rows: [{ model: 'ETS', mae: 12.3 }] };
const ETS_PARAMS: EtsParametersResponse = { rows: [{ country: 'China', alpha: 0.1, beta_star: 0.2, phi: 0.9 }] };
const FEATURE_IMPORTANCE: FeatureImportanceResponse = { rows: [{ feature: 'co2_lag1', importance: 0.5 }] };

function mockAllResolved() {
  vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
  vi.mocked(api.forecast).mockResolvedValue(FORECAST);
  vi.mocked(api.forecastSummary).mockResolvedValue(SUMMARY);
  vi.mocked(api.modelComparison).mockResolvedValue(MODEL_COMPARISON);
  vi.mocked(api.etsParameters).mockResolvedValue(ETS_PARAMS);
  vi.mocked(api.featureImportance).mockResolvedValue(FEATURE_IMPORTANCE);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('ForecastsPage', () => {
  it('fires all 5 endpoint calls and renders the chart, summary table, and all 3 accordion sections', async () => {
    mockAllResolved();
    render(<ForecastsPage />);

    expect(await screen.findByText('ETS(A,Ad,N) Forecast — China')).toBeInTheDocument();
    expect(screen.getByText('Forecast Summary — 1 Countries')).toBeInTheDocument();
    expect(await screen.findByText('Five-Model Comparison Table (MAE / RMSE)')).toBeInTheDocument();
    expect(screen.getByText('ETS(A,Ad,N) Fitted Parameters — 1 Countries')).toBeInTheDocument();
    expect(screen.getByText('Random Forest Feature Importance (Pooled Model)')).toBeInTheDocument();

    expect(vi.mocked(api.forecast)).toHaveBeenCalledWith('China');
    expect(vi.mocked(api.forecastSummary)).toHaveBeenCalled();
    expect(vi.mocked(api.modelComparison)).toHaveBeenCalled();
    expect(vi.mocked(api.etsParameters)).toHaveBeenCalled();
    expect(vi.mocked(api.featureImportance)).toHaveBeenCalled();
  });

  it('only renders accordion sections whose data has actually loaded', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.forecast).mockResolvedValue(FORECAST);
    vi.mocked(api.forecastSummary).mockResolvedValue(SUMMARY);
    vi.mocked(api.modelComparison).mockResolvedValue(MODEL_COMPARISON);
    vi.mocked(api.etsParameters).mockRejectedValue(new Error('Failed to load data.'));
    vi.mocked(api.featureImportance).mockRejectedValue(new Error('Failed to load data.'));
    render(<ForecastsPage />);

    expect(await screen.findByText('Five-Model Comparison Table (MAE / RMSE)')).toBeInTheDocument();
    expect(screen.queryByText('ETS(A,Ad,N) Fitted Parameters — 1 Countries')).not.toBeInTheDocument();
    expect(screen.queryByText('Random Forest Feature Importance (Pooled Model)')).not.toBeInTheDocument();
  });

  it('renders an inline error for the main forecast chart when that call fails, independent of the others', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.forecast).mockRejectedValue(new Error('Failed to load data.'));
    vi.mocked(api.forecastSummary).mockResolvedValue(SUMMARY);
    vi.mocked(api.modelComparison).mockResolvedValue(MODEL_COMPARISON);
    vi.mocked(api.etsParameters).mockResolvedValue(ETS_PARAMS);
    vi.mocked(api.featureImportance).mockResolvedValue(FEATURE_IMPORTANCE);
    render(<ForecastsPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(await screen.findByText('Forecast Summary — 1 Countries')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<ForecastsPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.forecast)).not.toHaveBeenCalled();
  });
});
