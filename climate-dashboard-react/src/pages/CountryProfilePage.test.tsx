import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { CountryProfileResponse } from '../api/types';
import CountryProfilePage from './CountryProfilePage';

vi.mock('../api/client', () => ({ api: { countryProfile: vi.fn() } }));

// See OverviewPage.test.tsx — SyChart's Plotly rendering is design-system's own
// concern, stubbed here so this page's data-wiring is what's under test.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, SyChart: (props: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={props.ariaLabel} /> };
});

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
  it('renders the profile for the default (first) country', async () => {
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    render(<CountryProfilePage />);

    expect(await screen.findByText('CO₂ Emissions — China')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenCalledWith('China');
  });

  it('re-fetches with the newly selected country', async () => {
    vi.mocked(api.countryProfile).mockResolvedValue(RESPONSE);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<CountryProfilePage />);
    await screen.findByText('CO₂ Emissions — China');

    vi.mocked(api.countryProfile).mockResolvedValue({ ...RESPONSE, country: 'India' });
    await user.click(screen.getByLabelText('Select a country'));
    await user.click(await screen.findByRole('option', { name: 'India' }));

    expect(await screen.findByText('CO₂ Emissions — India')).toBeInTheDocument();
    expect(vi.mocked(api.countryProfile)).toHaveBeenLastCalledWith('India');
  });

  it('renders an inline error instead of crashing when the API call fails', async () => {
    vi.mocked(api.countryProfile).mockRejectedValue(new Error('Failed to load data.'));
    render(<CountryProfilePage />);

    expect(await screen.findByText('Failed to load data.')).toBeInTheDocument();
  });
});
