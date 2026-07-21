import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { HistoricalDecadeCompositionResponse, HistoricalTimeseriesResponse } from '../api/types';
import HistoricalTrendsPage from './HistoricalTrendsPage';

vi.mock('../api/client', () => ({
  api: { historicalTimeseries: vi.fn(), historicalDecadeComposition: vi.fn() },
}));

// See OverviewPage.test.tsx for why SyChart is stubbed rather than rendered for
// real — this test in particular unmounts a rendered chart mid-test (deselecting
// all countries), which is exactly the scenario that races with Plotly's async
// redraw in jsdom.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

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
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    render(<HistoricalTrendsPage />);

    expect(await screen.findByText('CO₂ Emissions by Country')).toBeInTheDocument();
    expect(screen.getByText('GHG Composition by Decade — 10 Countries (% share)')).toBeInTheDocument();
    // Default selection is the first 5 focus countries (constants.ts) — confirms the
    // country MultiSelect's initial value actually reached the API call.
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(
      expect.arrayContaining(['China']),
      'co2',
    );
  });

  it('shows a warning instead of calling the timeseries API when no countries are selected', async () => {
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
    expect(await screen.findByText('Select at least one country.')).toBeInTheDocument();
  });
});
