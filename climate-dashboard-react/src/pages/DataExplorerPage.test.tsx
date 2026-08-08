import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { ExplorerDataResponse, ExplorerMetaResponse, ModelComparisonResponse } from '../api/types';
import DataExplorerPage from './DataExplorerPage';

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

// RangeSlider/MultiSelect/DataTable render plain DOM (no canvas/Plotly lifecycle) —
// only SyChart needs stubbing elsewhere in this app, none of that applies here.
vi.mock('../api/client', () => ({
  api: {
    explorerMeta: vi.fn(),
    explorerData: vi.fn(),
    explorerSummary: vi.fn(),
    explorerDownloadUrl: vi.fn(),
  },
}));

const META: ExplorerMetaResponse = {
  countries: ['China', 'Kenya', 'United States'],
  columns: ['country', 'year', 'co2', 'population'],
  year_min: 1990,
  year_max: 2023,
};
const DATA: ExplorerDataResponse = {
  columns: ['country', 'year', 'co2'],
  rows: [{ country: 'China', year: 2023, co2: 11000 }],
  total_rows: 1,
  page: 1,
  page_size: 50,
};
const SUMMARY: ModelComparisonResponse = {
  columns: ['statistic', 'co2'],
  rows: [{ statistic: 'count', co2: 1 }],
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

describe('DataExplorerPage', () => {
  it('fetches meta then data/summary, and renders the row count and filter controls', async () => {
    vi.mocked(api.explorerMeta).mockResolvedValue(META);
    vi.mocked(api.explorerData).mockResolvedValue(DATA);
    vi.mocked(api.explorerSummary).mockResolvedValue(SUMMARY);
    vi.mocked(api.explorerDownloadUrl).mockReturnValue('/api/explorer/download?foo=bar');
    render(<DataExplorerPage />);

    expect(await screen.findByText('Data Explorer')).toBeInTheDocument();
    expect(await screen.findByText('1 rows · page 1 of 1')).toBeInTheDocument();
    expect(screen.getByText('Countries (leave empty to show all)')).toBeInTheDocument();
    expect(screen.getByText('Year range')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Summary Statistics' })).toBeInTheDocument();

    expect(vi.mocked(api.explorerData)).toHaveBeenCalledWith([], 1990, 2023, ['country', 'year', 'co2', 'population'], 1, 50);
    const link = screen.getByText('Download filtered data as CSV');
    expect(link).toHaveAttribute('href', '/api/explorer/download?foo=bar');
  });

  it('renders an inline error instead of crashing when meta fails to load', async () => {
    vi.mocked(api.explorerMeta).mockRejectedValue(new Error('Failed to load data.'));
    render(<DataExplorerPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('renders an inline error for the table when the data call fails, independent of summary', async () => {
    vi.mocked(api.explorerMeta).mockResolvedValue(META);
    vi.mocked(api.explorerData).mockRejectedValue(new Error('Failed to load data.'));
    vi.mocked(api.explorerSummary).mockResolvedValue(SUMMARY);
    render(<DataExplorerPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Summary Statistics' })).toBeInTheDocument();
  });

  it('renders a Jump To nav under the h1 linking to both sections', async () => {
    vi.mocked(api.explorerMeta).mockResolvedValue(META);
    vi.mocked(api.explorerData).mockResolvedValue(DATA);
    vi.mocked(api.explorerSummary).mockResolvedValue(SUMMARY);
    vi.mocked(api.explorerDownloadUrl).mockReturnValue('/api/explorer/download?foo=bar');
    render(<DataExplorerPage />);
    await screen.findByText('1 rows · page 1 of 1');

    const nav = await screen.findByRole('navigation', { name: 'Jump links' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Dataset Preview', 'Summary Statistics']);
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['#dataset-preview', '#summary-stats']);
    expect(document.getElementById('dataset-preview')).not.toBeNull();
    expect(document.getElementById('summary-stats')).not.toBeNull();
  });
});
