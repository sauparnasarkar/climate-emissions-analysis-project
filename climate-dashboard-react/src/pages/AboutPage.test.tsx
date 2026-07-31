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

    expect(await screen.findByText(/Expanded: 4 countries/)).toBeInTheDocument();
    expect(screen.getByText(/Selected \(Overview page comparison\) defaults to these Featured countries: China, United States, India\./)).toBeInTheDocument();
  });

  it('renders the error message inline in the methodology table when listCountries fails', async () => {
    vi.mocked(api.listCountries).mockRejectedValue(new Error('Failed to load data.'));
    render(<AboutPage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });

  it('embeds the presentation via Microsoft\'s viewer, pointed at the deployed pptx, with a direct-link fallback', () => {
    vi.mocked(api.listCountries).mockReturnValue(new Promise(() => {}));
    render(<AboutPage />);

    const expectedPptxUrl = `${window.location.origin}/GHG_Internship_Review_QA_Deck.pptx`;
    const iframe = screen.getByTitle('GHG Internship Review Q&A Deck');
    expect(iframe).toHaveAttribute('src', `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(expectedPptxUrl)}`);
    expect(screen.getByRole('link', { name: 'Open or download the presentation' })).toHaveAttribute('href', expectedPptxUrl);
  });
});
