import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, ScenarioCompareResponse, ScenarioCumulativeResponse } from '../api/types';
import ScenarioComparisonPage from './ScenarioComparisonPage';

vi.mock('../api/client', () => ({
  api: { listCountries: vi.fn(), scenarioCumulative: vi.fn(), scenarioCompare: vi.fn() },
}));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own concern.
// The treemap's onTileClick (SPEC.md §5.10) is real page-level logic, not SyChart's own
// concern, so the stub exposes a button that simulates a tap on the first tile -- this
// exercises ScenarioComparisonPage's own state wiring without needing a real Plotly click.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: { ariaLabel?: string; height?: number; series: Array<{ kind?: string; onTileClick?: (i: number, label: string) => void }> }) => {
      const treemapSeries = props.series.find((s) => s.kind === 'treemap');
      return (
        <div data-testid="sychart" aria-label={props.ariaLabel} data-height={props.height}>
          {treemapSeries?.onTileClick && (
            <button onClick={() => treemapSeries.onTileClick!(0, 'China')}>Simulate tile tap</button>
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

const COMPARE: ScenarioCompareResponse = {
  countries: ['China'],
  scenarios: {
    BAU: [{ name: 'China', years: [2020, 2040], values: [10000, 16000] }],
    Moderate: [{ name: 'China', years: [2020, 2040], values: [10000, 9000] }],
    Aggressive: [{ name: 'China', years: [2020, 2040], values: [10000, 7000] }],
  },
};

afterEach(() => {
  vi.clearAllMocks();
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
