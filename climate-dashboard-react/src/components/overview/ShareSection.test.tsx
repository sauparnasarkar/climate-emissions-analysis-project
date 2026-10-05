import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import { ApiError } from '../../api/types';
import { shareResponse } from '../../test/shareFixtures';
import { ShareSection } from './ShareSection';

vi.mock('../../api/client', () => ({ api: { correlationCountryShare: vi.fn() } }));

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? matches : false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
}

const RESP = shareResponse([
  ['CHN', 'China', [[2022, 14, 30], [2023, 15, 31], [2024, 16, 32]]],
  ['USA', 'United States', [[2022, 24.5, 13.5], [2023, 24.2, 13.2], [2024, 24, 13]]],
]);

beforeEach(() => {
  mockReducedMotion(false);
  vi.mocked(api.correlationCountryShare).mockResolvedValue(RESP);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.useRealTimers(); });

const mount = (countries = ['CHN', 'USA']) => render(<ShareSection countries={countries} />);
const tableCell = (row: string, col: number) => within(screen.getByRole('row', { name: new RegExp(`^${row}`) })).getAllByRole('cell')[col].textContent;

describe('ShareSection', () => {
  it('asks for the selected countries from 1970 and shows stock and flow at the latest year, with Rest of world as the remainder', async () => {
    mount();
    expect(await screen.findByRole('heading', { level: 2, name: 'Who emitted the stock, and who emits now' })).toBeInTheDocument();
    expect(api.correlationCountryShare).toHaveBeenCalledWith({ source: 'owid_co2', gasScope: 'co2', countries: ['CHN', 'USA'], startYear: 1970 });
    expect(await screen.findByText('Share by country, 2024')).toBeInTheDocument();
    expect(tableCell('United States', 0)).toBe('24.0%');
    expect(tableCell('United States', 1)).toBe('13.0%');
    expect(tableCell('China', 0)).toBe('16.0%');
    expect(tableCell('Rest of world', 0)).toBe('60.0%');
    expect(tableCell('Rest of world', 1)).toBe('55.0%');
    expect(screen.getByRole('img', { name: /^The stock: United States 24.0%, China 16.0%, Rest of world 60.0%$/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /^The flow: United States 13.0%, China 32.0%, Rest of world 55.0%$/ })).toBeInTheDocument();
    expect(screen.getByText('Cumulative 1750–2024')).toBeInTheDocument();
    expect(screen.getByText(/no warming is attributed to a country/)).toBeInTheDocument();
  });

  it('plays one year per 250 ms from the first year, ends on the latest and stops, keeping segment order fixed', async () => {
    vi.useFakeTimers();
    mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(screen.getByText('Share by country, 2024')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    expect(screen.getByText('Share by country, 2022')).toBeInTheDocument(); // replays from the first year
    expect(tableCell('China', 0)).toBe('14.0%');
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(screen.getByText('Share by country, 2023')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(screen.getByText('Share by country, 2024')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    const rows = screen.getAllByRole('row').map((r) => r.textContent ?? '');
    expect(rows.findIndex((t) => t.startsWith('United States'))).toBeLessThan(rows.findIndex((t) => t.startsWith('China')));
  });

  it('scrubbing the slider jumps to that year and pauses', async () => {
    mount();
    await screen.findByText('Share by country, 2024');
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('aria-valuemin', '2022');
    expect(slider).toHaveAttribute('aria-valuemax', '2024');
    fireEvent.keyDown(slider, { key: 'ArrowLeft' });
    expect(screen.getByText('Share by country, 2023')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
  });

  it('refetches with the chosen measure\'s source and gas scope', async () => {
    mount();
    await screen.findByText('Share by country, 2024');
    fireEvent.click(screen.getByRole('radio', { name: 'All GHGs · PRIMAP-hist' }));
    await screen.findByText('Share by country, 2024');
    expect(api.correlationCountryShare).toHaveBeenLastCalledWith({ source: 'primap_hist', gasScope: 'total_ghg', countries: ['CHN', 'USA'], startYear: 1970 });
    fireEvent.click(screen.getByRole('radio', { name: 'CO₂ · PRIMAP-hist' }));
    await screen.findByText('Share by country, 2024');
    expect(api.correlationCountryShare).toHaveBeenLastCalledWith({ source: 'primap_hist', gasScope: 'co2', countries: ['CHN', 'USA'], startYear: 1970 });
  });

  it('asks for a selection instead of requesting anything when no country is selected', () => {
    mount([]);
    expect(screen.getByText('Select countries in the picker below to compare their shares.')).toBeInTheDocument();
    expect(api.correlationCountryShare).not.toHaveBeenCalled();
    expect(document.getElementById('share')).not.toBeNull(); // still a real jump target
  });

  it('omits the flow bar and column, with a note, when the annual shares are not published yet', async () => {
    vi.mocked(api.correlationCountryShare).mockResolvedValue(shareResponse([['USA', 'United States', [[2023, 24.2, null], [2024, 24, null]]]]));
    mount(['USA']);
    expect(await screen.findByText(/annual \(flow\) shares are not published yet/)).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /^The flow/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Flow' })).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: /^The stock/ })).toBeInTheDocument();
  });

  it('draws the table only, with a warning, when a published share is negative', async () => {
    vi.mocked(api.correlationCountryShare).mockResolvedValue(shareResponse([
      ['USA', 'United States', [[2023, 24, 13], [2024, 23, -1]]], ['CHN', 'China', [[2023, 15, 30], [2024, 16, 10]]],
    ]));
    mount();
    expect(await screen.findByText(/negative \(a recorded data deviation\)/)).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /^The (stock|flow)/ })).not.toBeInTheDocument();
    expect(await screen.findByText('Share by country, 2024')).toBeInTheDocument();
    expect(tableCell('United States', 1)).toBe('-1.0%');
  });

  it('names a country with no data in the measure and leaves it out rather than showing 0.0%', async () => {
    vi.mocked(api.correlationCountryShare).mockResolvedValue({
      ...shareResponse([['USA', 'United States', [[2023, 24, 13], [2024, 23, 12]]], ['TWN', 'Taiwan', []]]),
      notes: ['no PRIMAP-hist rows for TWN'],
    });
    mount(['USA', 'TWN']);
    expect(await screen.findByText(/No data in this measure for Taiwan; it is left out\. no PRIMAP-hist rows for TWN/)).toBeInTheDocument();
    expect(screen.queryByRole('row', { name: /^Taiwan/ })).not.toBeInTheDocument();
  });

  it('describes the measure neutrally, not as CO₂', async () => {
    mount();
    expect(await screen.findByText(/everything emitted so far, by the measure chosen below/)).toBeInTheDocument();
    expect(screen.queryByText(/all CO₂ emitted/)).not.toBeInTheDocument();
  });

  it('shows the API\'s own message when the request fails', async () => {
    vi.mocked(api.correlationCountryShare).mockRejectedValue(new ApiError(404, 'unknown country code(s): XYZ'));
    mount(['XYZ']);
    expect(await screen.findByText(/unknown country code\(s\): XYZ/)).toBeInTheDocument();
  });

  it('tweens the segments, except under reduced motion', async () => {
    mount();
    const flex = () => (screen.getByRole('img', { name: /^The stock/ }).firstElementChild as HTMLElement).style.transition;
    await screen.findByText('Share by country, 2024');
    expect(flex()).toContain('250ms');
    cleanup();
    mockReducedMotion(true);
    mount();
    await screen.findByText('Share by country, 2024');
    expect(flex()).toBe('none');
  });
});
