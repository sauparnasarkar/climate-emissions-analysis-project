import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse } from '../api/types';
import AboutPage from './AboutPage';

vi.mock('../api/client', () => ({ api: { listCountries: vi.fn() } }));

const COUNTRIES: CountriesResponse = {
  featured: ['China', 'United States', 'India'],
  expanded: ['China', 'United States', 'India', 'Vietnam'],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('AboutPage', () => {
  it('renders the static methodology and data-source content without crashing', () => {
    vi.mocked(api.listCountries).mockReturnValue(new Promise(() => {}));
    render(<AboutPage />);

    expect(screen.getByText('About This Project')).toBeInTheDocument();
    expect(screen.getByText('Methodology Summary')).toBeInTheDocument();
    expect(screen.getByText('Data Sources')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://github.com/owid/co2-data' })).toHaveAttribute(
      'href',
      'https://github.com/owid/co2-data',
    );
  });

  it('shows a loading placeholder in the methodology table before listCountries resolves', () => {
    vi.mocked(api.listCountries).mockReturnValue(new Promise(() => {}));
    render(<AboutPage />);

    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders the country count and featured list once listCountries resolves', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    render(<AboutPage />);

    expect(await screen.findByText(/4 countries analyzed/)).toBeInTheDocument();
    expect(screen.getByText(/Featured for comparison: China, United States, India\./)).toBeInTheDocument();
  });

  it('renders the error message inline in the methodology table when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<AboutPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });
});
