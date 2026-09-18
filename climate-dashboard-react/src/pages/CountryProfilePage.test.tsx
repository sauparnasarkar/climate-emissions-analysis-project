import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, CountryProfileResponse } from '../api/types';
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

vi.mock('../api/client', () => ({ api: { countryProfile: vi.fn(), listCountries: vi.fn() } }));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own
// concern, stubbed here so this page's data-wiring is what's under test. Also surfaces the
// YoY bar series' own `pointColors` (as JSON in a data attribute) so a test can assert those
// come from the resolved theme pair, not a hardcoded/stale value (Copilot review, PR #182 —
// the resolver/hook unit tests alone don't protect this page's own wiring from regressing).
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: { ariaLabel?: string; height?: number; series: Array<{ kind?: string; pointColors?: string[] }> }) => (
      <div
        data-testid="sychart"
        aria-label={props.ariaLabel}
        data-height={props.height}
        data-point-colors={JSON.stringify(props.series.find((s) => s.kind === 'bar')?.pointColors)}
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

beforeEach(() => {
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

describe('CountryProfilePage', () => {
  it('renders the profile for the default (featured[0]) country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<CountryProfilePage />);

    expect(await screen.findByText('CO₂ Emissions — China')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('China');
  });

  it('renders a Jump To nav under the h1 linking to all four sections', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<CountryProfilePage />);
    await screen.findByText('CO₂ Emissions — China');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Emissions', 'Per Capita', 'YoY Change', 'Key Statistics']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#emissions', '#per-capita', '#yoy-change', '#key-stats']);
    expect(document.getElementById('emissions')).not.toBeNull();
    expect(document.getElementById('key-stats')).not.toBeNull();
  });

  it('re-fetches with a newly selected, expanded-but-not-featured country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<CountryProfilePage />);
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
    render(<CountryProfilePage />);
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

  it('maps YoY bar colors to the live-resolved on-panel sentiment pair, not a hardcoded value (Claude Design theme-adherence review, C1)', async () => {
    // Set directly on documentElement (resolveThemeColorHex.ts's own fallback target when no
    // [data-theme] element exists, which is the case here -- this test renders the page in
    // isolation, not inside App.tsx's themed shell) so the resolved pair is provably NOT the
    // hardcoded fallback hex, proving live theme resolution actually wires through to this
    // page's pointColors rather than only being covered in isolation by the resolver's/hook's
    // own unit tests.
    document.documentElement.style.setProperty('--__s9cmpx-chart-sentiment-positive', '#111111');
    document.documentElement.style.setProperty('--__s9cmpx-chart-sentiment-negative', '#222222');
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue({ ...RESPONSE, yoy_years: [2020, 2021], yoy_values: [10.5, -3.2] });
    render(<CountryProfilePage />);
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
    render(<CountryProfilePage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<CountryProfilePage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).not.toHaveBeenCalled();
  });
});
