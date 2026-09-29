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
let ioCallback: ((entries: Array<{ isIntersecting: boolean }>) => void) | null = null;

beforeEach(() => {
  vi.useFakeTimers();
  reduced = false;
  ioCallback = null;
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: reduced && q === '(prefers-reduced-motion: reduce)', media: q, addEventListener: () => {}, removeEventListener: () => {},
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
const ranking = () => within(screen.getByRole('list', { name: /largest emitters in/i })).getAllByRole('listitem').map((li) => li.textContent);

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

  it('under reduced motion: no autoplay, no play button, a year slider instead', () => {
    reduced = true;
    mount();
    expect(ioCallback).toBeNull(); // never even observes
    expect(screen.queryByRole('button', { name: /Play|Pause|Replay/ })).not.toBeInTheDocument();
    expect(ranking()).toEqual(['Beta: 300', 'Alpha: 100', 'Gamma: 10']);
    const slider = screen.getByRole('slider');
    fireEvent.keyDown(slider, { key: 'Home' });
    expect(ranking()).toEqual(['Alpha: 100', 'Beta: 50', 'Gamma: 10']);
  });
});
