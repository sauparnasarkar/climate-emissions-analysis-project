import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountriesResponse, CountryProfileResponse } from '../api/types';
import CountryProfilePage from './CountryProfilePage';

vi.mock('../api/client', () => ({ api: { countryProfile: vi.fn(), listCountries: vi.fn() } }));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own
// concern, stubbed here so this page's data-wiring is what's under test.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
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

afterEach(() => {
  vi.clearAllMocks();
});

describe('CountryProfilePage', () => {
  it('renders the profile for the default (featured[0]) country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<CountryProfilePage />);

    expect(await screen.findByText('CO₂ Emissions — China')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('China');
  });

  it('re-fetches with a newly selected, expanded-but-not-featured country', async () => {
    vi.mocked(api.listCountries).mockResolvedValue(COUNTRIES);
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<CountryProfilePage />);
    await screen.findByText('CO₂ Emissions — China');

    vi.mocked(api.countryProfile).mockResolvedValue({ ...RESPONSE, country: 'Vietnam' });
    await user.click(screen.getByLabelText('Select a country'));
    await user.click(await screen.findByRole('option', { name: 'Vietnam' }));

    expect(await screen.findByText('CO₂ Emissions — Vietnam')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenLastCalledWith('Vietnam');
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
