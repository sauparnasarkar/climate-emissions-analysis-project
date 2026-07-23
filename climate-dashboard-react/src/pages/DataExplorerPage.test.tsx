import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { ExplorerDataResponse, ExplorerMetaResponse, ModelComparisonResponse } from '../api/types';
import DataExplorerPage from './DataExplorerPage';

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

afterEach(() => {
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
    expect(screen.getByText('Summary Statistics')).toBeInTheDocument();

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
    expect(await screen.findByText('Summary Statistics')).toBeInTheDocument();
  });
});
