import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { ApiError } from '../api/types';
import type { CountriesResponse, OverviewResponse, WorldMapTimeSeries } from '../api/types';
import OverviewPage from './OverviewPage';

vi.mock('../api/client', () => ({ api: { listCountries: vi.fn(), overview: vi.fn(), worldMapSeries: vi.fn() } }));

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
// on the final rendered value don't race the animation in jsdom's rAF shim.
vi.mock('../hooks/useCountUp', () => ({ useCountUp: (target: number) => target }));

// useYearAnimation's own play/pause/replay/reduced-motion logic has its own dedicated test
// file (useYearAnimation.test.ts) -- stubbed here to a fixed, controllable return value so
// this page's tests assert on wiring (does the right year/co2 data reach the right controls),
// not on real setInterval timing racing jsdom.
vi.mock('../hooks/useYearAnimation');

const DEFAULT_ANIMATION = {
  currentYear: 2024,
  isPlaying: false,
  play: vi.fn(),
  pause: vi.fn(),
  toggle: vi.fn(),
  seek: vi.fn(),
  reducedMotion: false,
};

const FEATURED = [
  'China', 'United States', 'India', 'Russia', 'Japan',
  'Germany', 'Brazil', 'United Kingdom', 'South Africa', 'Australia',
];

const COUNTRIES: CountriesResponse = {
  featured: FEATURED,
  expanded: [...FEATURED, 'Vietnam'],
};

const RESPONSE: OverviewResponse = {
  all_countries: { label: 'All Countries', countries_count: 195, latest_year: 2024, latest_co2_total: 37406, co2_1990_total: 22184, pct_change_since_1990: 68.6, co2_by_year: [22184, 37406] },
  expanded_countries: { label: 'Expanded', countries_count: 40, latest_year: 2024, latest_co2_total: 34477, co2_1990_total: 19686, pct_change_since_1990: 75.1, co2_by_year: [19686, 34477] },
  selected: { label: 'Selected', countries_count: 10, latest_year: 2024, latest_co2_total: 25324, co2_1990_total: 14350, pct_change_since_1990: 76.5, co2_by_year: [] },
  selected_country_list: FEATURED,
  latest_year_bar: [{ country: 'China', value: 12000 }],
  top_movers: [{ country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 }],
  fastest_growth: { country: 'China', co2_1990: 2000, co2_latest: 12000, absolute_change: 10000, pct_change: 500 },
  largest_reduction: { country: 'United Kingdom', co2_1990: 600, co2_latest: 300, absolute_change: -300, pct_change: -50 },
  world_map: [{ country: 'China', iso_code: 'CHN', value: 12000 }],
};

// Only China (a FEATURED country) and Vietnam (used by the "switch selection" test) need
// real entries -- AnimatedWorldMap's client-side Selected sum simply skips any FEATURED
// country absent from this array, so the other 9 don't need fixture rows to exercise the
// default-selection path. Two consecutive years (not 1990/2024 literally) keeps yearIdx
// arithmetic (currentYear - years[0]) trivial to reason about in these tests; DEFAULT_ANIMATION's
// currentYear=2024 requires years[1]===2024 to land on index 1.
const WORLD_MAP_SERIES: WorldMapTimeSeries = {
  iso_codes: ['CHN', 'VNM'],
  countries: ['China', 'Vietnam'],
  years: [2023, 2024],
  values: [
    [14350, 21],
    [25324, 370],
  ],
  value_range: [21, 25324],
};

beforeEach(() => {
  vi.mocked(useYearAnimation).mockReturnValue(DEFAULT_ANIMATION);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('OverviewPage', () => {
  it('shows a loading state, then renders all three KPI rows from the API response', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<OverviewPage />);

    expect(await screen.findByText(/for 40 major countries/)).toBeInTheDocument();
    // Both the map and the Selected-tier bar chart share this exact title when their years
    // coincide (as in this fixture) -- assert the expected count of 2, not just >0.
    expect(screen.getAllByText('CO₂ Emissions by Country (2024)')).toHaveLength(2);
    expect(screen.getByText('All Countries')).toBeInTheDocument();
    expect(screen.getByText('Expanded (Coverage + ≥100 Mt)')).toBeInTheDocument();
    expect(screen.getByText('Selected')).toBeInTheDocument();
    // 'CO₂ (2024)' appears once per tier card (All Countries / Expanded / Selected = 3).
    expect(screen.getAllByText('CO₂ (2024)')).toHaveLength(3);
    // Tier numbers snap directly to their value (no CountUpText/aria-hidden duplication --
    // these change every autoplay tick, unlike the one-time KpiStat count-ups below).
    expect(screen.getByText('37,406 MtCO₂')).toBeInTheDocument();
    expect(screen.getByText('34,477 MtCO₂')).toBeInTheDocument();
    // Selected's CO2 total is now computed client-side from WORLD_MAP_SERIES (25324 at
    // index 1), not read from RESPONSE.selected.latest_co2_total directly.
    expect(screen.getByText('25,324 MtCO₂')).toBeInTheDocument();
    // (25324 - 14350) / 14350 * 100 = 76.47...% -> "+76.5%", same figure the old
    // server-computed RESPONSE.selected.pct_change_since_1990 fixture used to assert,
    // now independently reproduced by the client-side computation.
    expect(screen.getByText('+76.5%')).toBeInTheDocument();
    expect(screen.getByText('Top Movers Since 1990 (10 Selected Countries)')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).toHaveBeenCalledWith(FEATURED);
  });

  it('fetches world-map-series exactly once, regardless of how many times the selection changes', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText('Selected');

    vi.mocked(api.overview).mockResolvedValue({ ...RESPONSE, selected_country_list: ['Vietnam'] });
    await user.click(screen.getByLabelText('Select countries (up to 10/11)'));
    await user.click(screen.getByRole('option', { name: 'Vietnam' }));
    await screen.findByText('Fastest Growth — China'); // re-render settled

    expect(vi.mocked(api.worldMapSeries)).toHaveBeenCalledTimes(1);
  });

  it('renders the Play/Pause control and a year slider bounded to the series range', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<OverviewPage />);

    const playButton = await screen.findByRole('button', { name: 'Play' });
    expect(playButton).not.toBeDisabled();
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('aria-valuemin', '2023');
    expect(slider).toHaveAttribute('aria-valuemax', '2024');
    expect(slider).toHaveAttribute('aria-valuenow', '2024');
  });

  it('calls toggle when the Play/Pause button is clicked', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<OverviewPage />);

    await user.click(await screen.findByRole('button', { name: 'Play' }));
    expect(DEFAULT_ANIMATION.toggle).toHaveBeenCalledTimes(1);
  });

  it('disables Play (but keeps the slider scrubbable) when prefers-reduced-motion is set', async () => {
    vi.mocked(useYearAnimation).mockReturnValue({ ...DEFAULT_ANIMATION, isPlaying: false, reducedMotion: true });
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<OverviewPage />);

    expect(await screen.findByRole('button', { name: 'Play' })).toBeDisabled();
    expect(screen.getByRole('slider')).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('suppresses "% Change since 1990" on the animation\'s first frame instead of showing a misleading +0.0%', async () => {
    vi.mocked(useYearAnimation).mockReturnValue({ ...DEFAULT_ANIMATION, currentYear: 2023 });
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<OverviewPage />);

    await screen.findByText('Selected');
    // All Countries, Expanded, and Selected each suppress their own pct-change row.
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.queryByText('+0.0%')).not.toBeInTheDocument();
  });

  it('blocks selecting an 11th country beyond the 10-selection cap', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
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
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
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

    // 370 MtCO₂ now comes from WORLD_MAP_SERIES' Vietnam entry at the current frame (index 1,
    // year 2024), summed client-side over the new ['Vietnam']-only selection -- the same
    // number the old server-computed RESPONSE.selected.latest_co2_total fixture used to carry.
    expect(await screen.findByText('370 MtCO₂')).toBeInTheDocument();
    expect(await screen.findByText('Fastest Growth — Vietnam')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).toHaveBeenLastCalledWith(['Vietnam']);
  });

  it('shows a warning in place of the Selected tier/charts when deselecting to 0, while the top two tiers stay visible', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
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
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
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
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when the world-map-series API call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockRejectedValue(new ApiError(503, 'Failed to load map data.'));
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load map data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<OverviewPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).not.toHaveBeenCalled();
  });
});
