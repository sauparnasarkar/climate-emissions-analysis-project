import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { OverviewResponse } from '../api/types';
import OverviewPage from './OverviewPage';

vi.mock('../api/client', () => ({ api: { overview: vi.fn() } }));

// SyChart's Plotly rendering is design-system's own concern (covered by its own
// test suite) — stubbed here so this page's tests exercise its own data-wiring
// logic, not Plotly's DOM lifecycle in jsdom (which has no real canvas/rAF timing
// and throws internally if a chart unmounts mid-redraw).
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

const RESPONSE: OverviewResponse = {
  latest_year: 2024,
  latest_co2_total: 25324,
  co2_1990_total: 14350,
  pct_change_since_1990: 76.5,
  countries_count: 10,
  total_countries_analyzed: 40,
  focus_countries: ['China', 'United States', 'India'],
  latest_year_bar: [{ country: 'China', value: 12000 }],
  top_movers: [{ country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 }],
  fastest_growth: { country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 },
  largest_reduction: { country: 'United Kingdom', co2_1990: 600, co2_latest: 300, absolute_change: -300, pct_change: -50 },
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('OverviewPage', () => {
  it('shows a loading state, then renders KPIs from the API response', async () => {
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    render(<OverviewPage />);

    expect(await screen.findByText(/25,324 MtCO/)).toBeInTheDocument();
    expect(screen.getByText('+76.5%')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText(/China.*United States.*India/)).toBeInTheDocument();
    expect(screen.getByText(/for 40 major countries/)).toBeInTheDocument();
    expect(screen.getByText('10-Country CO₂ (2024)')).toBeInTheDocument();
    expect(screen.getByText('Top Movers Since 1990 (3 Focus Countries)')).toBeInTheDocument();
    expect(screen.getByText(/among the 3 focus countries/)).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when the API call fails', async () => {
    vi.mocked(api.overview).mockRejectedValue(new Error('Failed to load data.'));
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });
});
