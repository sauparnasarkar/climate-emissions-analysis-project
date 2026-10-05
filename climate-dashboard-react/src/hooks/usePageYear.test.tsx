import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { parseYearParam, usePageYear } from './usePageYear';

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: false, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

const YEARS = Array.from({ length: 55 }, (_, i) => 1970 + i);
const wrap = (url: string) => ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>;
const setup = (url: string, years: number[] | null = YEARS) =>
  renderHook(() => ({ year: usePageYear(years), loc: useLocation() }), { wrapper: wrap(url) });

describe('parseYearParam', () => {
  it('reads a four-digit year and ignores anything else', () => {
    expect(parseYearParam('?year=2010')).toBe(2010);
    expect(parseYearParam('?year=abc')).toBeUndefined();
    expect(parseYearParam('?year=20')).toBeUndefined();
    expect(parseYearParam('')).toBeUndefined();
  });
});

describe('usePageYear', () => {
  it('defaults to the latest year and leaves the URL clean', () => {
    const { result } = setup('/overview?countries=China');
    expect(result.current.year.currentYear).toBe(2024);
    expect(result.current.year.isPlaying).toBe(false);
    expect(result.current.loc.search).toBe('?countries=China');
  });

  it('opens on ?year=, clamped to the range, and a link with an out-of-range year lands on the nearest end', () => {
    expect(setup('/overview?year=2010').result.current.year.currentYear).toBe(2010);
    expect(setup('/overview?year=1850').result.current.year.currentYear).toBe(1970);
  });

  it('writes the year to the URL as it changes, keeping other params and the hash, and drops it at the latest year', () => {
    const { result } = setup('/overview?countries=China&countries=India#share');
    act(() => result.current.year.seek(1990));
    expect(result.current.loc.search).toBe('?countries=China&countries=India&year=1990');
    expect(result.current.loc.hash).toBe('#share');
    act(() => result.current.year.seek(2024));
    expect(result.current.loc.search).toBe('?countries=China&countries=India');
  });

  it('plays by decade, stops on the latest year, and the URL follows each step', () => {
    const { result } = setup('/overview?year=2010');
    act(() => result.current.year.play());
    act(() => { vi.advanceTimersByTime(1750); });
    expect(result.current.year.currentYear).toBe(2020);
    expect(result.current.loc.search).toBe('?year=2020');
    act(() => { vi.advanceTimersByTime(1750); });
    expect(result.current.year.currentYear).toBe(2024);
    expect(result.current.year.isPlaying).toBe(false);
    expect(result.current.loc.search).toBe('');
  });

  it('follows the URL when it changes from outside while the page stays mounted (back/forward, another deep link), without overwriting it', () => {
    const { result } = renderHook(() => ({ year: usePageYear(YEARS), loc: useLocation(), nav: useNavigate() }), { wrapper: wrap('/overview?year=2010') });
    expect(result.current.year.currentYear).toBe(2010);
    act(() => result.current.nav('/overview?year=1990&countries=China'));
    expect(result.current.year.currentYear).toBe(1990);
    expect(result.current.loc.search).toBe('?year=1990&countries=China'); // not rewritten back to 2010
    act(() => result.current.nav('/overview')); // a link to the bare page = the latest year
    expect(result.current.year.currentYear).toBe(2024);
    expect(result.current.loc.search).toBe('');
    act(() => result.current.nav(-1)); // back
    expect(result.current.year.currentYear).toBe(1990);
    expect(result.current.loc.search).toBe('?year=1990&countries=China');
  });

  it('does not touch the URL until the series has loaded (the year is unknown until then)', () => {
    const { result, rerender } = renderHook(({ years }) => ({ year: usePageYear(years), loc: useLocation() }), { wrapper: wrap('/overview?year=2010'), initialProps: { years: null as number[] | null } });
    expect(result.current.loc.search).toBe('?year=2010');
    rerender({ years: YEARS });
    expect(result.current.year.currentYear).toBe(2010);
    expect(result.current.loc.search).toBe('?year=2010');
  });
});
