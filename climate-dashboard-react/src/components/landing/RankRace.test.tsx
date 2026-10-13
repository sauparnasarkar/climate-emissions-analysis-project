import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorldMapTimeSeries } from '../../api/types';
import { RankRace } from './RankRace';

const MAP: WorldMapTimeSeries = {
  iso_codes: ['AAA', 'BBB', 'CCC'],
  countries: ['Alpha', 'Beta', 'Gamma'],
  years: [2000, 2001, 2002],
  // Beta overtakes Alpha in 2002.
  values: [[100, 50, 10], [100, 90, 10], [100, 300, 10]],
  value_range: [1, 300],
};
const WORLD = [160, 200, 410];

let reduced = false;
let mqlListeners: Array<(e: { matches: boolean }) => void> = [];
let ioCallback: ((entries: Array<{ isIntersecting: boolean }>) => void) | null = null;

beforeEach(() => {
  vi.useFakeTimers();
  reduced = false;
  ioCallback = null;
  mqlListeners = [];
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: reduced && q === '(prefers-reduced-motion: reduce)', media: q,
    addEventListener: (_: string, cb: (e: { matches: boolean }) => void) => { mqlListeners.push(cb); },
    removeEventListener: (_: string, cb: (e: { matches: boolean }) => void) => { mqlListeners = mqlListeners.filter((l) => l !== cb); },
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null,
  }));
  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: (entries: Array<{ isIntersecting: boolean }>) => void) { ioCallback = cb; }
    observe() {}
    disconnect() {}
  });
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const mount = () => render(<MemoryRouter><RankRace series={MAP} worldTotals={WORLD} expandedCount={40} /></MemoryRouter>);
const rankingWithShares = () => within(screen.getByRole('list', { name: /largest emitters in/i })).getAllByRole('listitem').map((li) => li.textContent);
// order and value only: the existing race tests are about the ranking, not the shares (those have their own tests below)
const ranking = () => rankingWithShares().map((t) => t!.replace(/ \(.*\)$/, ''));

describe('RankRace', () => {
  it('starts on the final year, in real rank order, with the share of the world total', () => {
    mount();
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']);
    expect(screen.getByRole('heading', { name: '10 countries, 100% of the world’s CO₂' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Replay 2000 → 2002' })).toBeInTheDocument();
  });

  it('autoplays once when scrolled into view: restarts at the first year, re-ranks, stops at the end', () => {
    mount();
    act(() => ioCallback!([{ isIntersecting: true }]));
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 50', 'Gamma: 10']); // 2000
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(550); });
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 90', 'Gamma: 10']); // 2001
    act(() => { vi.advanceTimersByTime(550); });
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']); // 2002: Beta overtakes
    act(() => { vi.advanceTimersByTime(550); });
    expect(screen.getByRole('button', { name: 'Replay 2000 → 2002' })).toBeInTheDocument();
    // A second intersection never restarts it on its own.
    act(() => ioCallback!([{ isIntersecting: true }]));
    expect(screen.getByRole('button', { name: /Replay/ })).toBeInTheDocument();
  });

  it('Pause stops the clock and Replay restarts from the first year', () => {
    mount();
    act(() => ioCallback!([{ isIntersecting: true }]));
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    act(() => { vi.advanceTimersByTime(2000); });
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 50', 'Gamma: 10']); // frozen at 2000
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    act(() => { vi.advanceTimersByTime(550); });
    expect(ranking()[1]).toBe('Beta: 90');
  });

  it('under reduced motion: no autoplay, but Play works (user-initiated) and a year slider is offered too', () => {
    reduced = true;
    mount();
    expect(ioCallback).toBeNull(); // never even observes, so nothing autoplays
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']); // static until asked

    // The button is present and enabled; pressing it plays from the first year, one step per tick.
    const play = screen.getByRole('button', { name: 'Replay 2000 → 2002' });
    expect(play).toBeEnabled();
    fireEvent.click(play);
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 50', 'Gamma: 10']); // 2000
    act(() => { vi.advanceTimersByTime(550); });
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 90', 'Gamma: 10']); // 2001

    // The slider still scrubs, and scrubbing pauses playback.
    fireEvent.keyDown(screen.getByRole('slider'), { key: 'Home' });
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(2000); });
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 50', 'Gamma: 10']); // stayed at 2000
  });

  it('stops autoplay and snaps to the final year if reduced motion turns on mid-race', () => {
    mount();
    act(() => ioCallback!([{ isIntersecting: true }]));
    act(() => { vi.advanceTimersByTime(550); });
    expect(ranking()[1]).toBe('Beta: 90'); // 2001, still racing
    reduced = true;
    act(() => { mqlListeners.forEach((l) => l({ matches: true })); });
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']); // snapped to 2002
    act(() => { vi.advanceTimersByTime(5000); });
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']); // and stays put
    expect(screen.getByRole('button', { name: 'Replay 2000 → 2002' })).toBeEnabled(); // Play remains available
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('gives the reduced-motion slider real years (aria min/max/now), not row indices', () => {
    reduced = true;
    mount();
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('aria-valuemin', '2000');
    expect(slider).toHaveAttribute('aria-valuemax', '2002');
    expect(slider).toHaveAttribute('aria-valuenow', '2002');
    fireEvent.keyDown(slider, { key: 'ArrowLeft' });
    expect(slider).toHaveAttribute('aria-valuenow', '2001');
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 90', 'Gamma: 10']); // 2001's ranking
  });

  describe('the share of the world total on each bar', () => {
    it("gives each country's share of that year's World total, one decimal, in the list and beside the bar", () => {
      mount();
      // 2002: World 410 (the three countries are 410 here), so Beta 300 -> 73.2%, Alpha 100 -> 24.4%, Gamma 10 -> 2.4%
      expect(rankingWithShares()).toEqual(['Beta: 300 (73.2%)', 'Alpha: 100 (24.4%)', 'Gamma: 10 (2.4%)']);
      const chart = screen.getByRole('group', { name: /ranking race, 2002/i });
      expect(within(chart).getByText('73.2%')).toBeInTheDocument();
      expect(within(chart).getByText('24.4%')).toBeInTheDocument();
      expect(within(chart).getByText(/share of the world total \(international aviation and shipping included\)/)).toBeInTheDocument();
    });

    it('is of the World total, which can exceed the countries shown: the bars then sum to less than the heading', () => {
      render(<MemoryRouter><RankRace series={MAP} worldTotals={[160, 200, 512.5]} expandedCount={40} /></MemoryRouter>);
      // the same three countries against a World of 512.5 (410 plus international transport and the rest): 300/512.5 = 58.5%
      expect(rankingWithShares()[0]).toBe('Beta: 300 (58.5%)');
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('10 countries, 80% of the world’s CO₂');
    });

    it('shows no share, on the bars or in the heading, when the World total is unavailable', () => {
      render(<MemoryRouter><RankRace series={MAP} worldTotals={[]} expandedCount={40} /></MemoryRouter>);
      expect(rankingWithShares()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']);
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/^10 countries$/);
      expect(screen.queryByText(/share of the world total/)).not.toBeInTheDocument();
      render(<MemoryRouter><RankRace series={MAP} worldTotals={[NaN, NaN, NaN]} expandedCount={40} /></MemoryRouter>);
      expect(screen.queryAllByText(/%/)).toHaveLength(0);
    });
  });
});
