import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useYearAnimation } from './useYearAnimation';

// vi.stubGlobal (not a direct window.matchMedia assignment) so vi.unstubAllGlobals() in
// afterEach actually restores the original -- mirrors useCountUp.test.ts's identical helper.
let changeListener: ((e: MediaQueryListEvent) => void) | undefined;
function mockReducedMotion(matches: boolean) {
  changeListener = undefined;
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? matches : false,
      media: query,
      addEventListener: vi.fn((_event: string, listener: (e: MediaQueryListEvent) => void) => {
        changeListener = listener;
      }),
      removeEventListener: vi.fn(),
    })),
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('useYearAnimation', () => {
  it('autoplays from minYear, stepping forward one year per intervalMs tick', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1993, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(1990);
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1991);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1992);
  });

  it('stops at maxYear instead of looping past it', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1991, intervalMs: 500 }));

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1991);
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1991); // no further advance
    expect(result.current.isPlaying).toBe(false); // playback stopped itself

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(1991); // still not looping
  });

  it('play() restarts from minYear once playback has finished at maxYear', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1991, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(1000)); // reaches and stops at maxYear
    expect(result.current.currentYear).toBe(1991);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.play());
    expect(result.current.currentYear).toBe(1990);
    expect(result.current.isPlaying).toBe(true);
  });

  it('play() resumes from the current year when playback was merely paused, not finished', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2000, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(500)); // 1991
    act(() => result.current.pause());
    expect(result.current.currentYear).toBe(1991);

    act(() => result.current.play());
    expect(result.current.currentYear).toBe(1991); // unchanged -- resumed, not restarted
    expect(result.current.isPlaying).toBe(true);
  });

  it('toggle() alternates between play and pause', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2000 }));
    expect(result.current.isPlaying).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.toggle());
    expect(result.current.isPlaying).toBe(true);
  });

  it('seek() always pauses and clamps to [minYear, maxYear]', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2000 }));

    act(() => result.current.seek(1995));
    expect(result.current.currentYear).toBe(1995);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.seek(2050));
    expect(result.current.currentYear).toBe(2000);

    act(() => result.current.seek(1900));
    expect(result.current.currentYear).toBe(1990);
  });

  it('pins at maxYear with playback disabled when prefers-reduced-motion is set on mount', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2000, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(2000);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.reducedMotion).toBe(true);

    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(false); // no-op

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(2000); // no autoplay ticking at all

    // Manual scrubbing still works even though autoplay is disabled.
    act(() => result.current.seek(1995));
    expect(result.current.currentYear).toBe(1995);
  });

  it('stops playback and snaps to maxYear if the OS setting changes to reduced-motion mid-session', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2000, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(1000)); // 1992, still playing
    expect(result.current.currentYear).toBe(1992);
    expect(result.current.isPlaying).toBe(true);

    act(() => changeListener?.({ matches: true } as MediaQueryListEvent));
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentYear).toBe(2000);
  });
});
