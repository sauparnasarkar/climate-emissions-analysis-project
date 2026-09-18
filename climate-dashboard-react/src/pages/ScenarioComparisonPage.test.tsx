import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, ScenarioCompareResponse, ScenarioCumulativeResponse } from '../api/types';
import ScenarioComparisonPage from './ScenarioComparisonPage';

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
  api: { listCountries: vi.fn(), scenarioCumulative: vi.fn(), scenarioCompare: vi.fn() },
}));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own concern.
// The treemap's onTileClick (SPEC.md §5.10) is real page-level logic, not SyChart's own
// concern, so the stub exposes a button that simulates a tap on the first tile -- this
// exercises ScenarioComparisonPage's own state wiring without needing a real Plotly click.
// Also surfaces the treemap series' own labels/values/colorValues verbatim (as JSON in a
// hidden node) and one tap button per label, so a test can assert the emitted "Other"
// grouping directly rather than only inferring it from the detail panel's rendered text
// (Copilot review, PR #182 — the 1% partition/aggregation had no coverage at all before this).
// Also surfaces colorScale/colorRange so a test can assert the diverging scale's stop order
// is reversed (increase reads as the negative/bad end), the same fix as Overview's % Change
// bar chart -- see OverviewPage.test.tsx's equivalent test for the shared rationale.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: {
      ariaLabel?: string;
      height?: number;
      series: Array<{
        kind?: string;
        labels?: string[];
        values?: number[];
        colorValues?: Array<number | null>;
        colorScale?: Array<[number, string]>;
        colorRange?: [number, number];
        onTileClick?: (i: number, label: string) => void;
      }>;
    }) => {
      const treemapSeries = props.series.find((s) => s.kind === 'treemap');
      return (
        <div
          data-testid="sychart"
          aria-label={props.ariaLabel}
          data-height={props.height}
          data-color-scale={treemapSeries?.colorScale ? JSON.stringify(treemapSeries.colorScale) : undefined}
          data-color-range={treemapSeries?.colorRange ? JSON.stringify(treemapSeries.colorRange) : undefined}
        >
          {treemapSeries?.onTileClick && (
            <>
              <button onClick={() => treemapSeries.onTileClick!(0, 'China')}>Simulate tile tap</button>
              {treemapSeries.labels?.map((label, i) => (
                <button key={label} onClick={() => treemapSeries.onTileClick!(i, label)}>
                  {`Simulate tap: ${label}`}
                </button>
              ))}
              <div data-testid="treemap-series-data" style={{ display: 'none' }}>
                {JSON.stringify({ labels: treemapSeries.labels, values: treemapSeries.values, colorValues: treemapSeries.colorValues })}
              </div>
            </>
          )}
        </div>
      );
    },
  };
});

const COUNTRIES: CountriesResponse = { featured: ['China'], expanded: ['China', 'Vietnam'] };

const CUMULATIVE: ScenarioCumulativeResponse = {
  sort_by: 'BAU',
  order: ['China', 'United States'],
  scenarios: ['BAU', 'Moderate', 'Aggressive'],
  rows: [
    {
      country: 'China',
      values: { BAU: 1000, Moderate: 800, Aggressive: 600 },
      year_2040: { BAU: 16000, Moderate: 9000, Aggressive: 7000 },
      current_level: 11000,
    },
    {
      country: 'United States',
      values: { BAU: 500, Moderate: 400, Aggressive: 300 },
      year_2040: { BAU: 3800, Moderate: 3500, Aggressive: 3000 },
      current_level: 4700,
    },
  ],
};

// Exercises the "Other" grouping (Claude Design theme-adherence review, C7): China and India
// each clear the 1% threshold and stay individual tiles; Vietnam and Fiji (0.3%/0.7% of the
// 10,000 total) fall under it and are grouped. Deliberately UNEQUAL weights (30 vs. 70), not
// the 50/50 this fixture used before Copilot review, PR #182 caught that a 50/50 split can't
// distinguish weighted from unweighted averaging -- both produce 5 when the weights are equal.
// Here the weighted average is (20*30 + -10*70) / (30+70) = -1, while the plain (unweighted)
// mean of the same two deltas is (20 + -10) / 2 = 5 -- a regression to an unweighted mean
// would assert -1 and get 5, and fail.
const CUMULATIVE_WITH_LONG_TAIL: ScenarioCumulativeResponse = {
  sort_by: 'BAU',
  order: ['China', 'India', 'Vietnam', 'Fiji'],
  scenarios: ['BAU', 'Moderate', 'Aggressive'],
  rows: [
    { country: 'China', values: { BAU: 8000 }, year_2040: { BAU: 16000 }, current_level: 11000 },
    { country: 'India', values: { BAU: 1900 }, year_2040: { BAU: 2500 }, current_level: 2000 },
    { country: 'Vietnam', values: { BAU: 30 }, year_2040: { BAU: 120 }, current_level: 100 },
    { country: 'Fiji', values: { BAU: 70 }, year_2040: { BAU: 90 }, current_level: 100 },
  ],
};

const COMPARE: ScenarioCompareResponse = {
  countries: ['China'],
  scenarios: {
    BAU: [{ name: 'China', years: [2020, 2040], values: [10000, 16000] }],
    Moderate: [{ name: 'China', years: [2020, 2040], values: [10000, 9000] }],
    Aggressive: [{ name: 'China', years: [2020, 2040], values: [10000, 7000] }],
  },
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

describe('ScenarioComparisonPage', () => {
  it('renders the treemap and all three scenario panels for the default featured selection', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Cumulative Emissions & Reduction Scenarios — BAU — 2 Expanded Countries')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'BAU' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Moderate' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Aggressive' })).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).toHaveBeenCalledWith(['China']);
  });

  it('colors the treemap so a country whose emissions are still rising under BAU reads as the negative/bad end of the diverging scale, not the positive end', async () => {
    // Live-resolved (not the hardcoded fallback), same rationale as OverviewPage.test.tsx's
    // equivalent test. China's BAU 2040 level (16000) is above its current level (11000) --
    // a delta of +5000, still rising/bad -- so it must land on `low`/brown, not `high`/teal.
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-low', '#111111');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-mid', '#222222');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-high', '#333333');
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    const treemapChart = screen.getAllByTestId('sychart')[0];
    expect(treemapChart).toHaveAttribute(
      'data-color-scale',
      JSON.stringify([
        [0, '#333333'],
        [0.5, '#222222'],
        [1, '#111111'],
      ]),
    );
    // China: 16000 - 11000 = +5000 (largest magnitude); US: 3800 - 4700 = -900. colorRange
    // must be symmetric around the larger magnitude so "no change" still lands on the
    // scale's true midpoint.
    expect(treemapChart).toHaveAttribute('data-color-range', JSON.stringify([-5000, 5000]));
  });

  it('renders a Jump To nav under the h1 linking to all three sections, always present regardless of selection', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Reduction Map', 'Country Comparison', 'Cumulative Impact']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#reduction-map', '#country-comparison', '#cumulative-impact']);
    expect(document.getElementById('reduction-map')).not.toBeNull();
    expect(document.getElementById('country-comparison')).not.toBeNull();
    expect(document.getElementById('cumulative-impact')).not.toBeNull();
  });

  it('refetches the comparison panels when the country selection changes', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    const updated: ScenarioCompareResponse = { ...COMPARE, countries: ['China', 'Vietnam'] };
    vi.mocked(api.scenarioCompare).mockResolvedValue(updated);
    await user.click(screen.getByLabelText(/Select countries/));
    await user.click(screen.getByRole('option', { name: 'Vietnam' }));

    expect(await screen.findByRole('heading', { name: 'BAU' })).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).toHaveBeenLastCalledWith(['China', 'Vietnam']);
  });

  it('shows a warning instead of calling scenarioCompare when no countries are selected', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    vi.mocked(api.scenarioCompare).mockClear();
    const removeButtons = screen.getAllByRole('button', { name: /remove|×|clear/i });
    for (const button of removeButtons) {
      await user.click(button);
    }

    expect(await screen.findByText('Select at least one country.')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).not.toHaveBeenCalled();
  });

  it('expands and restores the treemap via ChartCard\'s expandable control (SPEC.md §5.11)', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative Emissions & Reduction Scenarios — BAU — 2 Expanded Countries');

    // The treemap is always the first SyChart rendered on this page (the 3 per-scenario
    // panel charts, also stubbed with the same testid, come later in render order). Every
    // ChartCard on this page is now expandable (SPEC.md §5.11), so scope to the first
    // "Expand chart" button rather than assuming it's the only one.
    const treemapChart = () => screen.getAllByTestId('sychart')[0];
    expect(treemapChart()).toHaveAttribute('data-height', '360');

    await user.click(screen.getAllByRole('button', { name: 'Expand chart' })[0]);
    expect(treemapChart()).toHaveAttribute('data-height', '640');
    expect(screen.getByRole('button', { name: 'Restore chart' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Restore chart' }));
    expect(treemapChart()).toHaveAttribute('data-height', '360');
    expect(screen.getAllByRole('button', { name: 'Expand chart' })[0]).toBeInTheDocument();
  });

  it('expands and restores a Country Comparison panel independently of the others (SPEC.md §5.11)', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByRole('heading', { name: 'BAU' });

    // Panel order: treemap (index 0), then BAU/Moderate/Aggressive panels (indices 1-3).
    const bauPanelChart = () => screen.getAllByTestId('sychart')[1];
    expect(bauPanelChart()).toHaveAttribute('data-height', '300');

    // The treemap renders first, then the BAU/Moderate/Aggressive panels in that order
    // (same ordering the sychart-index comment above relies on) -- index into the ordered
    // list of "Expand chart" buttons rather than traversing design-system's internal markup.
    await user.click(screen.getAllByRole('button', { name: 'Expand chart' })[1]);
    expect(bauPanelChart()).toHaveAttribute('data-height', '600');

    // The treemap and other panels are unaffected by this one panel's toggle.
    expect(screen.getAllByTestId('sychart')[0]).toHaveAttribute('data-height', '360');
    expect(screen.getAllByTestId('sychart')[2]).toHaveAttribute('data-height', '300');
  });

  it('recolors the treemap (via its title) when a different scenario radio is selected, without refetching', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative Emissions & Reduction Scenarios — BAU — 2 Expanded Countries');

    await user.click(screen.getByRole('radio', { name: 'Aggressive' }));

    expect(await screen.findByText('Cumulative Emissions & Reduction Scenarios — Aggressive — 2 Expanded Countries')).toBeInTheDocument();
    // Purely a client-side recolor of the already-fetched data -- no additional fetch.
    expect(vi.mocked(api.scenarioCumulative)).toHaveBeenCalledTimes(1);
  });

  it('shows a dismissible detail area for the tapped tile instead of drilling in (SPEC.md §5.10)', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative Emissions & Reduction Scenarios — BAU — 2 Expanded Countries');

    expect(screen.queryByText(/Cumulative BAU: 1[,   ]000 MtCO/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Simulate tile tap' }));

    expect(await screen.findByText(/Cumulative BAU: 1[,   ]000 MtCO/)).toBeInTheDocument();
    expect(screen.getByText(/BAU 2040 vs\. Current: \+5[,   ]000 MtCO/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Dismiss country detail' }));
    expect(screen.queryByText(/Cumulative BAU: 1[,   ]000 MtCO/)).not.toBeInTheDocument();
  });

  it('groups countries below 1% of total BAU into a single "Other" tile with a value-weighted average color (SPEC.md §5.10, Claude Design C7)', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE_WITH_LONG_TAIL);
    vi.mocked(api.scenarioCompare).mockResolvedValue(COMPARE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<ScenarioComparisonPage />);
    await screen.findByText('Cumulative Emissions & Reduction Scenarios — BAU — 4 Expanded Countries');

    // China and India clear the 1% threshold and stay individual; Vietnam and Fiji (0.3%/0.7%)
    // are grouped into one trailing "Other" tile -- exactly 3 tiles, not 4. colorValues[2] is
    // -1 (the weighted average), not 5 (the unweighted mean of the same two deltas) -- see the
    // fixture's own comment for why the two are deliberately different here.
    const seriesData = JSON.parse(screen.getByTestId('treemap-series-data').textContent!);
    expect(seriesData).toEqual({
      labels: ['China', 'India', 'Other'],
      values: [8000, 1900, 100],
      colorValues: [5000, 500, -1],
    });

    // Tapping the "Other" tile (the mocked SyChart exposes one tap button per emitted label)
    // shows the aggregate, not a single country, and the weighted-average wording --
    // distinguishing this from the single-country detail panel checked below. Scoped to the
    // detail panel itself (via its dismiss button's container), not the whole document --
    // "India" and "China" also appear as ordinary rows in the Cumulative Impact table below.
    await user.click(screen.getByRole('button', { name: 'Simulate tap: Other' }));
    const detailPanel = () => screen.getByRole('button', { name: 'Dismiss country detail' }).closest('div')!;
    expect(await within(detailPanel()).findByText('Other (2 countries)')).toBeInTheDocument();
    expect(within(detailPanel()).getByText(/Cumulative BAU: 100 MtCO/)).toBeInTheDocument();
    expect(within(detailPanel()).getByText(/BAU 2040 vs\. Current \(weighted avg\.\): -1 MtCO/)).toBeInTheDocument();

    // Tapping an individual (non-grouped) tile still shows the plain, ungrouped wording.
    await user.click(screen.getByRole('button', { name: 'Simulate tap: India' }));
    expect(await within(detailPanel()).findByText('India')).toBeInTheDocument();
    expect(within(detailPanel()).queryByText(/countries\)/)).not.toBeInTheDocument();
    expect(within(detailPanel()).getByText(/BAU 2040 vs\. Current: \+500 MtCO/)).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when the compare call fails', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.scenarioCumulative).mockResolvedValue(CUMULATIVE);
    vi.mocked(api.scenarioCompare).mockRejectedValue(new Error('Failed to load data.'));
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error instead of crashing when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<ScenarioComparisonPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(vi.mocked(api.scenarioCompare)).not.toHaveBeenCalled();
  });
});
