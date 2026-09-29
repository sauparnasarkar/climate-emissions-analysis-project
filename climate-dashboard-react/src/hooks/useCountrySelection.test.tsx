import type { ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { MAX_SELECTED_COUNTRIES } from '../constants';
import { canonicalCountries, useSelectedCountries, useSelectedCountry } from './useCountrySelection';

const EXPANDED = ['China', 'United States', 'India', 'Russia', 'Japan', 'Germany', 'Brazil', 'United Kingdom', 'South Africa', 'Australia', 'Vietnam', 'Canada'];
const DEFAULTS = EXPANDED.slice(0, 10);

function setup<T>(initial: string, hook: () => T) {
  const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>;
  return renderHook(() => ({ value: hook(), loc: useLocation() }), { wrapper });
}

describe('canonicalCountries', () => {
  it('canonicalises case, trims, drops unknowns and duplicates, keeps first-seen order', () => {
    expect(canonicalCountries(['india', ' CHINA ', 'Atlantis', 'India', 'china'], EXPANDED)).toEqual(['India', 'China']);
  });
  it('caps at the maximum', () => {
    expect(canonicalCountries(EXPANDED, EXPANDED)).toHaveLength(MAX_SELECTED_COUNTRIES);
    expect(canonicalCountries(EXPANDED, EXPANDED, 3)).toEqual(EXPANDED.slice(0, 3));
  });
});

describe('useSelectedCountries', () => {
  it('uses the defaults when there is no param', () => {
    expect(setup('/x', () => useSelectedCountries(DEFAULTS, EXPANDED)).result.current.value[0]).toEqual(DEFAULTS);
  });

  it('honours repeated ?countries= values (validated, deduped)', () => {
    const { result } = setup('/x?countries=vietnam&countries=India&countries=Vietnam', () => useSelectedCountries(DEFAULTS, EXPANDED));
    expect(result.current.value[0]).toEqual(['Vietnam', 'India']);
  });

  it('falls back to the defaults when nothing valid remains', () => {
    const { result } = setup('/x?countries=Atlantis&countries=Mordor', () => useSelectedCountries(DEFAULTS, EXPANDED));
    expect(result.current.value[0]).toEqual(DEFAULTS);
  });

  it('caps a hand-edited long list at MAX_SELECTED_COUNTRIES', () => {
    const qs = EXPANDED.map((c) => `countries=${encodeURIComponent(c)}`).join('&');
    expect(setup(`/x?${qs}`, () => useSelectedCountries(DEFAULTS, EXPANDED)).result.current.value[0]).toHaveLength(MAX_SELECTED_COUNTRIES);
  });

  it('treats a bare ?countries= as an explicitly empty selection (so clearing the picker survives a reload)', () => {
    expect(setup('/x?countries=', () => useSelectedCountries(DEFAULTS, EXPANDED)).result.current.value[0]).toEqual([]);
  });

  it('writes the selection to the URL with replace, keeping other params and the hash', () => {
    const { result } = setup('/x?gas=co2#by-country', () => useSelectedCountries(DEFAULTS, EXPANDED));
    act(() => result.current.value[1](['India', 'Vietnam']));
    expect(result.current.loc.search).toBe('?gas=co2&countries=India&countries=Vietnam');
    expect(result.current.loc.hash).toBe('#by-country');
    expect(result.current.value[0]).toEqual(['India', 'Vietnam']);
  });

  it('removes the param when the selection is set back to the defaults, and encodes an empty one as ?countries=', () => {
    const { result } = setup('/x?countries=India', () => useSelectedCountries(DEFAULTS, EXPANDED));
    act(() => result.current.value[1](DEFAULTS));
    expect(result.current.loc.search).toBe('');
    act(() => result.current.value[1]([]));
    expect(result.current.loc.search).toBe('?countries=');
    expect(result.current.value[0]).toEqual([]);
  });
});

describe('useSelectedCountry', () => {
  it('honours a valid ?country= (case-insensitive) and falls back otherwise', () => {
    expect(setup('/p?country=india', () => useSelectedCountry('China', EXPANDED)).result.current.value[0]).toBe('India');
    expect(setup('/p?country=Atlantis', () => useSelectedCountry('China', EXPANDED)).result.current.value[0]).toBe('China');
    expect(setup('/p', () => useSelectedCountry('China', EXPANDED)).result.current.value[0]).toBe('China');
    expect(setup('/p?country=', () => useSelectedCountry('China', EXPANDED)).result.current.value[0]).toBe('China');
  });

  it('writes ?country= only when it differs from the fallback', () => {
    const { result } = setup('/p', () => useSelectedCountry('China', EXPANDED));
    act(() => result.current.value[1]('Vietnam'));
    expect(result.current.loc.search).toBe('?country=Vietnam');
    act(() => result.current.value[1]('China'));
    expect(result.current.loc.search).toBe('');
  });
});
