import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { ApiError } from '../api/types';
import type { MoverRow, OverviewResponse, OverviewTierMetrics, WorldMapTimeSeries } from '../api/types';
import type { CorrelationConcentrationResponse, CorrelationEmissionsTemperatureResponse, CorrelationTemperatureResponse, SeriesPoint } from '../api/correlationTypes';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { FORECAST_END_YEAR, SCENARIO_END_YEAR } from '../constants';
import LandingPage from './LandingPage';

vi.mock('../api/client', () => ({
  api: { overview: vi.fn(), worldMapSeries: vi.fn(), correlationEmissionsTemperature: vi.fn(), correlationTemperature: vi.fn(), correlationConcentration: vi.fn() },
}));
vi.mock('../hooks/useYearAnimation');

// Globe's canvas/d3 rendering is design-system's own concern (its own stories) -- stubbed, but it
// surfaces the props this page wires so a test can assert them.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    Globe: (props: Record<string, unknown>) => (
      <div
        data-testid="globe"
        data-year-index={String(props.yearIndex)}
        data-iso={(props.isoCodes as string[]).join(',')}
        data-range={JSON.stringify(props.colorRange)}
        data-rotation-ms={String(props.rotationPeriodMs)}
        data-blend-ms={String(props.blendMs)}
        data-show-labels={String(props.showLabels)}
        data-show-legend={String(props.showLegend)}
        data-show-controls={String(props.showControls)}
        data-auto-rotate={String(props.autoRotate)}
        data-allow-spin-reduced={String(props.allowSpinWithReducedMotion)}
        data-transparent={String(props.transparent)}
        data-no-data-color={String(props.noDataColor)}
        aria-label={String(props.ariaLabel)}
      />
    ),
  };
});

beforeAll(() => {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null,
  }));
});

const mover = (country: string, from: number, to: number): MoverRow => ({
  country, co2_1990: from, co2_latest: to, absolute_change: to - from, pct_change: ((to - from) / from) * 100,
});

const tier = (label: OverviewTierMetrics['label'], count: number, byYear: number[]): OverviewTierMetrics => ({
  label, countries_count: count, latest_year: 2024, latest_co2_total: byYear[byYear.length - 1], co2_1990_total: byYear[0],
  pct_change_since_1990: ((byYear[byYear.length - 1] - byYear[0]) / byYear[0]) * 100, co2_by_year: byYear,
});

// Three years, four countries. World totals are the column sums, as in the real API.
const MAP: WorldMapTimeSeries = {
  iso_codes: ['AAA', 'BBB', 'CCC', 'DDD'],
  countries: ['Alpha', 'Beta', 'Gamma', 'Delta'],
  years: [2022, 2023, 2024], // contiguous, as in the real API (the page indexes by year - firstYear)
  values: [
    [100, 50, 10, 90],
    [100, 120, 12, 40],
    [100, 300, 12, 15],
  ],
  value_range: [1, 300],
};
const WORLD = MAP.values.map((row) => row.reduce<number>((s, v) => s + (v ?? 0), 0)); // 250, 272, 427

function overview(over: Partial<OverviewResponse> = {}, expanded = 12): OverviewResponse {
  return {
    all_countries: tier('All Countries', 4, WORLD),
    expanded_countries: tier('Expanded', expanded, WORLD),
    selected: tier('Selected', 2, []),
    selected_country_list: [], latest_year_bar: [], top_movers: [],
    headline_movers: [mover('Alpha', 100, 100), mover('Beta', 50, 300), mover('Gamma', 10, 12), mover('Delta', 90, 15)],
    fastest_growth: mover('Beta', 50, 300), largest_reduction: mover('Delta', 90, 15), world_map: [],
    ...over,
  };
}

const ANIMATION = { currentYear: 2023, isPlaying: true, play: vi.fn(), pause: vi.fn(), toggle: vi.fn(), seek: vi.fn(), reducedMotion: false };

function mount(o: OverviewResponse = overview(), m: WorldMapTimeSeries = MAP, anim: typeof ANIMATION = ANIMATION) {
  vi.mocked(api.overview).mockResolvedValue(o);
  vi.mocked(api.worldMapSeries).mockResolvedValue(m);
  vi.mocked(useYearAnimation).mockReturnValue(anim);
  return render(<MemoryRouter><LandingPage /></MemoryRouter>);
}

afterEach(() => vi.clearAllMocks());

describe('LandingPage', () => {
  it('shows the headline and a way in while loading, then the sections', async () => {
    vi.mocked(api.overview).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.worldMapSeries).mockReturnValue(new Promise(() => {}));
    render(<MemoryRouter><LandingPage /></MemoryRouter>);
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂ comes from/i })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Loading');
    expect(screen.getByRole('link', { name: 'Explore the data' })).toHaveAttribute('href', '/overview');
  });

  it('keeps the headline and CTA and shows the message when the API fails', async () => {
    vi.mocked(api.overview).mockRejectedValue(new ApiError(503, 'Data files missing'));
    vi.mocked(api.worldMapSeries).mockResolvedValue(MAP);
    render(<MemoryRouter><LandingPage /></MemoryRouter>);
    expect(await screen.findByText('Data files missing')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Explore the data' })).toBeInTheDocument();
  });

  it('computes the hero KPIs, eyebrow and lede from the API responses (no literals)', async () => {
    mount();
    expect(await screen.findByText('OUR WORLD IN DATA CO₂ · 2022–2024 · 4 countries', { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/Emissions for 4 countries since 2022, ETS\(A,Ad,N\) forecasts to/)).toBeInTheDocument();
    expect(screen.getByText('427')).toBeInTheDocument(); // latest_co2_total
    expect(screen.getByText('MtCO₂ in 2024, all countries')).toBeInTheDocument();
    expect(screen.getByText('+70.8%')).toBeInTheDocument(); // (427-250)/250
    expect(screen.getByText('Change since 2022')).toBeInTheDocument();
    expect(screen.getByText('Countries in the Expanded set').previousElementSibling).toHaveTextContent('12');
    expect(screen.getByText(new RegExp(`ETS\\(A,Ad,N\\) forecasts to ${FORECAST_END_YEAR}.*pathways to ${SCENARIO_END_YEAR}`))).toBeInTheDocument();
    // Only ETS carries 2043 forecasts in the UI -- the lede must not credit regression/RF with them.
    expect(screen.queryByText(/regression and Random Forest/)).not.toBeInTheDocument();
  });

  it('feeds the globe the map series, its own value range, and the animation year', async () => {
    mount();
    const globe = await screen.findByTestId('globe');
    expect(globe).toHaveAttribute('data-iso', 'AAA,BBB,CCC,DDD');
    expect(globe).toHaveAttribute('data-range', '[1,300]');
    expect(globe).toHaveAttribute('data-year-index', '1'); // currentYear 2023 - first year 2022
    // one full turn across the whole pass (3 years = 2 steps of 700 ms), colours blended over each step
    expect(globe).toHaveAttribute('data-rotation-ms', '1400');
    expect(globe).toHaveAttribute('data-blend-ms', '700');
    expect(globe).toHaveAttribute('data-auto-rotate', 'true');
  });

  it('spins the globe exactly while Play is running -- also under reduced motion, where Play is the user asking for it', async () => {
    const { unmount } = mount();
    expect(await screen.findByTestId('globe')).toHaveAttribute('data-auto-rotate', 'true');
    unmount();
    const paused = mount(overview(), MAP, { ...ANIMATION, isPlaying: false });
    expect(await screen.findByTestId('globe')).toHaveAttribute('data-auto-rotate', 'false');
    paused.unmount();
    // Reduced motion: no autoplay means isPlaying starts false (nothing spins at rest)...
    const reducedIdle = mount(overview(), MAP, { ...ANIMATION, isPlaying: false, reducedMotion: true });
    const idle = await screen.findByTestId('globe');
    expect(idle).toHaveAttribute('data-auto-rotate', 'false');
    reducedIdle.unmount();
    // ...but once the user presses Play it spins, and the Globe is told that's allowed.
    mount(overview(), MAP, { ...ANIMATION, isPlaying: true, reducedMotion: true });
    const spinning = await screen.findByTestId('globe');
    expect(spinning).toHaveAttribute('data-auto-rotate', 'true');
    expect(spinning).toHaveAttribute('data-allow-spin-reduced', 'true');
  });

  it('describes only ETS as the source of the 2043 forecasts in the feature card', async () => {
    mount();
    expect(await screen.findByText(/^ETS\(A,Ad,N\) forecasts to 2043 for all 12 Expanded countries, with 95% confidence bands, benchmarked against Linear Regression and Random Forest\.$/)).toBeInTheDocument();
    expect(screen.queryByText(/Random Forest and ETS/)).not.toBeInTheDocument();
  });

  it('draws the globe without its own panel background, and shows the year/total once while paused (the hidden overlay copy lives inside the Globe)', async () => {
    mount(overview(), MAP, { ...ANIMATION, isPlaying: false });
    expect(await screen.findByTestId('globe')).toHaveAttribute('data-transparent', 'true');
    // The page renders the year + total block above the globe (CSS shows it on phones, hides it on wide screens);
    // the overlay copy is passed to Globe as `title`, which the stub doesn't render -- so exactly one here.
    expect(screen.getAllByText('all countries')).toHaveLength(1);
    expect(screen.getByText('272 MtCO₂')).toBeInTheDocument(); // the animation's current year (2023) total, from the series itself
  });

  it('while the globe plays, the legend, controls, total and year slider stay; only the per-country MtCO₂ labels are hidden', async () => {
    mount(); // ANIMATION is playing
    const globe = await screen.findByTestId('globe');
    expect(globe).toHaveAttribute('data-show-labels', 'false');
    expect(globe).not.toHaveAttribute('data-show-legend', 'false'); // left at the Globe's default (shown)
    expect(globe).not.toHaveAttribute('data-show-controls', 'false');
    expect(screen.getByText('272 MtCO₂')).toBeInTheDocument();
    expect(screen.getByText('all countries')).toBeInTheDocument();
    expect(screen.getByRole('slider')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });

  it('when the globe is not spinning the per-country labels appear, with everything else unchanged -- also under reduced motion, which starts paused', async () => {
    const { unmount } = mount(overview(), MAP, { ...ANIMATION, isPlaying: false });
    const globe = await screen.findByTestId('globe');
    expect(globe).toHaveAttribute('data-show-labels', 'true');
    expect(screen.getByRole('slider')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    unmount();
    mount(overview(), MAP, { ...ANIMATION, isPlaying: false, reducedMotion: true });
    expect(await screen.findByTestId('globe')).toHaveAttribute('data-show-labels', 'true');
  });

  it('asks the API for the globe\'s 1970 range and keeps the 1990-based view for the rest of the page', async () => {
    mount();
    await screen.findByTestId('globe');
    expect(api.worldMapSeries).toHaveBeenCalledWith(1970);
  });

  it('picks the three stories from the headline movers, with their figures and deep links', async () => {
    mount();
    const stories = await screen.findByRole('heading', { name: /three stories in 3 years of data/i });
    const section = stories.closest('section')!;
    expect(within(section).getByText('Among the 4 largest emitters of 2024, 2022 → 2024.')).toBeInTheDocument();
    const cards = within(section).getAllByRole('article');
    expect(cards).toHaveLength(3);
    expect(within(cards[0]).getByText('Beta · largest absolute rise')).toBeInTheDocument();
    expect(within(cards[0]).getByText('+250')).toBeInTheDocument();
    expect(within(cards[1]).getByText('Beta · fastest growth')).toBeInTheDocument();
    expect(within(cards[1]).getByText('+500.0%')).toBeInTheDocument();
    expect(within(cards[2]).getByText('Delta · steepest decline')).toBeInTheDocument();
    expect(within(cards[2]).getByText('−83.3%')).toBeInTheDocument();
    expect(within(cards[0]).getByRole('link', { name: 'Open Beta’s profile →' })).toHaveAttribute('href', '/country-profile?country=Beta');
    expect(within(cards[1]).getByRole('link', { name: 'See Beta in Historical Trends →' })).toHaveAttribute('href', '/historical?countries=Beta');
    expect(within(cards[2]).getByRole('link', { name: /See % change on the Overview/ })).toHaveAttribute('href', '/overview#pct-change');
  });

  it('drops the decline card (and retitles the section) when nothing declined', async () => {
    mount(overview({ headline_movers: [mover('Alpha', 10, 20), mover('Beta', 10, 15)] }));
    expect(await screen.findByRole('heading', { name: /two stories in 3 years of data/i })).toBeInTheDocument();
    expect(screen.queryByText(/steepest decline/i)).not.toBeInTheDocument();
  });

  it('renders no stories section at all when no mover has usable figures', async () => {
    mount(overview({ headline_movers: [{ country: 'X', co2_1990: null, co2_latest: null, absolute_change: null, pct_change: null }] }));
    await screen.findByTestId('globe');
    expect(screen.queryByRole('heading', { name: /stories/i })).not.toBeInTheDocument();
  });

  it('shows the real final-year top ranking and its share of the world total', async () => {
    mount();
    const race = (await screen.findByRole('heading', { name: /countries, \d+% of the world’s co₂/i })).closest('section')!;
    // Final year (no autoplay without IntersectionObserver): 300+100+15+12 = 427 of 427 -> 100%.
    expect(within(race).getByRole('heading', { name: '10 countries, 100% of the world’s CO₂' })).toBeInTheDocument();
    const list = within(race).getByRole('list', { name: /largest emitters in 2024/i });
    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Beta: 300', 'Alpha: 100', 'Delta: 15', 'Gamma: 12',
    ]);
    expect(within(race).getByText(/bar length on a fixed 0–300 scale/)).toBeInTheDocument();
  });

  it('follows the fixture for counts in feature/CTA copy rather than literals', async () => {
    mount(overview({}, 7));
    expect(await screen.findByText(/for all 7 Expanded countries/)).toBeInTheDocument();
    expect(screen.getByText(/any of the 7 Expanded countries/)).toBeInTheDocument();
    expect(screen.getByText(/Compare any 10 of 7 countries/)).toBeInTheDocument();
    expect(screen.getByText(/cumulative 2025–2040 totals/)).toBeInTheDocument();
  });

  it('links every dashboard page from the feature cards, About excluded, plus the agent', async () => {
    mount();
    const features = (await screen.findByRole('heading', { name: 'Everything you need to read the trend' })).closest('section')!;
    const hrefs = within(features).getAllByRole('link').map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/overview', '/historical', '/country-profile', '/data-explorer', '/climate-correlation', '/forecasts', '/scenarios', '/ask']);
  });
});


// ---------------------------------------------------------------- Area 2: climate-signal carousel (Release 21, Phase 2.1)

const env = { schema_version: 1, generated_at: null, note: '', caveats: [], attribution: [], source_vintage: null };
const sp = (year: number, value: number | null): SeriesPoint => ({ year, month: null, value, uncertainty: null, deseasonalized: null });
const indicator = { id: 'i', name: 'i', unit: 'u', kind: 'level', decimals: null, description: null };
const PAIR: CorrelationEmissionsTemperatureResponse = {
  ...env, source: 'owid_co2', variant: 'total', baseline: 'preindustrial', window: [1850, 2024], x: indicator, y: indicator, n_years: 175,
  points: [{ year: 1850, cumulative_emissions: 2_910, temperature: -0.13 }, { year: 1950, cumulative_emissions: 900_000, temperature: 0.1 }, { year: 2024, cumulative_emissions: 2_751_504, temperature: 1.62 }],
  omitted_years: [], fit: { slope: 0.5196, ci95_hac: [0.48, 0.559], r_squared: 0.9, n_years: 175, start: 1850, end: 2024, unit: '°C per 1,000 GtCO2' }, fit_context: {}, warnings: [], notes: [],
};
const SERIES = (points: SeriesPoint[]): CorrelationTemperatureResponse & CorrelationConcentrationResponse => ({
  ...env, indicator, view: 'level', baseline: null, resolution: 'annual', start_year: null, end_year: null, coverage: null, points, notes: [], details: {},
});

function mountWithClimate(anim: typeof ANIMATION = ANIMATION) {
  vi.mocked(api.correlationEmissionsTemperature).mockResolvedValue(PAIR);
  vi.mocked(api.correlationTemperature).mockResolvedValue(SERIES([sp(2023, 1.5), sp(2024, 1.617)]));
  vi.mocked(api.correlationConcentration).mockResolvedValue(SERIES([sp(2024, 424.6), sp(2025, 427.35)]));
  return mount(overview(), MAP, anim);
}

describe('LandingPage — climate-signal carousel', () => {
  it('shows a two-slide carousel: the climate signal first (figures from the API, each with its own year), the existing hero second', async () => {
    mountWithClimate();
    const region = await screen.findByRole('region', { name: 'Featured' });
    expect(region).toHaveAttribute('aria-roledescription', 'carousel');
    const slides = within(region).getAllByRole('group', { hidden: true });
    expect(slides.map((s) => s.getAttribute('aria-label'))).toEqual(['1 of 2: Climate signal', '2 of 2: Where CO₂ comes from']);
    expect(screen.getByRole('heading', { level: 1, name: /global temperature has risen with the co₂ we have accumulated/i })).toBeInTheDocument();
    const banner = region.querySelector('.climate-banner') as HTMLElement;
    expect(within(banner).getByText('+1.62 °C')).toBeInTheDocument();
    expect(within(banner).getByText('2024, vs 1850–1900')).toBeInTheDocument();
    expect(within(banner).getByText('427.4 ppm')).toBeInTheDocument();
    expect(within(banner).getByText('Atmospheric CO₂, 2025')).toBeInTheDocument();
    expect(within(banner).getByText('0.52 °C')).toBeInTheDocument();
    expect(screen.getByText(/over 175 years, warming has followed the cumulative total, not any single year’s emissions/i)).toBeInTheDocument();
    // the slide hidden from assistive technology is the second (its own H1 is not exposed)
    expect(screen.queryByRole('heading', { level: 1, name: /where the world’s co₂ comes from/i })).not.toBeInTheDocument();
  });

  it('shows the four-step band below the hero when the climate data is there, and not otherwise', async () => {
    mountWithClimate();
    const band = await screen.findByRole('region', { name: 'The chain reaction, step by step' });
    expect(within(band).getAllByRole('listitem').filter((li) => li.getAttribute('aria-hidden') !== 'true')).toHaveLength(4);
    expect(within(band).getByText('Berkeley Earth', { exact: false })).toBeInTheDocument();
  });

  it('Banner 1 sends the primary CTA to the Overview climate signal and keeps Explore the data and Forecasts as secondary paths', async () => {
    mountWithClimate();
    const primary = await screen.findByRole('link', { name: 'See the climate signal' });
    expect(primary).toHaveAttribute('href', '/overview#climate-signal');
    expect(screen.getByRole('link', { name: 'Explore the data' })).toHaveAttribute('href', '/overview');
    expect(screen.getByRole('link', { name: `Forecasts to ${FORECAST_END_YEAR} →` })).toHaveAttribute('href', '/forecasts');
  });

  it('states the baseline, the sources and that the chart is context, not a climate model', async () => {
    mountWithClimate();
    await screen.findByRole('region', { name: 'Featured' });
    expect(screen.getByText('Baseline 1850–1900 · Berkeley Earth')).toBeInTheDocument();
    expect(screen.getByText(/shown as context from observed data; not a climate model/i)).toBeInTheDocument();
    expect(screen.getByText(/Source: Berkeley Earth/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /scatter chart, one dot per year from 1850 to 2024/i })).toBeInTheDocument();
  });

  it('has a Pause button first in tab order; the button alone decides auto-rotate: a manual slide change leaves it on, Pause stops it', async () => {
    mountWithClimate();
    const region = await screen.findByRole('region', { name: 'Featured' });
    const buttons = within(region).getAllByRole('button');
    expect(buttons[0]).toHaveAccessibleName('Pause automatic rotation');
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(screen.getByRole('button', { name: 'Pause automatic rotation' })).toBeInTheDocument(); // still on
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂ comes from/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: /global temperature has risen/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Pause automatic rotation' }));
    expect(screen.getByRole('button', { name: 'Start automatic rotation' })).toBeInTheDocument();
  });

  it('switches slides with the tab buttons and the arrow keys', async () => {
    mountWithClimate();
    await screen.findByRole('region', { name: 'Featured' });
    fireEvent.click(screen.getByRole('button', { name: /02\s*Where CO₂ comes from/ }));
    expect(screen.getByRole('button', { name: /02\s*Where CO₂ comes from/ })).toHaveAttribute('aria-current', 'true');
    fireEvent.keyDown(screen.getByRole('region', { name: 'Featured' }), { key: 'ArrowLeft' });
    expect(screen.getByRole('button', { name: /01\s*Climate signal/ })).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('heading', { level: 1, name: /global temperature has risen/i })).toBeInTheDocument();
  });

  it('ignores arrow keys pressed in the hero\'s Year slider: they scrub the year and do not switch slides', async () => {
    mountWithClimate({ ...ANIMATION, isPlaying: false }); // the slider is shown while the globe is paused
    await screen.findByRole('region', { name: 'Featured' });
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' })); // the hero (with its slider) is now showing
    const slider = screen.getByRole('slider');
    fireEvent.keyDown(slider, { key: 'ArrowLeft' }); // the slider handles (and prevents) its own arrow keys
    fireEvent.keyDown(slider, { key: 'ArrowRight' });
    expect(screen.getByRole('button', { name: /02\s*Where CO₂ comes from/ })).toHaveAttribute('aria-current', 'true');
    // the same key from the carousel's own controls does switch
    fireEvent.keyDown(screen.getByRole('button', { name: /02\s*Where CO₂ comes from/ }), { key: 'ArrowLeft' });
    expect(screen.getByRole('button', { name: /01\s*Climate signal/ })).toHaveAttribute('aria-current', 'true');
  });

  it('slides sideways: the next slide comes in from the right and the old one leaves left, and going back reverses it', async () => {
    mountWithClimate();
    await screen.findByRole('region', { name: 'Featured' });
    const pos = () => [...document.querySelectorAll('.hero-carousel__slide')].map((s) => s.getAttribute('data-pos'));
    expect(pos()).toEqual(['active', 'after']);
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(pos()).toEqual(['before', 'active']);
    fireEvent.click(screen.getByRole('button', { name: 'Previous slide' }));
    expect(pos()).toEqual(['active', 'after']);
  });

  it('holds the globe animation off while its slide is hidden, and on once it is shown', async () => {
    mountWithClimate();
    await screen.findByRole('region', { name: 'Featured' });
    const enabledFlags = () => vi.mocked(useYearAnimation).mock.calls.map(([o]) => o.enabled);
    expect(enabledFlags().at(-1)).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(enabledFlags().at(-1)).toBe(true);
  });

  it('falls back to the existing hero alone, with no carousel, when the climate data fails or is incomplete', async () => {
    vi.mocked(api.correlationEmissionsTemperature).mockRejectedValue(new ApiError(503, 'climate data missing'));
    vi.mocked(api.correlationTemperature).mockResolvedValue(SERIES([sp(2024, 1.6)]));
    vi.mocked(api.correlationConcentration).mockResolvedValue(SERIES([sp(2024, 424)]));
    mount();
    await screen.findByTestId('globe'); // the hero itself (the loading placeholder shares its headline)
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂ comes from/i })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Featured' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'The chain reaction, step by step' })).not.toBeInTheDocument();
    expect(screen.queryByText('+1.62 °C')).not.toBeInTheDocument();
  });

  it('stops waiting for a stalled climate request after a bound, shows the existing hero, and ignores a late answer', async () => {
    vi.useFakeTimers();
    try {
      let resolveLate: (v: CorrelationEmissionsTemperatureResponse) => void = () => {};
      vi.mocked(api.correlationEmissionsTemperature).mockReturnValue(new Promise((r) => { resolveLate = r; }));
      vi.mocked(api.correlationTemperature).mockResolvedValue(SERIES([sp(2024, 1.6)]));
      vi.mocked(api.correlationConcentration).mockResolvedValue(SERIES([sp(2024, 424)]));
      mount();
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      expect(screen.queryByTestId('globe')).not.toBeInTheDocument(); // still inside the bound: waiting
      await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
      expect(screen.getByTestId('globe')).toBeInTheDocument();
      expect(screen.queryByRole('region', { name: 'Featured' })).not.toBeInTheDocument();
      await act(async () => { resolveLate(PAIR); await vi.advanceTimersByTimeAsync(100); });
      expect(screen.queryByRole('region', { name: 'Featured' })).not.toBeInTheDocument(); // no remount, the globe is not restarted
      expect(screen.getAllByTestId('globe')).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
