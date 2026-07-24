import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, ScenarioCumulativeResponse, ScenarioTimeseriesResponse } from '../api/types';
import ScenarioComparisonPage from './ScenarioComparisonPage';

vi.mock('../api/client', () => ({
  api: { listCountries: vi.fn(), scenarioTimeseries: vi.fn(), scenarioCumulative: vi.fn() },
}));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own concern.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

const COUNTRIES: CountriesResponse = { featured: ['China'], expanded: ['China', 'Vietnam'] };

const TIMESERIES: ScenarioTimeseriesResponse = {
  title_suffix: 'China',
  historical: { name: 'Historical', years: [2020], values: [10000] },
  scenarios: [{ name: 'BAU', years: [2025], values: [11000] }],
  level_1990: 2000,
};
const CUMULATIVE: ScenarioCumulativeResponse = {
  sort_by: 'BAU',
  order: ['China'],
  scenarios: ['BAU', 'Moderate', 'Aggressive'],
  rows: [{ country: 'China', values: { BAU: 1, Moderate: 2, Aggressive: 3 } }],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('ScenarioComparisonPage', () => {
  it('defaults to Single Country view for the featured[0] country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('CO₂ Emissions Scenarios — China')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioTimeseries)).toHaveBeenCalledWith('single', 'China');
  });

  it('switches to Global Aggregate and drops the country param', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('CO₂ Emissions Scenarios — China');

    vi.mocked(api.scenarioTimeseries).mockResolvedValue({ ...TIMESERIES, title_suffix: 'All 40 Countries' });
    await user.click(screen.getByText('Global Aggregate'));

    expect(await screen.findByText('CO₂ Emissions Scenarios — All 40 Countries')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioTimeseries)).toHaveBeenLastCalledWith('global', undefined);
    // The per-country Select should disappear entirely in Global Aggregate view.
    expect(screen.queryByLabelText('Select a country')).not.toBeInTheDocument();
  });

  it('re-sorts the cumulative table when a different scenario radio is selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by BAU)');

    vi.mocked(api.scenarioCumulative).mockResolvedValue({ ...CUMULATIVE, sort_by: 'Moderate' });
    await user.click(screen.getByRole('radio', { name: 'Moderate' }));

    expect(await screen.findByText('Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by Moderate)')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCumulative)).toHaveBeenLastCalledWith('Moderate');
  });

  it('renders an inline error instead of crashing when the timeseries call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioTimeseries).mockRejectedValue(new Error('Failed to load data.'));
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioTimeseries)).not.toHaveBeenCalled();
  });
});
