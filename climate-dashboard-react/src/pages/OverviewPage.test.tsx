import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { ApiError } from '../api/types';
import type { CountriesResponse, OverviewResponse, WorldMapTimeSeries } from '../api/types';
import { NEGATIVE_COLOR, POSITIVE_COLOR } from '../constants';
import OverviewPage from './OverviewPage';
import { CONCENTRATION, PAIR, TEMPERATURE, TEMPERATURE_MEAN5Y } from '../test/climateFixtures';
import { CLIMATE_SIGNAL_ANCHOR, RELATIONSHIP_ANCHOR } from '../lib/climateCopy';

vi.mock('../api/client', () => ({
  api: {
    listCountries: vi.fn(), overview: vi.fn(), worldMapSeries: vi.fn(),
    correlationEmissionsTemperature: vi.fn(), correlationTemperature: vi.fn(), correlationConcentration: vi.fn(),
  },
}));

// SyChart's Plotly rendering is design-system's own concern (covered by its own
// test suite) — stubbed here so this page's tests exercise its own data-wiring
// logic, not Plotly's DOM lifecycle in jsdom (which has no real canvas/rAF timing
// and throws internally if a chart unmounts mid-redraw). Also surfaces the choropleth
// series' own `noDataColor` prop so a test can assert it's the live-resolved theme color,
// not `var(...)` or the removed hardcoded value (Copilot review, PR #182), and the % Change
// bar series' `colorScale`/`colorRange` so a test can assert the diverging scale's stop
// order is reversed (increase reads as the negative/bad end) rather than SyChart's own
// default order — the resolver's own unit tests don't protect this page's wiring.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: {
      ariaLabel?: string;
      series?: Array<{ kind?: string; noDataColor?: string; colorScale?: Array<[number, string]>; colorRange?: [number, number] }>;
      outlineLocations?: string[];
    }) => {
      const barSeries = props.series?.find((s) => s.kind === 'bar');
      return (
        <div
          data-testid="sychart"
          aria-label={props.ariaLabel}
          data-no-data-color={props.series?.find((s) => s.kind === 'choropleth')?.noDataColor}
          data-axes={props.series ? JSON.stringify(props.series.map((s) => (s as { yAxis?: string }).yAxis ?? 'y')) : undefined}
          data-outline={props.outlineLocations ? JSON.stringify(props.outlineLocations) : undefined}
          data-bar-color-scale={barSeries?.colorScale ? JSON.stringify(barSeries.colorScale) : undefined}
          data-bar-color-range={barSeries?.colorRange ? JSON.stringify(barSeries.colorRange) : undefined}
        />
      );
    },
  };
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
  // Reflects SPEC.md §5.18.1's own hand-verified default-selection example -- exercises a
  // distinct abs-grower (China) vs. pct-grower (India), a near-zero "most stable" entry
  // (United States), and two decliners (United Kingdom, Germany), enough rows to trigger the
  // headline sentence's "most stable" clause (rows.length >= 4).
  top_movers: [
    { country: 'China', co2_1990: 2378, co2_latest: 12184, absolute_change: 9806, pct_change: 412.4 },
    { country: 'India', co2_1990: 681, co2_latest: 3763, absolute_change: 3082, pct_change: 452.6 },
    { country: 'United States', co2_1990: 5104, co2_latest: 4853, absolute_change: -251, pct_change: -4.9 },
    { country: 'United Kingdom', co2_1990: 592, co2_latest: 306, absolute_change: -286, pct_change: -48.3 },
    { country: 'Germany', co2_1990: 1042, co2_latest: 561, absolute_change: -481, pct_change: -46.2 },
  ],
  // Independent, 10-country fixture (SPEC.md §5.18.5) -- deliberately DIFFERENT from top_movers
  // above, to prove in tests that the headline sentence no longer shares data with the
  // selection-scoped Top Movers section. Reflects the real hand-verified top-10-emitters
  // example: China/India/United States/Germany/Russia are the four "interesting" entries the
  // sentence names; the other five (Japan/Indonesia/Iran/Saudi Arabia/South Korea) are filler
  // with moderate positive pct_change that doesn't disturb absGrower/pctGrower/mostStable/
  // decliners selection.
  headline_movers: [
    { country: 'China', co2_1990: 2378, co2_latest: 12184, absolute_change: 9806, pct_change: 412.4 },
    { country: 'India', co2_1990: 420, co2_latest: 2320, absolute_change: 1900, pct_change: 452.5 },
    { country: 'United States', co2_1990: 5000, co2_latest: 4780, absolute_change: -220, pct_change: -4.4 },
    { country: 'Germany', co2_1990: 1000, co2_latest: 543, absolute_change: -457, pct_change: -45.7 },
    { country: 'Russia', co2_1990: 1000, co2_latest: 702, absolute_change: -298, pct_change: -29.8 },
    { country: 'Japan', co2_1990: 1000, co2_latest: 1150, absolute_change: 150, pct_change: 15.0 },
    { country: 'Indonesia', co2_1990: 300, co2_latest: 840, absolute_change: 540, pct_change: 180.0 },
    { country: 'Iran', co2_1990: 300, co2_latest: 660, absolute_change: 360, pct_change: 120.0 },
    { country: 'Saudi Arabia', co2_1990: 250, co2_latest: 800, absolute_change: 550, pct_change: 220.0 },
    { country: 'South Korea', co2_1990: 400, co2_latest: 780, absolute_change: 380, pct_change: 95.0 },
  ],
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

// JumpLinks (SPEC.md §5.19) calls design-system's useReducedMotion during render -- jsdom has
// no window.matchMedia at all, so every test needs this stub regardless of whether it cares
// about reduced motion specifically.
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
  vi.mocked(useYearAnimation).mockReturnValue(DEFAULT_ANIMATION);
  mockReducedMotion(false);
});

afterEach(() => {
  // Not vi.unstubAllGlobals() -- that would also wipe the global ResizeObserver stub
  // src/test/setup.ts establishes once for the whole file (design-system's DataTable needs
  // it), breaking every test after the first. beforeEach already re-stubs matchMedia fresh
  // before each test, so there's nothing stale left for this to clean up anyway.
  vi.clearAllMocks();
  document.documentElement.removeAttribute('style');
});

describe('OverviewPage', () => {
  it('shows a loading state, then renders all three KPI rows from the API response', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
    // The picker card's hint is computed from the selection and the expanded list, not typed in.
    expect(screen.getByText('10 of 10 max · from the 11 Expanded countries · drives the Selected tier and every chart below')).toBeInTheDocument();
    // Both the map and the Selected-tier bar chart share this exact title when their years
    // coincide (as in this fixture) -- assert the expected count of 2, not just >0.
    expect(screen.getAllByText('CO₂ Emissions by Country (2024)')).toHaveLength(2);
    expect(screen.getByText('All Countries')).toBeInTheDocument();
    expect(screen.getByText('Expanded (Coverage + ≥100 Mt)')).toBeInTheDocument();
    expect(screen.getByText('Selected')).toBeInTheDocument();
    // Each tier row carries its own inline 'CO₂ (2024)' metric label (SPEC.md §5.18.2's
    // heading-above-a-metric-strip layout, one per tier: All Countries/Expanded/Selected).
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

  it("gives the map's no-data color the live-resolved theme value, not a hardcoded literal (Claude Design theme-adherence review, C4)", async () => {
    // Set directly on documentElement (resolveThemeColorHex.ts's own fallback target when no
    // [data-theme] element exists, the case here) so the resolved color is provably not the
    // hardcoded fallback -- proving live theme resolution actually wires through to this
    // page's chart props, not just covered in isolation by the resolver's own unit tests.
    document.documentElement.style.setProperty('--__s9cmpx-chart-surface-text-weak', '#abcdef');
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('Selected');

    const mapChart = screen.getAllByTestId('sychart').find((el) => el.hasAttribute('data-no-data-color'));
    expect(mapChart).toHaveAttribute('data-no-data-color', '#abcdef');
  });

  it('colors the % Change bar chart so an increase in emissions reads as the negative/bad end of the diverging scale, not the positive end', async () => {
    // Live-resolved (not the hardcoded fallback) to prove this page's wiring, same rationale
    // as the no-data-color test above -- SyChart's default stop order would put `high` (teal,
    // the "high value" end) on this chart's largest positive pct_change (China's +412.4%,
    // an increase/bad reading), which reads backwards; resolveDivergingScaleReversedHex swaps
    // the order so the increase end gets `low`/brown instead.
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-low', '#111111');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-high', '#333333');
    // Mid comes from --__s9cmpx-color-brand-100, not --__s9cmpx-chart-diverging-mid (round 2:
    // the latter is the panel background itself, which read as "empty" at near-zero values).
    document.documentElement.style.setProperty('--__s9cmpx-color-brand-100', '#222222');
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('Selected');

    const barChart = screen.getAllByTestId('sychart').find((el) => el.hasAttribute('data-bar-color-scale'));
    expect(barChart).toHaveAttribute(
      'data-bar-color-scale',
      JSON.stringify([
        [0, '#333333'],
        [0.5, '#222222'],
        [1, '#111111'],
      ]),
    );
    // top_movers' largest-magnitude pct_change is India's 452.6 -- colorRange must be
    // symmetric around it so 0% change (no change) still lands on the scale's true midpoint.
    expect(barChart).toHaveAttribute('data-bar-color-range', JSON.stringify([-452.6, 452.6]));
  });

  it('renders the headline sentence (with its "Since 1990" eyebrow), bolding country names and coloring increase/decrease values', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByText('Since 1990')).toBeInTheDocument();
    // The sentence now renders as multiple child nodes (bolded country names, colored values),
    // not one text node -- match on the <p>'s full textContent instead of a single string node.
    const expectedText =
      'Among the top 10 emitters by 2024 output, China has grown the most in absolute terms (+9,806 MtCO₂), while India has the fastest growth rate (+452.5%). ' +
      'United States has stayed comparatively flat (-4.4%), while Germany and Russia show the steepest declines (-45.7%, -29.8%).';
    const paragraph = screen.getByText((_, element) => element?.tagName === 'P' && element.textContent === expectedText);
    expect(paragraph).toBeInTheDocument();

    // Country names are bolded (SPEC.md §5.18.6).
    expect(within(paragraph).getByText('China').tagName).toBe('STRONG');
    expect(within(paragraph).getByText('India').tagName).toBe('STRONG');

    // An increase in emissions (more CO2, bad) is colored NEGATIVE_COLOR; a decrease (good) is
    // colored POSITIVE_COLOR -- the same convention TierSummaryPanel's % Change column uses.
    expect(within(paragraph).getByText('+452.5%')).toHaveStyle({ color: NEGATIVE_COLOR });
    expect(within(paragraph).getByText('-4.4%')).toHaveStyle({ color: POSITIVE_COLOR });

    // The "Since 1990" eyebrow already carries the timeframe -- the sentence itself must not
    // repeat it, or the two collide in the same three lines (reported live).
    expect(screen.queryByText(/since 1990/i, { selector: 'p' })).not.toBeInTheDocument();
  });

  it('colors the Fastest Growth / Largest Reduction KPI cards with the same brown/teal pair as the narrative panel and % Change chart, via KpiStat\'s deltaColor override (Claude Design theme-adherence review round 2)', async () => {
    // KpiStat is the real design-system component here (unlike SyChart, it isn't mocked in this
    // file), so this exercises the actual rendered `color` style, not a stubbed prop passthrough.
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('Since 1990');

    // Fastest Growth: absolute_change 10000 (bad/increase) -> NEGATIVE_COLOR.
    expect(screen.getByText('+10,000 MtCO₂')).toHaveStyle({ color: NEGATIVE_COLOR });
    // Largest Reduction: absolute_change -300 (good/decrease) -> POSITIVE_COLOR.
    expect(screen.getByText('-300 MtCO₂')).toHaveStyle({ color: POSITIVE_COLOR });
  });

  it('fetches world-map-series exactly once, regardless of how many times the selection changes', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    await user.click(await screen.findByRole('button', { name: 'Play' }));
    expect(DEFAULT_ANIMATION.toggle).toHaveBeenCalledTimes(1);
  });

  it('keeps Play enabled (and the slider scrubbable) when prefers-reduced-motion is set -- reduced motion stops autoplay, it does not remove the control', async () => {
    vi.mocked(useYearAnimation).mockReturnValue({ ...DEFAULT_ANIMATION, isPlaying: false, reducedMotion: true });
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByRole('button', { name: 'Play' })).toBeEnabled();
    expect(screen.getByRole('slider')).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('suppresses "% Change since 1990" on the animation\'s first frame instead of showing a misleading +0.0%', async () => {
    vi.mocked(useYearAnimation).mockReturnValue({ ...DEFAULT_ANIMATION, currentYear: 2023 });
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('Selected');

    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }

    // The warning now appears once per gated section (By Country, Top Movers/% Change) --
    // headings for both sit outside the selected.length gate (SPEC.md §5.19, so #by-country/
    // #pct-change are always real jump targets), so each renders its own InlineAlert instead
    // of one shared alert for the whole block.
    expect(await screen.findAllByText('Select at least one country.')).toHaveLength(2);
    expect(screen.queryByText('Selected')).not.toBeInTheDocument();
    // All Countries/Expanded stay rendered regardless of the (now empty) selection.
    expect(screen.getByText('All Countries')).toBeInTheDocument();
    expect(screen.getByText('Expanded (Coverage + ≥100 Mt)')).toBeInTheDocument();
    // headline_movers (SPEC.md §5.18.5) is a fixed top-10-emitters set from the server,
    // completely independent of `selected` -- unlike the old top_movers-backed headline, it
    // must stay visible even when every country has been deselected from the picker.
    expect(await screen.findByText('Since 1990')).toBeInTheDocument();
    // #by-country/#pct-change (SPEC.md §5.19) stay real, jumpable DOM targets even with 0
    // selected -- previously this whole block was one InlineAlert-or-fragment ternary with no
    // persistent element for a jump-nav link to land on.
    expect(document.getElementById('by-country')).not.toBeNull();
    expect(document.getElementById('pct-change')).not.toBeNull();
  });

  it('renders a Jump To nav under the h1 linking to all three sections', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    // "Climate signal" always leads (the emissions KPIs stand on their own); "Relationship" only joins when the climate data is there.
    expect(links.map((l) => l.textContent)).toEqual(['Climate signal', 'Map', 'By Country', '% Change']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#climate-signal', '#map', '#by-country', '#pct-change']);
    expect(document.getElementById('map')).not.toBeNull();
  });

  it('"Reset to default" restores the featured selection and refetches', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('Selected');

    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }
    await screen.findAllByText('Select at least one country.');

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
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when the world-map-series API call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockRejectedValue(new ApiError(503, 'Failed to load map data.'));
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load map data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.overview)).not.toHaveBeenCalled();
  });

  it('opens with the countries named in ?countries= as its Selected tier, keeping an explicit empty selection empty', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { unmount } = render(<MemoryRouter initialEntries={['/overview?countries=vietnam&countries=Atlantis']}><OverviewPage /></MemoryRouter>);
    await screen.findByText('All Countries');
    expect(vi.mocked(api.overview)).toHaveBeenCalledWith(['Vietnam']);
    unmount();
    vi.mocked(api.overview).mockClear();
    render(<MemoryRouter initialEntries={['/overview?countries=']}><OverviewPage /></MemoryRouter>);
    await screen.findByText('All Countries');
    expect(await screen.findAllByText('Select at least one country.')).not.toHaveLength(0);
  });

  it('outlines the picker\'s selection on the map via its own SyChart prop (ISO codes), following ?countries=', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD_MAP_SERIES);
    const { unmount } = render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('All Countries');
    const map = () => screen.getAllByTestId('sychart').find((el) => el.hasAttribute('data-outline'))!;
    // Default selection is the 10 featured; only China is in this 2-country fixture series.
    expect(map()).toHaveAttribute('data-outline', '["CHN"]');
    expect(screen.getByText('Outlined = your selected countries')).toBeInTheDocument();
    unmount();
    render(<MemoryRouter initialEntries={['/overview?countries=vietnam']}><OverviewPage /></MemoryRouter>);
    await screen.findByText('All Countries');
    expect(map()).toHaveAttribute('data-outline', '["VNM"]');
  });

  it('offers a Table view of every country for the current year (largest first, "No data" included), and back', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue({ ...WORLD_MAP_SERIES, iso_codes: ['CHN', 'VNM', 'XXX'], countries: ['China', 'Vietnam', 'Nowhere'], values: [[14350, 21, null], [25324, 370, null]] });
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    await screen.findByText('All Countries');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    const toggle = screen.getByRole('button', { name: 'Table view' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(toggle);
    const table = screen.getByRole('table', { name: /CO₂ by country, 2024 \(MtCO₂\) — all 3 countries/ });
    const rows = within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell').map((c) => c.textContent));
    expect(rows).toEqual([['China', '25,324'], ['Vietnam', '370'], ['Nowhere', 'No data']]);
    expect(screen.getByRole('button', { name: 'Map view' })).toHaveAttribute('aria-pressed', 'true');

    await user.click(screen.getByRole('button', { name: 'Map view' }));
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});


// ---------------------------------------------------------------- Area 2: climate signal (Release 21, Phase 2.2)

// Two years only, as above; the climate series add 1970-style context via the same fixture.
const LONG_MAP: WorldMapTimeSeries = {
  iso_codes: ['CHN', 'VNM'], countries: ['China', 'Vietnam'], years: [1970, 1990, 2023, 2024],
  values: [[800, 5], [2400, 20], [14350, 21], [25324, 370]], value_range: [5, 25324],
};

function mountWithClimate() {
  vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
  vi.mocked(api.overview).mockResolvedValue(RESPONSE);
  vi.mocked(api.worldMapSeries).mockResolvedValue(LONG_MAP);
  vi.mocked(api.correlationEmissionsTemperature).mockResolvedValue(PAIR);
  vi.mocked(api.correlationTemperature).mockImplementation(async (o) => (o?.view === 'mean5y' ? TEMPERATURE_MEAN5Y : TEMPERATURE));
  vi.mocked(api.correlationConcentration).mockResolvedValue(CONCENTRATION);
  return render(<MemoryRouter><OverviewPage /></MemoryRouter>);
}

describe('OverviewPage — climate signal', () => {
  it('has the #climate-signal and #relationship anchors the Landing CTA and the jump links point at, in order, with the jump links first', async () => {
    mountWithClimate();
    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    expect(within(nav).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual(['#climate-signal', '#relationship', '#map', '#by-country', '#pct-change']);
    expect(CLIMATE_SIGNAL_ANCHOR).toBe('climate-signal'); // the Landing's primary CTA is /overview#climate-signal
    expect(document.getElementById(CLIMATE_SIGNAL_ANCHOR)).not.toBeNull();
    expect(document.getElementById(RELATIONSHIP_ANCHOR)).not.toBeNull();
    const ids = ['climate-signal', 'relationship', 'map', 'by-country'].map((id) => document.getElementById(id)!);
    ids.slice(1).forEach((el, i) => expect(ids[i].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy());
    // sticks to the top while scrolling
    expect((nav.parentElement as HTMLElement).style.position).toBe('sticky');
  });

  it('shows the four KPI cards with figures from the API, each at its own year', async () => {
    mountWithClimate();
    const section = (await screen.findByRole('region', { name: 'What is happening globally' }));
    expect(within(section).getByText('CO₂ emissions · 2024')).toBeInTheDocument();
    expect(within(section).getByText('37,406')).toBeInTheDocument();
    expect(within(section).getByText('Change since baseline')).toBeInTheDocument();
    expect(within(section).getByText('168.6')).toBeInTheDocument(); // 100 + 68.6
    expect(within(section).getByText('+68.6% · 1990 = 100')).toBeInTheDocument();
    expect(within(section).getByText('Atmospheric CO₂ · 2024')).toBeInTheDocument();
    expect(within(section).getByText('424.6')).toBeInTheDocument();
    expect(within(section).getByText('+48.0% vs pre-industrial (1850)')).toBeInTheDocument(); // 424.6 / 286.8
    expect(within(section).getByText('Temperature anomaly · 2024')).toBeInTheDocument();
    expect(within(section).getByText('+1.62 °C')).toBeInTheDocument();
    expect(within(section).getByText('5-year mean 1.39 °C')).toBeInTheDocument();
  });

  it('every KPI carries its baseline as a chip and the full baseline detail behind the ⓘ (requirements §2.5)', async () => {
    mountWithClimate();
    const section = await screen.findByRole('region', { name: 'What is happening globally' });
    expect(within(section).getAllByText(/^Baseline /).length).toBeGreaterThanOrEqual(4);
    expect(within(section).getByText('Baseline 1850–1900 · Berkeley Earth')).toBeInTheDocument();
    const info = within(section).getByRole('button', { name: 'Baseline details: Change since baseline' });
    fireEvent.click(info);
    const panel = within(section).getByRole('region', { name: 'Baseline for Change since baseline' });
    for (const text of ['1990 = 100', 'World total in 1990', 'value ÷ value1990 × 100', 'OWID, 1970–2024', 'None']) expect(panel).toHaveTextContent(text);
    fireEvent.click(within(section).getByRole('button', { name: 'Baseline details: Temperature anomaly · 2024' }));
    expect(within(section).getByRole('region', { name: 'Baseline for Temperature anomaly · 2024' })).toHaveTextContent(/vintage 2025-01-10/);
  });

  it('shows the relationship chart over time on two axes by default, and swaps to the cumulative scatter with the toggle', async () => {
    mountWithClimate();
    const section = await screen.findByRole('region', { name: 'Why the trend matters' });
    expect(within(section).getByRole('heading', { level: 3, name: 'CO₂ emissions and temperature anomaly, 1970–2024' })).toBeInTheDocument();
    const chart = within(section).getByTestId('sychart');
    expect(chart).toHaveAttribute('data-axes', JSON.stringify(['y', 'y2'])); // emissions on the left axis, temperature on the right
    expect(within(section).getByText(/^Purpose:/)).toBeInTheDocument();
    expect(within(section).getByText(/Long-term co-movement, shown as context. No single factor or year explains warming./)).toBeInTheDocument();
    expect(within(section).getByText('Baseline 1970–2024 annual · OWID + Berkeley Earth')).toBeInTheDocument();
    fireEvent.click(within(section).getByRole('radio', { name: 'Against cumulative CO₂' }));
    expect(within(section).getByRole('heading', { level: 3, name: 'Temperature anomaly vs cumulative CO₂, 1850–2024' })).toBeInTheDocument();
    expect(within(section).queryByTestId('sychart')).not.toBeInTheDocument();
    expect(within(section).getByRole('img', { name: /scatter chart, one dot per year/i })).toBeInTheDocument();
    expect(within(section).getByText('Baseline 1850–1900 · Berkeley Earth')).toBeInTheDocument();
  });

  it('explains the chain in the "Why emissions matter" card (data-driven) and links to the correlation module without attributing warming to a country', async () => {
    mountWithClimate();
    const card = (await screen.findByText('Why emissions matter')).closest('aside')!;
    expect(card).toHaveTextContent(/concentration of CO₂ in the atmosphere \(now 424.6 ppm\)/);
    expect(card).toHaveTextContent(/radiative forcing/);
    expect(card).toHaveTextContent(/temperature anomaly: \+1.62 °C in 2024/);
    expect(card).toHaveTextContent(/accumulated global forcing and the response of the ocean and climate system, not only this year’s emissions/);
    expect(card).toHaveTextContent(/do not assign warming to any country/);
    expect(within(card).getByRole('link', { name: /Temperature & GHG Correlation module/ })).toHaveAttribute('href', '/climate-correlation');
  });

  it('states the sources, the not-a-climate-model note and the Berkeley vintage caveat behind "Sources & method"', async () => {
    mountWithClimate();
    const section = await screen.findByRole('region', { name: 'Why the trend matters' });
    expect(within(section).getByText('Sources & method')).toBeInTheDocument();
    expect(within(section).getByText(/not a climate model/i)).toBeInTheDocument();
    expect(within(section).getByText(/vintage 2025-01-10/)).toBeInTheDocument();
    expect(within(section).getByRole('link', { name: 'Full methodology →' })).toHaveAttribute('href', '/climate-correlation#methodology');
  });

  it('leaves the climate cards, the relationship section and its jump link out when the climate data fails, never showing zeros', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.overview).mockResolvedValue(RESPONSE);
    vi.mocked(api.worldMapSeries).mockResolvedValue(LONG_MAP);
    vi.mocked(api.correlationEmissionsTemperature).mockRejectedValue(new ApiError(503, 'climate data missing'));
    vi.mocked(api.correlationTemperature).mockResolvedValue(TEMPERATURE);
    vi.mocked(api.correlationConcentration).mockResolvedValue(CONCENTRATION);
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
    const section = await screen.findByRole('region', { name: 'What is happening globally' });
    expect(within(section).getByText('CO₂ emissions · 2024')).toBeInTheDocument(); // the emissions cards stand alone
    expect(within(section).getByText('Change since baseline')).toBeInTheDocument();
    expect(within(section).queryByText(/Atmospheric CO₂/)).not.toBeInTheDocument();
    expect(within(section).queryByText(/Temperature anomaly/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Why the trend matters' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Jump links' })).queryByRole('link', { name: 'Relationship' })).not.toBeInTheDocument();
  });

  it('does not hold the page back indefinitely when the climate request stalls: renders after a bound, and shows the climate parts if they arrive late', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
      vi.mocked(api.overview).mockResolvedValue(RESPONSE);
      vi.mocked(api.worldMapSeries).mockResolvedValue(LONG_MAP);
      let late: (v: typeof PAIR) => void = () => {};
      vi.mocked(api.correlationEmissionsTemperature).mockReturnValue(new Promise((r) => { late = r; }));
      vi.mocked(api.correlationTemperature).mockResolvedValue(TEMPERATURE);
      vi.mocked(api.correlationConcentration).mockResolvedValue(CONCENTRATION);
      render(<MemoryRouter><OverviewPage /></MemoryRouter>);
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      expect(screen.queryByRole('heading', { level: 1, name: 'Overview' })).not.toBeInTheDocument(); // still within the bound
      await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
      expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
      expect(screen.queryByRole('region', { name: 'Why the trend matters' })).not.toBeInTheDocument();
      await act(async () => { late(PAIR); await vi.advanceTimersByTimeAsync(100); });
      expect(screen.getByRole('region', { name: 'Why the trend matters' })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
