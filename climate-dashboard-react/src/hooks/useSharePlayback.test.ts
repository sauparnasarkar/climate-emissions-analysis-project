import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSharePlayback } from './useSharePlayback';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('useSharePlayback', () => {
  it('starts on the latest year, paused', () => {
    const { result } = renderHook(() => useSharePlayback(1970, 1975, 250));
    expect(result.current.year).toBe(1975);
    expect(result.current.playing).toBe(false);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(result.current.year).toBe(1975); // never autoplays
  });

  it('follows the latest year while the range is still arriving, until the user moves it', () => {
    const { result, rerender } = renderHook(({ min, max }) => useSharePlayback(min, max, 250), { initialProps: { min: 1970, max: 1970 } });
    rerender({ min: 1970, max: 2024 }); // the data arrived
    expect(result.current.year).toBe(2024);
    act(() => result.current.seek(1990));
    rerender({ min: 1970, max: 2025 });
    expect(result.current.year).toBe(1990);
  });

  it('Play from the end replays from the first year, one year per step, and stops at the last', () => {
    const { result } = renderHook(() => useSharePlayback(1970, 1973, 250));
    act(() => result.current.toggle());
    expect(result.current.year).toBe(1970);
    expect(result.current.playing).toBe(true);
    act(() => { vi.advanceTimersByTime(249); });
    expect(result.current.year).toBe(1970);
    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.year).toBe(1971);
    act(() => { vi.advanceTimersByTime(500); });
    expect(result.current.year).toBe(1973);
    expect(result.current.playing).toBe(false); // ended on the latest year
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.year).toBe(1973);
  });

  it('Pause holds the year, and scrubbing pauses and jumps', () => {
    const { result } = renderHook(() => useSharePlayback(1970, 1980, 250));
    act(() => result.current.seek(1972));
    act(() => result.current.toggle());
    act(() => { vi.advanceTimersByTime(250); });
    expect(result.current.year).toBe(1973);
    act(() => result.current.toggle());
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.year).toBe(1973);
    act(() => result.current.toggle());
    act(() => result.current.seek(1976));
    expect(result.current.playing).toBe(false);
    expect(result.current.year).toBe(1976);
  });

  it('keeps the year inside a range that changes under it', () => {
    const { result, rerender } = renderHook(({ min, max }) => useSharePlayback(min, max, 250), { initialProps: { min: 1970, max: 2024 } });
    act(() => result.current.seek(1990));
    rerender({ min: 2000, max: 2010 });
    expect(result.current.year).toBe(2000);
  });
});
