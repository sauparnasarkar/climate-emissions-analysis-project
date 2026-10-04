import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CAROUSEL_DWELL_MS, useCarousel } from './useCarousel';

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? matches : false, media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
}
function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event('visibilitychange'));
}
const blurEvent = (inside: boolean) => ({ currentTarget: { contains: () => inside }, relatedTarget: {} }) as unknown as React.FocusEvent;

beforeEach(() => { vi.useFakeTimers(); mockReducedMotion(false); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); setHidden(false); });

describe('useCarousel', () => {
  it('advances after the dwell time and then stops after one full cycle, holding on the last slide', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    expect(result.current.index).toBe(0);
    expect(result.current.autoplay).toBe(true);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS - 1); });
    expect(result.current.index).toBe(0);
    act(() => { vi.advanceTimersByTime(1); });
    expect(result.current.index).toBe(1);
    expect(result.current.autoplay).toBe(false); // one cycle done
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(1);
  });

  it('a manual change stops autoplay until Play is pressed; Play then runs one more cycle', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => result.current.next());
    expect(result.current.index).toBe(1);
    expect(result.current.autoplay).toBe(false);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 2); });
    expect(result.current.index).toBe(1);
    act(() => result.current.play());
    expect(result.current.autoplay).toBe(true);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(0); // wraps
    expect(result.current.autoplay).toBe(false);
  });

  it('wraps for prev/next and goTo, and Pause stops it', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => result.current.prev());
    expect(result.current.index).toBe(1);
    act(() => result.current.goTo(0));
    expect(result.current.index).toBe(0);
    act(() => result.current.play());
    act(() => result.current.pause());
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 2); });
    expect(result.current.index).toBe(0);
  });

  it('pauses while the pointer is over it or focus is inside, and resumes when it leaves', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => result.current.regionHandlers.onMouseEnter());
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
    expect(result.current.autoplay).toBe(true); // the user did not stop it; it is only held
    act(() => result.current.regionHandlers.onMouseLeave());
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('focus moving between controls inside the region does not resume; leaving the region does', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => result.current.regionHandlers.onFocusCapture());
    act(() => result.current.regionHandlers.onBlurCapture(blurEvent(true)));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 2); });
    expect(result.current.index).toBe(0);
    act(() => result.current.regionHandlers.onBlurCapture(blurEvent(false)));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('pauses while the browser tab is hidden', () => {
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    act(() => setHidden(true));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
    act(() => setHidden(false));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('starts stopped under reduced motion and never auto-advances', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useCarousel({ count: 2 }));
    expect(result.current.autoplay).toBe(false);
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
    act(() => result.current.play()); // an explicit Play is a request for movement
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS); });
    expect(result.current.index).toBe(1);
  });

  it('does nothing for a single slide', () => {
    const { result } = renderHook(() => useCarousel({ count: 1 }));
    act(() => { vi.advanceTimersByTime(CAROUSEL_DWELL_MS * 3); });
    expect(result.current.index).toBe(0);
  });
});
