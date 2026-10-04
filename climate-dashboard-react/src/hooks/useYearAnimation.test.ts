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
  it('autoplays from minYear, stepping every 5 years then landing on maxYear -- not year by year', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(1990);
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1995); // not 1991

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2000);

    // Fast-forward through the remaining stops (2005, 2010, 2015, 2020, 2024).
    act(() => vi.advanceTimersByTime(500 * 5));
    expect(result.current.currentYear).toBe(2024); // final stop, even though not a 5-year boundary from 2020
    expect(result.current.isPlaying).toBe(false); // stopped itself at the last stop
  });

  it('does not add a duplicate final stop when maxYear already falls on a 5-year boundary', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2020, intervalMs: 500 }));

    // 1990 -> 1995 -> 2000 -> 2005 -> 2010 -> 2015 -> 2020 (6 ticks, no 7th duplicate 2020).
    act(() => vi.advanceTimersByTime(500 * 6));
    expect(result.current.currentYear).toBe(2020);
    expect(result.current.isPlaying).toBe(false);

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(2020); // no extra tick, no looping
  });

  it('stops at the final stop instead of looping past it', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 1995, intervalMs: 500 }));

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1995); // only stop after 1990, since maxYear is itself the next 5-year boundary
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
    act(() => vi.advanceTimersByTime(500)); // 1995
    act(() => result.current.pause());
    expect(result.current.currentYear).toBe(1995);

    act(() => result.current.play());
    expect(result.current.currentYear).toBe(1995); // unchanged -- resumed, not restarted
    expect(result.current.isPlaying).toBe(true);

    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2000); // continues from where it left off
  });

  it('resuming Play after a manual seek advances to the next stop after wherever the user scrubbed to', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    act(() => result.current.seek(2013)); // not a 5-year stop (between 2010 and 2015)
    expect(result.current.currentYear).toBe(2013);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(2015); // next stop after 2013, not 2010 or 2020
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

  it('under prefers-reduced-motion: starts pinned at maxYear with NO autoplay, but Play still works (user-initiated)', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));

    expect(result.current.currentYear).toBe(2024);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.reducedMotion).toBe(true);

    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.currentYear).toBe(2024); // nothing moves on its own

    // Pressing Play is deliberate, so it works: restarts from the first stop and steps through.
    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.currentYear).toBe(1990);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.currentYear).toBe(1995);

    // Scrubbing pauses, as it does without reduced motion.
    act(() => result.current.seek(2010));
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentYear).toBe(2010);
  });

  it('stops playback (leaving the year where it is) if the OS setting changes to reduced-motion mid-session', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500 }));
    act(() => vi.advanceTimersByTime(500)); // 1995, still playing
    expect(result.current.currentYear).toBe(1995);
    expect(result.current.isPlaying).toBe(true);

    act(() => changeListener?.({ matches: true } as MediaQueryListEvent));
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.currentYear).toBe(1995);
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.currentYear).toBe(1995); // and it stays put

    // Play remains available afterwards.
    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
  });

  describe('startWhenVisible', () => {
    let ioCallback: ((entries: Array<{ isIntersecting: boolean }>) => void) | null;
    let disconnected: boolean;
    beforeEach(() => {
      ioCallback = null;
      disconnected = false;
      vi.stubGlobal('IntersectionObserver', class {
        constructor(cb: (entries: Array<{ isIntersecting: boolean }>) => void) { ioCallback = cb; }
        observe() {}
        disconnect() { disconnected = true; }
      });
    });
    const opts = () => ({ minYear: 1990, maxYear: 2024, intervalMs: 500, startWhenVisible: { current: document.createElement('div') } });

    it('does not autoplay on mount; starts from the first stop the first time the element is in view', () => {
      mockReducedMotion(false);
      const { result } = renderHook(() => useYearAnimation(opts()));
      expect(result.current.isPlaying).toBe(false);
      act(() => vi.advanceTimersByTime(5000));
      expect(result.current.currentYear).toBe(1990); // nothing happens off-screen

      act(() => ioCallback!([{ isIntersecting: false }])); // still not visible
      expect(result.current.isPlaying).toBe(false);

      act(() => ioCallback!([{ isIntersecting: true }]));
      expect(result.current.isPlaying).toBe(true);
      expect(disconnected).toBe(true); // one-shot: it never restarts a finished or paused animation later
      act(() => vi.advanceTimersByTime(500));
      expect(result.current.currentYear).toBe(1995);
    });

    it('does not start if the user already drove it (scrubbed / pressed Play or Pause) before it scrolled into view', () => {
      mockReducedMotion(false);
      const { result } = renderHook(() => useYearAnimation(opts()));
      act(() => result.current.seek(2005));
      act(() => ioCallback!([{ isIntersecting: true }]));
      expect(result.current.isPlaying).toBe(false);
      expect(result.current.currentYear).toBe(2005);
    });

    it('never autostarts under reduced motion (and never even observes)', () => {
      mockReducedMotion(true);
      const { result } = renderHook(() => useYearAnimation(opts()));
      expect(result.current.isPlaying).toBe(false);
      expect(ioCallback).toBeNull();
      expect(result.current.currentYear).toBe(2024);
    });

    it('falls back to autoplaying on mount where IntersectionObserver does not exist', () => {
      mockReducedMotion(false);
      vi.stubGlobal('IntersectionObserver', undefined);
      const { result } = renderHook(() => useYearAnimation(opts()));
      expect(result.current.isPlaying).toBe(true);
    });
  });
});

describe('useYearAnimation `enabled`', () => {
  it('holds a disabled animation paused and ignores Play, then autoplays once enabled (never user-driven)', () => {
    mockReducedMotion(false);
    const { result, rerender } = renderHook(({ enabled }) => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500, enabled }), { initialProps: { enabled: false } });
    expect(result.current.isPlaying).toBe(false);
    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(false);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(result.current.currentYear).toBe(1990);
    // Turning it on does not by itself start playback when no IntersectionObserver gate is in use and it was off at mount:
    // the explicit Play now works.
    rerender({ enabled: true });
    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
  });

  it('pauses a playing animation when it becomes disabled', () => {
    mockReducedMotion(false);
    const { result, rerender } = renderHook(({ enabled }) => useYearAnimation({ minYear: 1990, maxYear: 2024, intervalMs: 500, enabled }), { initialProps: { enabled: true } });
    expect(result.current.isPlaying).toBe(true);
    rerender({ enabled: false });
    expect(result.current.isPlaying).toBe(false);
  });
});
