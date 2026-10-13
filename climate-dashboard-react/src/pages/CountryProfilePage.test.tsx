import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, CountryCumulativeResponse, CountryProfileResponse } from '../api/types';
import CountryProfilePage from './CountryProfilePage';

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

vi.mock('../api/client', () => ({ api: { countryProfile: vi.fn(), countryCumulative: vi.fn(), listCountries: vi.fn() } }));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own
// concern, stubbed here so this page's data-wiring is what's under test. Also surfaces the
// YoY bar series' own `pointColors` (as JSON in a data attribute) so a test can assert those
// come from the resolved theme pair, not a hardcoded/stale value (Copilot review, PR #182 —
// the resolver/hook unit tests alone don't protect this page's own wiring from regressing),
// and the line series' own `color` so a test can assert the CO2/per-capita charts stay pinned
// to a fixed literal rather than resolving back to SyChart's theme-varying categorical default
// (Claude Design theme-adherence review round 2).
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: { ariaLabel?: string; height?: number; series: Array<{ kind?: string; pointColors?: string[]; color?: string }> }) => (
      <div
        data-testid="sychart"
        aria-label={props.ariaLabel}
        data-height={props.height}
        data-point-colors={JSON.stringify(props.series.find((s) => s.kind === 'bar')?.pointColors)}
        data-line-color={props.series.find((s) => s.kind === 'line')?.color}
      />
    ),
  };
});

const COUNTRIES: CountriesResponse = {
  featured: ['China', 'United States'],
  expanded: ['China', 'United States', 'India', 'Vietnam'],
};

const RESPONSE: CountryProfileResponse = {
  country: 'China',
  years: [2020, 2021],
  co2: [10000, 11000],
  co2_per_capita: [7.1, 7.4],
  yoy_years: [2021],
  yoy_values: [10.5],
  table: [{ year: 2021, co2: 11000, co2_per_capita: 7.4, co2_yoy_pct_change: 10.5, ghg_intensity: 0.3 }],
};

const CUMULATIVE: CountryCumulativeResponse = {
  country: 'China',
  years: [1970, 2024],
  cumulative_co2: [10870, 285087],
  share_of_world_cumulative: [2.6, 15.4],
  share_of_world_annual: [4.1, 31.8],
  latest: { year: 2024, cumulative_co2: 285087, share_of_world_cumulative: 15.4, rank: 2, rank_of: 215 },
};

beforeEach(() => {
  mockReducedMotion(false);
  vi.mocked(api.countryCumulative).mockResolvedValue(CUMULATIVE);
});

afterEach(() => {
  // Not vi.unstubAllGlobals() -- that would also wipe the global ResizeObserver stub
  // src/test/setup.ts establishes once for the whole file (design-system's DataTable needs
  // it), breaking every test after the first. beforeEach already re-stubs matchMedia fresh
  // before each test, so there's nothing stale left for this to clean up anyway.
  vi.clearAllMocks();
  document.documentElement.removeAttribute('style');
});

describe('CountryProfilePage', () => {
  it('renders the profile for the default (featured[0]) country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);

    expect(await screen.findByText('CO₂ Emissions — China')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('China');
  });

  it('pins the CO2 Emissions and per-capita line charts to a fixed color, not the theme-varying categorical default (Claude Design theme-adherence review round 2)', async () => {
    // No CSS var is set here at all -- proving the line color is a fixed literal (SINGLE_LINE_COLOR
    // in CountryProfilePage.tsx), not resolved from a theme token the way every other chart color
    // in this app is. Round 1 left this chart on SyChart's own per-theme categorical-default-01,
    // which happens to be near-white on Dark but yellow-green on Light -- an unintended divergence
    // since both themes render this chart on the same dark chart panel.
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions — China');

    // Grid order: CO₂ Emissions (0), CO₂ per Capita (1) -- both line charts, both pinned.
    const charts = screen.getAllByTestId('sychart');
    expect(charts[0]).toHaveAttribute('data-line-color', '#ecf0f6');
    expect(charts[1]).toHaveAttribute('data-line-color', '#ecf0f6');
  });

  it('renders a Jump To nav under the h1 linking to all five sections', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions — China');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Emissions', 'Per Capita', 'YoY Change', 'Key Statistics', 'Cumulative']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#emissions', '#per-capita', '#yoy-change', '#key-stats', '#cumulative']);
    expect(document.getElementById('emissions')).not.toBeNull();
    expect(document.getElementById('key-stats')).not.toBeNull();
  });

  it('re-fetches with a newly selected, expanded-but-not-featured country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions — China');

    vi.mocked(api.countryProfile).mockResolvedValue({ ...RESPONSE, country: 'Vietnam' });
    await user.click(screen.getByLabelText('Select a country (4 available)'));
    await user.click(await screen.findByRole('option', { name: 'Vietnam' }));

    expect(await screen.findByText('CO₂ Emissions — Vietnam')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenLastCalledWith('Vietnam');
  });

  it('expands and restores the CO₂ Emissions chart via ChartCard\'s expandable control (SPEC.md §5.11)', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions — China');

    // Grid order: CO₂ Emissions (index 0), CO₂ per Capita (index 1), then the already
    // full-width Year-on-Year chart (index 2, not expandable).
    const emissionsChart = () => screen.getAllByTestId('sychart')[0];
    expect(emissionsChart()).toHaveAttribute('data-height', '280');

    await user.click(screen.getAllByRole('button', { name: 'Expand chart' })[0]);
    expect(emissionsChart()).toHaveAttribute('data-height', '560');
    expect(screen.getByRole('button', { name: 'Restore chart' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Restore chart' }));
    expect(emissionsChart()).toHaveAttribute('data-height', '280');

    // The CO₂ per Capita chart is unaffected by this one chart's toggle.
    expect(screen.getAllByTestId('sychart')[1]).toHaveAttribute('data-height', '280');
  });

  it('maps YoY bar colors to the live-resolved diverging pair, not a hardcoded value (same brown/teal pair Overview\'s % Change chart and the Scenario Comparison treemap use)', async () => {
    // Set directly on documentElement (resolveThemeColorHex.ts's own fallback target when no
    // [data-theme] element exists, which is the case here -- this test renders the page in
    // isolation, not inside App.tsx's themed shell) so the resolved pair is provably NOT the
    // hardcoded fallback hex, proving live theme resolution actually wires through to this
    // page's pointColors rather than only being covered in isolation by the resolver's/hook's
    // own unit tests.
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-high', '#111111');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-low', '#222222');
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue({ ...RESPONSE, yoy_years: [2020, 2021], yoy_values: [10.5, -3.2] });
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
    await screen.findByText('CO₂ Emissions — China');

    // Grid order: CO₂ Emissions (0), CO₂ per Capita (1), YoY Change (2) -- same ordering the
    // expand/restore test above relies on. 10.5 (not negative) -> negative-direction color
    // (increase is bad); -3.2 (negative) -> positive-direction color (decrease is good).
    const yoyChart = screen.getAllByTestId('sychart')[2];
    expect(JSON.parse(yoyChart.getAttribute('data-point-colors')!)).toEqual(['#222222', '#111111']);
  });

  it('renders an inline error instead of crashing when the profile API call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockRejectedValue(new Error('Failed to load data.'));
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).not.toHaveBeenCalled();
  });

  it('opens the country named in ?country= and falls back to the first featured country otherwise', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { unmount } = render(<MemoryRouter initialEntries={['/country-profile?country=india']}><CountryProfilePage /></MemoryRouter>);
    await screen.findByText(/CO₂ Emissions — India/);
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('India');
    unmount();
    vi.mocked(api.countryProfile).mockClear();
    render(<MemoryRouter initialEntries={['/country-profile?country=Atlantis']}><CountryProfilePage /></MemoryRouter>);
    await screen.findByText(/CO₂ Emissions — China/);
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('China');
  });

  describe('Cumulative contribution (SPEC.md §5.28)', () => {
    function arrange() {
      vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
      vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    }

    it('counts from the first record by default and, with "From a year", asks for emissions from that year and relabels the figures', async () => {
      arrange();
      const { default: userEvent } = await import('@testing-library/user-event');
      const user = userEvent.setup();
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      await screen.findByText('285 GtCO₂');
      expect(screen.getByRole('radio', { name: 'Since records began' })).toBeChecked();
      expect(screen.getByText('Cumulative CO₂ since records began · 2024')).toBeInTheDocument();
      vi.mocked(api.countryCumulative).mockResolvedValue({ ...CUMULATIVE, from_year: 1990, years: [1990, 2024], cumulative_co2: [0, 244176], share_of_world_cumulative: [null, 22.9], latest: { year: 2024, cumulative_co2: 244176, share_of_world_cumulative: 22.9, rank: 2, rank_of: 215 } });
      await user.click(screen.getByRole('radio', { name: 'From a year' }));
      expect(await screen.findByText('Emitted since 1990 · 2024')).toBeInTheDocument();
      expect(vi.mocked(api.countryCumulative)).toHaveBeenLastCalledWith('China', 1990);
      expect(screen.getByText('244 GtCO₂')).toBeInTheDocument();
      expect(screen.getByText("Share of the world's emissions since 1990")).toBeInTheDocument();
      expect(screen.getByText('22.9%')).toBeInTheDocument();
      expect(screen.getByText('Rank by emissions since 1990 · 2024')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'Share of World CO₂ since 1990 — China' })).toBeInTheDocument();
      expect(screen.getByText(/emissions since 1990: each total minus its total the year before 1990/)).toBeInTheDocument();
      expect(screen.queryByText(/in 1990$/)).toBeNull(); // no "x% in the first year" delta: the period starts from zero
    });

    it('opens on ?from= so a link from the Ask page shows the answer\'s numbers', async () => {
      arrange();
      render(<MemoryRouter initialEntries={['/country-profile?country=China&from=1990']}><CountryProfilePage /></MemoryRouter>);
      await screen.findByRole('heading', { name: 'Cumulative contribution' });
      await waitFor(() => expect(vi.mocked(api.countryCumulative)).toHaveBeenCalledWith('China', 1990));
      expect(screen.getByRole('radio', { name: 'From a year' })).toBeChecked();
    });

    it('shows the three figures and the share chart for the selected country', async () => {
      arrange();
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      expect(await screen.findByRole('heading', { name: 'Cumulative contribution' })).toBeInTheDocument();
      expect(vi.mocked(api.countryCumulative)).toHaveBeenCalledWith('China');
      expect(await screen.findByText('285 GtCO₂')).toBeInTheDocument();
      expect(screen.getByText('15.4%')).toBeInTheDocument();
      expect(screen.getByText('2.6% in 1970')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
      expect(screen.getByText('of 215 countries')).toBeInTheDocument();
      expect(screen.getByLabelText(/share of the world's cumulative CO₂ and of each year's CO₂ emissions, 1970 to 2024/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Open in Climate Correlation' })).toHaveAttribute('href', '/climate-correlation');
    });

    it('adds a Cumulative jump link to the new section', async () => {
      arrange();
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      const nav = await screen.findByRole('navigation', { name: 'Jump links' });
      expect(within(nav).getByRole('link', { name: 'Cumulative' })).toHaveAttribute('href', '#cumulative');
      expect(document.getElementById('cumulative')).not.toBeNull();
    });

    it('keeps the rest of the profile when the cumulative request fails', async () => {
      arrange();
      vi.mocked(api.countryCumulative).mockRejectedValue(new Error('boom'));
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Key Statistics' })).toBeInTheDocument();
    });

    it('says so when the country has no cumulative data', async () => {
      arrange();
      vi.mocked(api.countryCumulative).mockResolvedValue({ ...CUMULATIVE, latest: null });
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      expect(await screen.findByText('No cumulative CO₂ data for China.')).toBeInTheDocument();
    });

    it('shows a dash when OWID has no share for the latest year', async () => {
      arrange();
      vi.mocked(api.countryCumulative).mockResolvedValue({
        ...CUMULATIVE,
        share_of_world_cumulative: [null, null],
        latest: { ...CUMULATIVE.latest!, share_of_world_cumulative: null },
      });
      render(<MemoryRouter><CountryProfilePage /></MemoryRouter>);
      expect(await screen.findByText('—')).toBeInTheDocument();
    });
  });
});
