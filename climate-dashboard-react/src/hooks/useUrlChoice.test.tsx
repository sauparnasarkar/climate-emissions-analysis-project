import type { ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { useUrlChoice } from './useUrlChoice';

const GASES = ['co2', 'methane', 'nitrous_oxide'] as const;

function setup(initial: string) {
  const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>;
  return renderHook(() => ({ choice: useUrlChoice('gas', GASES, 'co2'), loc: useLocation() }), { wrapper });
}

describe('useUrlChoice', () => {
  it('uses the fallback when the param is absent', () => {
    expect(setup('/x').result.current.choice[0]).toBe('co2');
  });

  it('reads a recognised value, ignoring case and surrounding space', () => {
    expect(setup('/x?gas=methane').result.current.choice[0]).toBe('methane');
    expect(setup('/x?gas=%20NITROUS_OXIDE%20').result.current.choice[0]).toBe('nitrous_oxide');
  });

  it('falls back on an unrecognised value, so a stale or hand-edited URL cannot reach an API call', () => {
    expect(setup('/x?gas=plutonium').result.current.choice[0]).toBe('co2');
    expect(setup('/x?gas=').result.current.choice[0]).toBe('co2');
  });

  it('writes only its own param, keeps the other params and the hash, and replaces history', () => {
    const { result } = setup('/x?countries=India&year=2000#methodology');
    act(() => result.current.choice[1]('methane'));
    expect(result.current.choice[0]).toBe('methane');
    const { search, hash } = result.current.loc;
    expect(new URLSearchParams(search).get('gas')).toBe('methane');
    expect(new URLSearchParams(search).get('countries')).toBe('India');
    expect(new URLSearchParams(search).get('year')).toBe('2000');
    expect(hash).toBe('#methodology');
  });

  it('drops the param while the choice equals the fallback, leaving a clean URL', () => {
    const { result } = setup('/x?gas=methane');
    act(() => result.current.choice[1]('co2'));
    expect(result.current.loc.search).toBe('');
  });

  it('ignores a set to a value that is not an option', () => {
    const { result } = setup('/x');
    act(() => result.current.choice[1]('plutonium'));
    expect(result.current.choice[0]).toBe('co2');
    expect(result.current.loc.search).toBe('');
  });
});
