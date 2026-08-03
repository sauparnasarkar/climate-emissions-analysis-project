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
  it('autoplays from minYear, stepping to each decade boundary then maxYear -- not year by year', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(1990);
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2000); // not 1991

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2010);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2020);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2024); // final stop, even though not a decade boundary
    expect(result.current.isPlaying).toBe(false); // stopped itself at the last stop
  });

  it('does not add a duplicate final stop when maxYear already falls on a decade boundary', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2020, intervalMs: 500 }));

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2000);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2010);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2020);
    expect(result.current.isPlaying).toBe(false);

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(2020); // no extra tick, no looping
  });

  it('stops at the final stop instead of looping past it', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1995, intervalMs: 500 }));

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1995); // only stop after 1990, since maxYear < 2000
    expect(result.current.isPlaying).toBe(false);

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(1995);
  });

  it('play() restarts from the first stop once playback has finished at maxYear', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1995, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(500)); // reaches and stops at 1995
    expect(result.current.currentYear).toBe(1995);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.play());
    expect(result.current.currentYear).toBe(1990);
    expect(result.current.isPlaying).toBe(true);
  });

  it('play() resumes from the current stop when playback was merely paused, not finished', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(500)); // 2000
    act(() => result.current.pause());
    expect(result.current.currentYear).toBe(2000);

    act(() => result.current.play());
    expect(result.current.currentYear).toBe(2000); // unchanged -- resumed, not restarted
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2010); // continues from where it left off
  });

  it('resuming Play after a manual seek advances to the next stop after wherever the user scrubbed to', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    act(() => result.current.seek(2015)); // not a decade stop
    expect(result.current.currentYear).toBe(2015);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2020); // next stop after 2015, not 2016 or 2010
  });

  it('toggle() alternates between play and pause', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024 }));
    expect(result.current.isPlaying).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.toggle());
    expect(result.current.isPlaying).toBe(true);
  });

  it('seek() always pauses, allows any year (not just stops), and clamps to [minYear, maxYear]', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024 }));

    act(() => result.current.seek(2003)); // arbitrary non-stop year
    expect(result.current.currentYear).toBe(2003);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.seek(2050));
    expect(result.current.currentYear).toBe(2024);

    act(() => result.current.seek(1900));
    expect(result.current.currentYear).toBe(1990);
  });

  it('pins at maxYear with playback disabled when prefers-reduced-motion is set on mount', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(2024);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.reducedMotion).toBe(true);

    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(false); // no-op

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(2024); // no autoplay ticking at all

    // Manual scrubbing still works even though autoplay is disabled.
    act(() => result.current.seek(1995));
    expect(result.current.currentYear).toBe(1995);
  });

  it('stops playback and snaps to maxYear if the OS setting changes to reduced-motion mid-session', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(500)); // 2000, still playing
    expect(result.current.currentYear).toBe(2000);
    expect(result.current.isPlaying).toBe(true);

    act(() => changeListener?.({ matches: true } as MediaQueryListEvent));
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentYear).toBe(2024);
  });
});
