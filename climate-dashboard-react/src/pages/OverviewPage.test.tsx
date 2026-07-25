import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, OverviewResponse } from '../api/types';
import OverviewPage from './OverviewPage';

vi.mock('../api/client', () => ({ api: { listCountries: vi.fn(), overview: vi.fn() } }));

// SyChart's Plotly rendering is design-system's own concern (covered by its own
// test suite) — stubbed here so this page's tests exercise its own data-wiring
// logic, not Plotly's DOM lifecycle in jsdom (which has no real canvas/rAF timing
// and throws internally if a chart unmounts mid-redraw).
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

// useCountUp's animation is a UI-polish concern (real timing covered by manual/visual
// verification, not unit tests) -- stubbed to return the target immediately so assertions
// on the final rendered value don't race a ~600ms animation in jsdom's rAF shim.
vi.mock('../hooks/useCountUp', () => ({ useCountUp: (target: number) => target }));

const FEATURED = [
  'China', 'United States', 'India', 'Russia', 'Japan',
  'Germany', 'Brazil', 'United Kingdom', 'South Africa', 'Australia',
];

const COUNTRIES: CountriesResponse = {
  featured: FEATURED,
  expanded: [...FEATURED, 'Vietnam'],
};

const RESPONSE: OverviewResponse = {
  all_countries: { label: 'All Countries', countries_count: 195, latest_year: 2024, latest_co2_total: 37406, co2_1990_total: 22184, pct_change_since_1990: 68.6 },
  expanded_countries: { label: 'Expanded', countries_count: 40, latest_year: 2024, latest_co2_total: 34477, co2_1990_total: 19686, pct_change_since_1990: 75.1 },
  selected: { label: 'Selected', countries_count: 10, latest_year: 2024, latest_co2_total: 25324, co2_1990_total: 14350, pct_change_since_1990: 76.5 },
  selected_country_list: FEATURED,
  latest_year_bar: [{ country: 'China', value: 12000 }],
  top_movers: [{ country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 }],
  fastest_growth: { country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 },
  largest_reduction: { country: 'United Kingdom', co2_1990: 600, co2_latest: 300, absolute_change: -300, pct_change: -50 },
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('OverviewPage', () => {
  it('shows a loading state, then renders all three KPI rows from the API response', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    render(<OverviewPage />);

    expect(await screen.findByText(/for 40 major countries/)).toBeInTheDocument();
    expect(screen.getByText('All Countries')).toBeInTheDocument();
    expect(screen.getByText('Expanded (Coverage + ≥100 Mt)')).toBeInTheDocument();
    expect(screen.getByText('Selected')).toBeInTheDocument();
    expect(screen.getByText('CO₂ (2024)')).toBeInTheDocument();
    expect(screen.getByText('37,406 MtCO₂')).toBeInTheDocument();
    expect(screen.getByText('34,477 MtCO₂')).toBeInTheDocument();
    expect(screen.getByText('25,324 MtCO₂')).toBeInTheDocument();
    expect(screen.getByText('+76.5%')).toBeInTheDocument();
    expect(screen.getByText(/China.*United States.*India/)).toBeInTheDocument();
    expect(screen.getByText('Top Movers Since 1990 (10 Selected Countries)')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).toHaveBeenCalledWith(FEATURED);
  });

  it('blocks selecting an 11th country beyond the 10-selection cap', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText('Selected');

    await user.click(screen.getByLabelText('Select countries (up to 10/11)'));
    const vietnamOption = screen.getByRole('option', { name: 'Vietnam' });
    expect(vietnamOption).toHaveAttribute('aria-disabled', 'true');

    await user.click(vietnamOption);
    expect(vi.mocked(api.overview)).not.toHaveBeenCalledWith(expect.arrayContaining(['Vietnam']));
  });

  it('refetches and updates the Selected row/chart/Top Movers when the selection changes', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText('Selected');

    const updated: OverviewResponse = {
      ...RESPONSE,
      selected: { ...RESPONSE.selected, countries_count: 1, latest_co2_total: 370 },
      selected_country_list: ['Vietnam'],
      fastest_growth: { country: 'Vietnam', co2_1990: 21, co2_latest: 370, absolute_change: 349, pct_change: 1641.5 },
      largest_reduction: { country: 'Vietnam', co2_1990: 21, co2_latest: 370, absolute_change: 349, pct_change: 1641.5 },
    };
    vi.mocked(api.overview).mockResolvedValue(updated);

    // Deselect everything except Vietnam by removing each featured tag, then add Vietnam.
    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }
    await user.click(screen.getByLabelText('Select countries (up to 10/11)'));
    await user.click(screen.getByRole('option', { name: 'Vietnam' }));

    expect(await screen.findByText('370 MtCO₂')).toBeInTheDocument();
    expect(await screen.findByText('Fastest Growth — Vietnam')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).toHaveBeenLastCalledWith(['Vietnam']);
  });

  it('shows a warning in place of the Selected tier/charts when deselecting to 0, while the top two tiers stay visible', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText('Selected');

    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }

    expect(await screen.findByText('Select at least one country.')).toBeInTheDocument();
    expect(screen.queryByText('Selected')).not.toBeInTheDocument();
    // All Countries/Expanded stay rendered regardless of the (now empty) selection.
    expect(screen.getByText('All Countries')).toBeInTheDocument();
    expect(screen.getByText('Expanded (Coverage + ≥100 Mt)')).toBeInTheDocument();
  });

  it('"Reset to default" restores the featured selection and refetches', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText('Selected');

    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }
    await screen.findByText('Select at least one country.');

    vi.mocked(api.overview).mockClear();
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    await user.click(screen.getByRole('button', { name: 'Reset to default' }));

    expect(await screen.findByText('Selected')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).toHaveBeenCalledWith(FEATURED);
  });

  it('renders an inline error instead of crashing when the overview API call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockRejectedValue(new Error('Failed to load data.'));
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).not.toHaveBeenCalled();
  });
});
