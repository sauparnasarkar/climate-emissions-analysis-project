import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

// JumpLinks (SPEC.md §5.19) calls design-system's useReducedMotion during render -- jsdom has
// no window.matchMedia at all, so every test needs this stub. Same pattern as useCountUp.test.ts.
function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? matches : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

beforeEach(() => {
  mockReducedMotion(false);
});

afterEach(() => {
  // Not vi.unstubAllGlobals() -- that would also wipe the global ResizeObserver stub
  // src/test/setup.ts establishes once for the whole file (design-system's DataTable needs
  // it), breaking every test after the first. beforeEach already re-stubs matchMedia fresh
  // before each test, so there's nothing stale left for this to clean up anyway.
  vi.clearAllMocks();
  window.location.hash = '';
});

describe('ForecastsPage', () => {
  it('fires all 5 endpoint calls and renders the chart, summary table, and all 3 accordion sections', async () => {
    mockAllResolved();
    render(<ForecastsPage />);

    expect(await screen.findByText('ETS(A,Ad,N) Forecast — China')).toBeInTheDocument();
    expect(screen.getByText('Forecast Summary — 1 Country')).toBeInTheDocument();
    expect(await screen.findByText('Five-Model Comparison Table (MAE / RMSE)')).toBeInTheDocument();
    expect(screen.getByText('ETS(A,Ad,N) Fitted Parameters — 1 Country')).toBeInTheDocument();
    expect(screen.getByText('Random Forest Feature Importance (Pooled Model)')).toBeInTheDocument();

    expect(vi.mocked(api.forecast)).toHaveBeenCalledWith('China');
    expect(vi.mocked(api.forecastSummary)).toHaveBeenCalledWith('expanded');
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
    expect(screen.queryByText('ETS(A,Ad,N) Fitted Parameters — 1 Country')).not.toBeInTheDocument();
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
    expect(await screen.findByText('Forecast Summary — 1 Country')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<ForecastsPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.forecast)).not.toHaveBeenCalled();
  });

  it('renders a Jump To nav with all 5 sections once every endpoint has resolved', async () => {
    mockAllResolved();
    render(<ForecastsPage />);
    await screen.findByText('ETS(A,Ad,N) Forecast — China');
    await screen.findByText('Five-Model Comparison Table (MAE / RMSE)');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual([
      'Forecast Chart', 'Forecast Summary', 'Model Comparison', 'ETS Parameters', 'Feature Importance',
    ]);
    expect(links.map((l) => l.getAttribute('href'))).toEqual([
      '#forecast-chart', '#forecast-summary',
      '#model-comparison-accordion-panel', '#ets-params-accordion-panel', '#feature-importance-accordion-panel',
    ]);
  });

  it('only lists accordion-backed jump items for sections whose data has actually loaded', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.forecast).mockResolvedValue(FORECAST);
    vi.mocked(api.forecastSummary).mockResolvedValue(SUMMARY);
    vi.mocked(api.modelComparison).mockResolvedValue(MODEL_COMPARISON);
    vi.mocked(api.etsParameters).mockRejectedValue(new Error('Failed to load data.'));
    vi.mocked(api.featureImportance).mockRejectedValue(new Error('Failed to load data.'));
    render(<ForecastsPage />);
    await screen.findByText('Five-Model Comparison Table (MAE / RMSE)');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Forecast Chart', 'Forecast Summary', 'Model Comparison']);
  });

  it('clicking a jump link opens its collapsed Accordion panel before scrolling to it', async () => {
    // jsdom has no real scrollIntoView implementation at all.
    Element.prototype.scrollIntoView = vi.fn();
    mockAllResolved();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ForecastsPage />);
    await screen.findByText('Five-Model Comparison Table (MAE / RMSE)');

    // Collapsed by default -- Accordion.tsx only mounts a panel's content once open.
    expect(screen.queryByText(/Five-Model Comparison Table \(MAE \/ RMSE\)/)?.closest('[role="region"]')).toBeNull();
    const panelButton = screen.getByRole('button', { name: 'Five-Model Comparison Table (MAE / RMSE)' });
    expect(panelButton).toHaveAttribute('aria-expanded', 'false');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    await user.click(within(nav).getByRole('link', { name: 'Model Comparison' }));

    expect(await screen.findByRole('button', { name: 'Five-Model Comparison Table (MAE / RMSE)' })).toHaveAttribute('aria-expanded', 'true');
    expect(document.getElementById('model-comparison-accordion-panel')).not.toBeNull();
  });

  it('a bookmarked URL targeting an accordion panel opens that panel and scrolls to it once its data loads', async () => {
    // Regression test for a bug the PR #126 review caught: useJumpToHashOnLoad used to fire on
    // first render (before modelComparison/etsParams/featureImportance resolved), so a bookmarked
    // #model-comparison-accordion-panel URL silently no-opped -- the panel doesn't exist in the
    // DOM until its data has loaded AND the panel is open.
    Element.prototype.scrollIntoView = vi.fn();
    window.location.hash = '#model-comparison-accordion-panel';
    mockAllResolved();
    render(<ForecastsPage />);

    expect(await screen.findByRole('button', { name: 'Five-Model Comparison Table (MAE / RMSE)' })).toHaveAttribute('aria-expanded', 'true');
    expect(document.activeElement?.id).toBe('model-comparison-accordion-panel');
  });
});
