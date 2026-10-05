import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CAROUSEL_DWELL_MS, useCarousel } from './useCarousel';

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? matches : false, media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
}

beforeEach(() => { vi.useFakeTimers(); mockReducedMotion(false); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('useCarousel', () => {
  it('rotates after 5 seconds on each banner (decision 71)', () => {
    expect(CAROUSEL_DWELL_MS).toBe(5000);
  });

  it('rotates every dwell period while auto-rotate is on, and keeps going round', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    expect(result.current.index).toBe(0);
    expect(result.current.autoplay).toBe(true);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS - 1); });
    expect(result.current.index).toBe(0);
    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.index).toBe(1);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(0); // wraps; only Pause stops it
    expect(result.current.autoplay).toBe(true);
  });

  it('Pause stops it and Play starts it again', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => result.current.pause());
    expect(result.current.autoplay).toBe(false);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
    act(() => result.current.play());
    expect(result.current.autoplay).toBe(true);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('moving to a slide by hand does not change the Play/Pause state; the dwell starts afresh on the chosen slide', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS - 100); });
    act(() => result.current.next());
    expect(result.current.index).toBe(1);
    expect(result.current.autoplay).toBe(true);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS - 100); }); // not yet a full dwell on slide 2
    expect(result.current.index).toBe(1);
    act(() => { vi.advanceTimersByTime(100); });
    expect(result.current.index).toBe(0);
    // and a paused carousel stays paused when navigated by hand
    act(() => result.current.pause());
    act(() => result.current.prev());
    expect(result.current.index).toBe(1);
    expect(result.current.autoplay).toBe(false);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 2); });
    expect(result.current.index).toBe(1);
  });

  it('wraps for prev, next and goTo', () => {
    const { result } = renderHook(() => useCarousel({ count: 3 }));
    act(() => result.current.prev());
    expect(result.current.index).toBe(2);
    act(() => result.current.next());
    expect(result.current.index).toBe(0);
    act(() => result.current.goTo(4));
    expect(result.current.index).toBe(1);
  });

  it('is not affected by the pointer, focus or the tab being hidden: only the button decides', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
  });

  it('starts paused under reduced motion and never auto-advances until Play is pressed', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    expect(result.current.autoplay).toBe(false);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
    act(() => result.current.play());
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('does nothing for a single slide', () => {
    const { result } = renderHook(() => useCarousel({ count: 1 }));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
  });

  it('reports the direction of each move: Next and auto-rotate are forward (also wrapping last -> first), Previous is back, a tab follows the slide order', () => {
    const { result } = renderHook(() => useCarousel({ count: 3 }));
    expect([result.current.previous, result.current.direction]).toEqual([null, 'forward']);
    act(() => result.current.next());
    expect([result.current.index, result.current.previous, result.current.direction]).toEqual([1, 0, 'forward']);
    act(() => result.current.prev());
    expect([result.current.index, result.current.previous, result.current.direction]).toEqual([0, 1, 'back']);
    act(() => result.current.prev()); // first -> last wraps and is still "back"
    expect([result.current.index, result.current.previous, result.current.direction]).toEqual([2, 0, 'back']);
    act(() => result.current.next()); // last -> first wraps and is still "forward"
    expect([result.current.index, result.current.previous, result.current.direction]).toEqual([0, 2, 'forward']);
    act(() => result.current.goTo(2)); // a later slide by tab: forward
    expect(result.current.direction).toBe('forward');
    act(() => result.current.goTo(1)); // an earlier one: back
    expect(result.current.direction).toBe('back');
  });

  it('auto-rotate round the last slide to the first is forward', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect([result.current.index, result.current.previous, result.current.direction]).toEqual([0, 1, 'forward']);
  });
});
