import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, ScenarioCompareResponse, ScenarioCumulativeResponse } from '../api/types';
import ScenarioComparisonPage from './ScenarioComparisonPage';

vi.mock('../api/client', () => ({
  api: { listCountries: vi.fn(), scenarioCumulative: vi.fn(), scenarioCompare: vi.fn() },
}));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own concern.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

const COUNTRIES: CountriesResponse = { featured: ['China'], expanded: ['China', 'Vietnam'] };

const CUMULATIVE: ScenarioCumulativeResponse = {
  sort_by: 'BAU',
  order: ['China', 'United States'],
  scenarios: ['BAU', 'Moderate', 'Aggressive'],
  rows: [
    { country: 'China', values: { BAU: 1000, Moderate: 800, Aggressive: 600 } },
    { country: 'United States', values: { BAU: 500, Moderate: 400, Aggressive: 300 } },
  ],
};

const COMPARE: ScenarioCompareResponse = {
  countries: ['China'],
  scenarios: {
    BAU: [{ name: 'China', years: [2020, 2040], values: [10000, 16000] }],
    Moderate: [{ name: 'China', years: [2020, 2040], values: [10000, 9000] }],
    Aggressive: [{ name: 'China', years: [2020, 2040], values: [10000, 7000] }],
  },
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('ScenarioComparisonPage', () => {
  it('renders the treemap and all three scenario panels for the default featured selection', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Cumulative BAU Emissions & Reduction Upside — 2 Countries')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'BAU' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Moderate' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Aggressive' })).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).toHaveBeenCalledWith(['China']);
  });

  it('refetches the comparison panels when the country selection changes', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    const updated: ScenarioCompareResponse = { ...COMPARE, countries: ['China', 'Vietnam'] };
    vi.mocked(api.scenarioCompare).mockResolvedValue(updated);
    await user.click(screen.getByLabelText(/Select countries/));
    await user.click(screen.getByRole('option', { name: 'Vietnam' }));

    expect(await screen.findByRole('heading', { name: 'BAU' })).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).toHaveBeenLastCalledWith(['China', 'Vietnam']);
  });

  it('shows a warning instead of calling scenarioCompare when no countries are selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    vi.mocked(api.scenarioCompare).mockClear();
    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }

    expect(await screen.findByText('Select at least one country.')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).not.toHaveBeenCalled();
  });

  it('re-sorts the cumulative table when a different scenario radio is selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by BAU)');

    vi.mocked(api.scenarioCumulative).mockResolvedValue({ ...CUMULATIVE, sort_by: 'Moderate' });
    await user.click(screen.getByRole('radio', { name: 'Moderate' }));

    expect(await screen.findByText('Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by Moderate)')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCumulative)).toHaveBeenLastCalledWith('Moderate');
  });

  it('renders an inline error instead of crashing when the compare call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockRejectedValue(new Error('Failed to load data.'));
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).not.toHaveBeenCalled();
  });
});
