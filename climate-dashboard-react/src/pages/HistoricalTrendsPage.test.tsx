import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { ApiError } from '../api/types';
import type {
  CountriesResponse,
  HistoricalCumulativeResponse,
  HistoricalDecadeCompositionResponse,
  HistoricalTimeseriesResponse,
} from '../api/types';
import HistoricalTrendsPage from './HistoricalTrendsPage';

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

vi.mock('../api/client', () => ({
  api: { listCountries: vi.fn(), historicalTimeseries: vi.fn(), historicalCumulative: vi.fn(), historicalDecadeComposition: vi.fn() },
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

const CUMULATIVE: HistoricalCumulativeResponse = {
  years: [1970, 2024],
  series: [{ name: 'China', cumulative_co2: [10000, 285000], share_of_world_cumulative: [2.5, 15.4], share_of_world_annual: [4, 31.8] }],
  world_cumulative_co2: [400000, 1849000],
};

const COMPOSITION: HistoricalDecadeCompositionResponse = {
  decades: [1990, 2000],
  series: [{ gas: 'co2', gas_label: 'CO₂', share: [70, 72] }],
};

beforeEach(() => {
  mockReducedMotion(false);
});

afterEach(() => {
  // Not vi.unstubAllGlobals() -- that would also wipe the global ResizeObserver stub
  // src/test/setup.ts establishes once for the whole file (design-system's DataTable needs
  // it), breaking every test after the first. beforeEach already re-stubs matchMedia fresh
  // before each test, so there's nothing stale left for this to clean up anyway.
  vi.clearAllMocks();
});

describe('HistoricalTrendsPage', () => {
  it('renders both charts once both API calls resolve', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);

    expect(await screen.findByText('CO₂ Emissions by Country')).toBeInTheDocument();
    expect(screen.getByText('GHG Composition by Decade — 10 Countries (% share)')).toBeInTheDocument();
    // Default selection is all 10 featured countries — matches Overview's Selected tier
    // default, and confirms the country MultiSelect's initial value actually reached the
    // API call.
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'co2');
    expect(vi.mocked(api.historicalDecadeComposition)).toHaveBeenCalledWith(FEATURED);
  });

  it('opens on the gas in ?gas= (so a link from the Ask page lands on the same metric) and ignores an unknown one', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { unmount } = render(<MemoryRouter initialEntries={['/historical?gas=methane']}><HistoricalTrendsPage /></MemoryRouter>);
    await screen.findByText('Methane (CH₄) Emissions by Country');
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'methane');
    unmount();

    vi.mocked(api.historicalTimeseries).mockClear();
    render(<MemoryRouter initialEntries={['/historical?gas=plutonium']}><HistoricalTrendsPage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions by Country');
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'co2');
    expect(vi.mocked(api.historicalTimeseries)).not.toHaveBeenCalledWith(FEATURED, 'plutonium');
  });

  it('renders a Jump To nav under the h1 linking to both sections', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Emissions Over Time', 'GHG Share by Decade']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#emissions-over-time', '#ghg-by-decade']);
    // Both targets exist unconditionally (headings sit outside the selection gate), regardless
    // of the default selection or loading state.
    expect(document.getElementById('emissions-over-time')).not.toBeNull();
    expect(document.getElementById('ghg-by-decade')).not.toBeNull();
  });

  it('shows a warning instead of calling the timeseries API when no countries are selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);

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
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);
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
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);
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
    render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.historicalTimeseries)).not.toHaveBeenCalled();
  });

  it('opens with the countries named in ?countries= (validated), and falls back to the defaults for junk', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
    vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    const { unmount } = render(<MemoryRouter initialEntries={['/historical?countries=vietnam&countries=Atlantis']}><HistoricalTrendsPage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions by Country');
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(['Vietnam'], 'co2');
    unmount();
    vi.mocked(api.historicalTimeseries).mockClear();
    render(<MemoryRouter initialEntries={['/historical?countries=Atlantis']}><HistoricalTrendsPage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions by Country');
    expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'co2');
  });

  describe('cumulative views (SPEC.md §5.28)', () => {
    function arrange() {
      vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
      vi.mocked(api.historicalTimeseries).mockResolvedValue(TIMESERIES);
      vi.mocked(api.historicalCumulative).mockResolvedValue(CUMULATIVE);
      vi.mocked(api.historicalDecadeComposition).mockResolvedValue(COMPOSITION);
    }

    it('keeps Annual as the default view and makes no cumulative request', async () => {
      arrange();
      render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('CO₂ Emissions by Country');
      expect(screen.getByRole('radio', { name: 'Annual' })).toBeChecked();
      expect(vi.mocked(api.historicalCumulative)).not.toHaveBeenCalled();
    });

    it('opens on ?view=cumulative: requests only the cumulative series, and says what the chart counts', async () => {
      arrange();
      render(<MemoryRouter initialEntries={['/historical?view=cumulative']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText('Cumulative CO₂ Emissions by Country')).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenCalledWith(FEATURED);
      expect(vi.mocked(api.historicalTimeseries)).not.toHaveBeenCalled();
      expect(screen.getByRole('radio', { name: 'Cumulative' })).toBeChecked();
      expect(screen.getByText(/counted from each country.s first record, shown from 1970/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Open in Climate Correlation' })).toHaveAttribute('href', '/climate-correlation');
      // The metric selector only applies to the annual view.
      expect(screen.getByLabelText('Emissions metric')).toBeDisabled();
    });

    it('switches between the three views without refetching the one it already has', async () => {
      arrange();
      const { default: userEvent } = await import('@testing-library/user-event');
      const user = userEvent.setup();
      render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('CO₂ Emissions by Country');

      await user.click(screen.getByRole('radio', { name: 'Share of world' }));
      expect(await screen.findByText("Share of the World's Cumulative CO₂")).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenCalledTimes(1);

      await user.click(screen.getByRole('radio', { name: 'Annual' }));
      expect(await screen.findByText('CO₂ Emissions by Country')).toBeInTheDocument();
    });

    it('shows no Annual / Cumulative / Share tabs for a gas other than CO₂ (only Annual exists), and brings them back for CO₂', async () => {
      arrange();
      const { unmount } = render(<MemoryRouter initialEntries={['/historical?gas=methane']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText('Methane (CH₄) Emissions by Country')).toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: 'Cumulative' })).toBeNull();
      expect(screen.queryByRole('radio', { name: 'Share of world' })).toBeNull();
      expect(screen.queryByRole('radio', { name: 'Annual' })).toBeNull(); // a switch with one option is not shown at all
      expect(screen.getByLabelText('Emissions metric')).not.toBeDisabled(); // the gas can still be changed
      unmount();
      render(<MemoryRouter initialEntries={['/historical?gas=co2']}><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('CO₂ Emissions by Country');
      for (const name of ['Annual', 'Cumulative', 'Share of world']) expect(screen.getByRole('radio', { name })).toBeInTheDocument();
    });

    it('reads a stale ?view=cumulative with a non-CO₂ gas as Annual: the annual chart, no cumulative request', async () => {
      arrange();
      render(<MemoryRouter initialEntries={['/historical?gas=methane&view=cumulative']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText('Methane (CH₄) Emissions by Country')).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).not.toHaveBeenCalled();
      expect(vi.mocked(api.historicalTimeseries)).toHaveBeenCalledWith(FEATURED, 'methane');
      expect(screen.queryByText('Cumulative CO₂ Emissions by Country')).toBeNull();
    });

    it('counts from each countrys first record by default, with the counting-from choice shown only in the cumulative views', async () => {
      arrange();
      const { default: userEvent } = await import('@testing-library/user-event');
      const user = userEvent.setup();
      render(<MemoryRouter><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('CO₂ Emissions by Country');
      expect(screen.queryByRole('radio', { name: 'Since records began' })).toBeNull(); // not in the annual view
      await user.click(screen.getByRole('radio', { name: 'Cumulative' }));
      expect(await screen.findByText('Cumulative CO₂ Emissions by Country')).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: 'Since records began' })).toBeChecked();
      expect(screen.queryByLabelText('From year')).toBeNull(); // the year choice appears only for "From a year"
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenLastCalledWith(FEATURED); // the default request carries no year
    });

    it('From a year asks the API to count from 1990 and says what the figures are', async () => {
      arrange();
      const { default: userEvent } = await import('@testing-library/user-event');
      const user = userEvent.setup();
      render(<MemoryRouter initialEntries={['/historical?view=cumulative']}><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('Cumulative CO₂ Emissions by Country');
      await user.click(screen.getByRole('radio', { name: 'From a year' }));
      expect(await screen.findByText('CO₂ Emitted Since 1990, by Country')).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenLastCalledWith(FEATURED, 1990);
      expect(screen.getByRole('combobox', { name: 'From year' })).toHaveTextContent('1990'); // the design-system Select is a button-style combobox: its displayed value
      expect(screen.getByText(/emissions since 1990: each total minus its total the year before 1990, so the chart is rebased to zero just before 1990 and the first point is 1990.s own emissions/)).toBeInTheDocument();
      expect(screen.getByText(/CO₂ a country has emitted since 1990, counted from zero just before 1990/)).toBeInTheDocument();
      await user.click(screen.getByRole('radio', { name: 'Since records began' }));
      expect(await screen.findByText('Cumulative CO₂ Emissions by Country')).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenLastCalledWith(FEATURED);
    });

    it('opens on ?from= (so the agent link shows its answer\'s numbers), in the share view too, and ignores an unrecognised year', async () => {
      arrange();
      const { unmount } = render(<MemoryRouter initialEntries={['/historical?view=share&from=2000']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText("Share of the World's CO₂ Emitted Since 2000")).toBeInTheDocument();
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenLastCalledWith(FEATURED, 2000);
      expect(screen.getByRole('radio', { name: 'From a year' })).toBeChecked();
      unmount();
      vi.mocked(api.historicalCumulative).mockClear();
      render(<MemoryRouter initialEntries={['/historical?view=cumulative&from=1850']}><HistoricalTrendsPage /></MemoryRouter>); // before the window: read as absent
      await screen.findByText('Cumulative CO₂ Emissions by Country');
      expect(vi.mocked(api.historicalCumulative)).toHaveBeenCalledWith(FEATURED);
    });

    it('a ?from= after the last data year shows the API\'s range message and keeps the year asked for in the control (no silent clamp)', async () => {
      arrange();
      vi.mocked(api.historicalCumulative).mockRejectedValue(new ApiError(422, 'from_year must be between 1970 and 2023'));
      render(<MemoryRouter initialEntries={['/historical?view=cumulative&from=2025']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText('from_year must be between 1970 and 2023')).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: 'From a year' })).toBeChecked();
      expect(screen.getByRole('combobox', { name: 'From year' })).toHaveTextContent('2025'); // not 2024: the control says what the URL asked for
    });

    it('ignores an unknown ?view= and shows the annual chart', async () => {
      arrange();
      render(<MemoryRouter initialEntries={['/historical?view=bogus']}><HistoricalTrendsPage /></MemoryRouter>);
      await screen.findByText('CO₂ Emissions by Country');
      expect(vi.mocked(api.historicalCumulative)).not.toHaveBeenCalled();
    });

    it('shows an inline error when the cumulative request fails, and keeps the rest of the page', async () => {
      arrange();
      vi.mocked(api.historicalCumulative).mockRejectedValue(new Error('boom'));
      render(<MemoryRouter initialEntries={['/historical?view=share']}><HistoricalTrendsPage /></MemoryRouter>);
      expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
      expect(await screen.findByText('GHG Composition by Decade — 10 Countries (% share)')).toBeInTheDocument();
    });
  });
});
