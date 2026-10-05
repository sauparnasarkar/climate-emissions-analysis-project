import { act, cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { ApiError } from '../api/types';
import type { WorldMapTimeSeries } from '../api/types';
import { ALL_GAS_PAIR, COMPOSITION, CONCENTRATION, COUNTRY_SNAPSHOT, PAIR, TEMPERATURE, TEMPERATURE_MEAN5Y } from '../test/climateFixtures';
import { shareResponse } from '../test/shareFixtures';
import ClimateCorrelationPage from './ClimateCorrelationPage';

const scrollSpy = vi.hoisted(() => vi.fn());
vi.mock('../api/client', () => ({
  api: { correlationEmissionsTemperature: vi.fn(), correlationTemperature: vi.fn(), correlationConcentration: vi.fn(), worldMapSeries: vi.fn(), correlationGhgComposition: vi.fn(), correlationCountryShare: vi.fn() },
}));
vi.mock('design-system', async (orig) => ({
  ...(await orig<typeof import('design-system')>()),
  scrollToJumpTarget: (id: string) => scrollSpy(id),
  SyChart: (p: { ariaLabel?: string }) => <div data-testid="sychart" aria-label={p.ariaLabel} />,
}));

const WORLD: WorldMapTimeSeries = { iso_codes: ['CHN', 'USA'], countries: ['China', 'United States'], years: [2023, 2024], values: [[30000, 5000], [32000, 5398]], value_range: [5000, 32000] };

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: false, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.mocked(api.correlationEmissionsTemperature).mockImplementation(async (o) => (o?.source === 'primap_ghg' ? ALL_GAS_PAIR : o?.variant === 'fossil' ? ({ ...PAIR, fit: { ...PAIR.fit, slope: 0.797 } } as never) : PAIR));
  vi.mocked(api.correlationTemperature).mockImplementation(async (o) => (o?.view === 'mean5y' ? TEMPERATURE_MEAN5Y : TEMPERATURE));
  vi.mocked(api.correlationConcentration).mockResolvedValue(CONCENTRATION);
  vi.mocked(api.worldMapSeries).mockResolvedValue(WORLD);
  vi.mocked(api.correlationGhgComposition).mockResolvedValue(COMPOSITION);
  vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : shareResponse([['USA', 'United States', [[1850, 4, 1], [2024, 24.1, 1]]]])));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

const mount = (hash = '') => render(<MemoryRouter initialEntries={[`/climate-correlation${hash}`]}><ClimateCorrelationPage /></MemoryRouter>);

describe('ClimateCorrelationPage — causal chain and headline relationship', () => {
  it('shows the intro, a sticky anchor row, the four-step chain and the headline relationship from the API', async () => {
    mount();
    expect(await screen.findByRole('heading', { level: 1, name: 'Temperature & GHG Correlation' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { level: 2, name: 'Causal chain' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Global relationship' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Jump links' });
    expect(within(nav).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual(['#causal-chain', '#global-relationship', '#country-view']);
    expect((nav.closest('[style*="position: sticky"]') as HTMLElement)).not.toBeNull();
    expect(within(document.querySelector('.module-chain') as HTMLElement).getAllByRole('listitem')[0]).toHaveTextContent('37,398 MtCO₂ in 2024'); // world total from the series, not typed in
    expect(screen.getByText('Fossil + cement only')).toBeInTheDocument();
    expect(api.correlationEmissionsTemperature).toHaveBeenCalledWith({ variant: 'fossil' });
    expect(document.getElementById('causal-chain')!.compareDocumentPosition(document.getElementById('global-relationship')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('still shows the relationship, without the fossil comparison, when only that request fails; and the chain without its emissions figure', async () => {
    vi.mocked(api.correlationEmissionsTemperature).mockImplementation(async (o) => {
      if (o?.variant === 'fossil') throw new ApiError(503, 'x');
      return PAIR;
    });
    vi.mocked(api.worldMapSeries).mockRejectedValue(new ApiError(503, 'x'));
    mount();
    expect(await screen.findByRole('heading', { level: 2, name: 'Global relationship' })).toBeInTheDocument();
    expect(screen.queryByText('Fossil + cement only')).not.toBeInTheDocument();
    expect(within(document.querySelector('.module-chain') as HTMLElement).getAllByRole('listitem')[0].textContent).not.toMatch(/MtCO₂/);
  });

  it('shows the recent all-gas view after the headline, fetched as the PRIMAP source, and the headline caption points to it', async () => {
    mount();
    const gas = await screen.findByRole('heading', { level: 3, name: /^Recent all-gas relationship/ });
    expect(api.correlationEmissionsTemperature).toHaveBeenCalledWith({ source: 'primap_ghg' });
    expect(document.getElementById('global-relationship')!.compareDocumentPosition(gas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/separate chart below and is not called TCRE/)).toBeInTheDocument();
  });

  it('leaves the all-gas view out, and the caption sentence about it, when its request fails; the headline is unaffected', async () => {
    vi.mocked(api.correlationEmissionsTemperature).mockImplementation(async (o) => {
      if (o?.source === 'primap_ghg') throw new ApiError(503, 'x');
      return o?.variant === 'fossil' ? ({ ...PAIR, fit: { ...PAIR.fit, slope: 0.797 } } as never) : PAIR;
    });
    mount();
    expect(await screen.findByRole('heading', { level: 2, name: 'Global relationship' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 3, name: /Recent all-gas/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/separate chart below/)).not.toBeInTheDocument();
  });

  it('shows gas composition after the all-gas view and the country view after it, fetching composition from 1970', async () => {
    mount();
    const gas = await screen.findByRole('heading', { level: 3, name: /^Gas composition, 1970 onward/ });
    const country = screen.getByRole('heading', { level: 2, name: 'Country view' });
    expect(api.correlationGhgComposition).toHaveBeenCalledWith({ startYear: 1970 });
    expect(document.getElementById('recent-all-gas')!.compareDocumentPosition(gas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(gas.compareDocumentPosition(country) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(api.correlationTemperature).toHaveBeenCalledWith({ view: 'mean5y', baseline: '1850_1900' });
  });

  it('leaves out gas composition alone when its request fails, and the country view still shows without the 5-year mean when that fails', async () => {
    vi.mocked(api.correlationGhgComposition).mockRejectedValue(new ApiError(503, 'x'));
    vi.mocked(api.correlationTemperature).mockImplementation(async (o) => { if (o?.view === 'mean5y') throw new ApiError(503, 'x'); return TEMPERATURE; });
    mount();
    expect(await screen.findByRole('heading', { level: 2, name: 'Country view' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Gas composition/ })).not.toBeInTheDocument();
    const temp = await screen.findByLabelText(/Line chart of the global temperature anomaly/);
    expect(temp.getAttribute('aria-label')).not.toMatch(/5-year mean/); // drawn with the annual line only
  });

  it('does not lose the chain and relationship when only the optional 5-year-mean request fails', async () => {
    vi.mocked(api.correlationTemperature).mockImplementation(async (o) => {
      if (o?.view === 'mean5y') throw new ApiError(503, 'x');
      return TEMPERATURE;
    });
    mount();
    expect(await screen.findByRole('heading', { level: 2, name: 'Global relationship' })).toBeInTheDocument();
    expect(screen.queryByText(/climate data is unavailable/)).not.toBeInTheDocument();
  });

  it('uses the latest year that has data when the final map row is all null, never a zero total', async () => {
    vi.mocked(api.worldMapSeries).mockResolvedValue({ ...WORLD, years: [2023, 2024, 2025], values: [...WORLD.values, [null, null]] });
    mount();
    await screen.findByRole('heading', { level: 2, name: 'Causal chain' });
    const first = within(document.querySelector('.module-chain') as HTMLElement).getAllByRole('listitem')[0];
    expect(first).toHaveTextContent('37,398 MtCO₂ in 2024');
    expect(first.textContent).not.toMatch(/\b0 MtCO₂/);
  });

  it('says the climate data is unavailable once, and shows neither section nor anchor row, when the headline request fails', async () => {
    vi.mocked(api.correlationEmissionsTemperature).mockRejectedValue(new ApiError(503, 'x'));
    mount();
    expect(await screen.findByText(/climate data is unavailable right now/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 2, name: 'Causal chain' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Jump links' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('a #global-relationship deep link jumps once the section exists, after the anchor row has been measured', async () => {
    window.history.replaceState(null, '', '/climate-correlation#global-relationship');
    mount('#global-relationship');
    await vi.waitFor(() => expect(scrollSpy).toHaveBeenCalledWith('global-relationship'));
    expect(document.getElementById('global-relationship')).not.toBeNull();
    expect(scrollSpy).toHaveBeenCalledTimes(1);
  });

  it('offsets jump targets by the measured height of the sticky row', async () => {
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { height: this.style.position === 'sticky' ? 90 : 0 } as DOMRect;
    });
    mount();
    await screen.findByRole('navigation', { name: 'Jump links' });
    await vi.waitFor(() => expect(document.querySelector('.climate-module style')?.textContent).toMatch(/scroll-margin-top: 168px/));
    rect.mockRestore();
    await act(async () => {});
  });
});
