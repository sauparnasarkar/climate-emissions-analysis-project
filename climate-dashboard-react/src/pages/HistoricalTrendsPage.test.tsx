import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, HistoricalDecadeCompositionResponse, HistoricalTimeseriesResponse } from '../api/types';
import HistoricalTrendsPage from './HistoricalTrendsPage';

vi.mock('../api/client', () => ({
  api: { listCountries: vi.fn(), historicalTimeseries: vi.fn(), historicalDecadeComposition: vi.fn() },
}));

// See OverviewPage.test.tsx for why SyChart is stubbed rather than rendered for
// real — this test in particular unmounts a rendered chart mid-test (deselecting
// all countries), which is exactly the scenario that races with Plotly's async
// redraw in jsdom.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

const FEATURED = [
  'China', 'United States', 'India', 'Russia', 'Japan',
  'Germany', 'Brazil', 'United Kingdom', 'South Africa', 'Australia',
];

const COUNTRIES: CountriesResponse = {
  featured: FEATURED,
  expanded: [...FEATURED, 'Vietnam'],
};

const TIMESERIES: HistoricalTimeseriesResponse = {
  gas: 'co2',
  gas_label: 'CO₂',
  series: [{ name: 'China', years: [2020, 2021], values: [10000, 11000] }],
};

const COMPOSITION: HistoricalDecadeCompositionResponse = {
  decades: [1990, 2000],
  series: [{ gas: 'co2', gas_label: 'CO₂', share: [70, 72] }],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('HistoricalTrendsPage', () => {
  it('renders both charts once both API calls resolve', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    render(<HistoricalTrendsPage />);

    expect(await screen.findByText('CO₂ Emissions by Country')).toBeInTheDocument();
    expect(screen.getByText('GHG Composition by Decade — 10 Countries (% share)')).toBeInTheDocument();
    // Default selection is all 10 featured countries — matches Overview's Selected tier
    // default, and confirms the country MultiSelect's initial value actually reached the
    // API call.
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'co2');
    expect(vi.mocked(api.historicalDecadeComposition)).toHaveBeenCalledWith(FEATURED);
  });

  it('shows a warning instead of calling the timeseries API when no countries are selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<HistoricalTrendsPage />);

    await screen.findByText('CO₂ Emissions by Country');
    // MultiSelect's own interaction pattern is design-system's concern (already
    // covered by its own test suite) — deselecting via the visible "×" chip is the
    // one piece of user-facing behavior this page itself is responsible for wiring up.
    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }
    // Both the line chart and the decade-composition chart show the same warning at 0
    // selected — the composition chart doesn't fall back to an all-40-countries aggregate.
    expect(await screen.findAllByText('Select at least one country.')).toHaveLength(2);
  });

  it('blocks selecting an 11th country since the default selection already sits at the 10-selection cap', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<HistoricalTrendsPage />);
    await screen.findByText('CO₂ Emissions by Country');

    // All 10 featured countries are preselected by default, already at maxSelected=10.
    await user.click(screen.getByLabelText('Select countries (up to 10/11)'));
    expect(await screen.findByText('Maximum 10 selected')).toBeInTheDocument();

    const vietnamOption = screen.getByRole('option', { name: 'Vietnam' });
    expect(vietnamOption).toHaveAttribute('aria-disabled', 'true');

    await user.click(vietnamOption);
    expect(vi.mocked(api.historicalTimeseries)).not.toHaveBeenCalledWith(
      expect.arrayContaining(['Vietnam']),
      expect.anything(),
    );
  });

  it('"Reset to default" restores all 10 featured countries and refetches', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<HistoricalTrendsPage />);
    await screen.findByText('CO₂ Emissions by Country');

    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }
    await screen.findAllByText('Select at least one country.');

    vi.mocked(api.historicalTimeseries).mockClear();
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    await user.click(screen.getByRole('button', { name: 'Reset to default' }));

    expect(await screen.findByText('CO₂ Emissions by Country')).toBeInTheDocument();
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'co2');
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<HistoricalTrendsPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.historicalTimeseries)).not.toHaveBeenCalled();
  });
});
