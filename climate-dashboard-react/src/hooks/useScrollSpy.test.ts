import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useScrollSpy } from './useScrollSpy';

const OFFSET = 120;
let tops: Record<string, number>;

/** Adds a section whose viewport top comes from `tops[id]`; ids in `skip` are never added (a section still loading). */
function addSections(ids: string[]) {
  for (const id of ids) {
    const el = document.createElement('section');
    el.id = id;
    el.getBoundingClientRect = () => ({ top: tops[id], bottom: tops[id] + 400, left: 0, right: 0, width: 0, height: 400, x: 0, y: tops[id], toJSON: () => ({}) });
    document.body.appendChild(el);
  }
}

function setPage({ scrollY, scrollHeight, innerHeight = 800 }: { scrollY: number; scrollHeight: number; innerHeight?: number }) {
  Object.defineProperty(window, 'scrollY', { value: scrollY, configurable: true });
  Object.defineProperty(window, 'innerHeight', { value: innerHeight, configurable: true });
  Object.defineProperty(document.documentElement, 'scrollHeight', { value: scrollHeight, configurable: true });
}

/** Fires a scroll and runs the animation frame the hook schedules. */
function scroll() {
  act(() => { window.dispatchEvent(new Event('scroll')); vi.runAllTimers(); });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => setTimeout(() => cb(0), 0));
  vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id));
  tops = { a: 200, b: 900, c: 1600 };
  setPage({ scrollY: 0, scrollHeight: 3000 });
});
afterEach(() => { document.body.innerHTML = ''; vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('useScrollSpy', () => {
  it('starts on the first section while none has reached the pinned rows', () => {
    addSections(['a', 'b', 'c']);
    const { result } = renderHook(() => useScrollSpy(['a', 'b', 'c'], OFFSET));
    expect(result.current).toBe('a');
  });

  it('moves to the last section whose top has passed under the pinned rows (with a few px of slack)', () => {
    addSections(['a', 'b', 'c']);
    const { result } = renderHook(() => useScrollSpy(['a', 'b', 'c'], OFFSET));
    tops = { a: -300, b: OFFSET + 4, c: 700 }; // b is exactly at the threshold + slack
    scroll();
    expect(result.current).toBe('b');
    tops = { a: -900, b: -200, c: OFFSET + 5 }; // c is one px short
    scroll();
    expect(result.current).toBe('b');
  });

  it('selects the last section once the page cannot scroll further, even if it never reached the top', () => {
    addSections(['a', 'b', 'c']);
    const { result } = renderHook(() => useScrollSpy(['a', 'b', 'c'], OFFSET));
    tops = { a: -900, b: -200, c: 500 };
    setPage({ scrollY: 2200, scrollHeight: 3000 }); // 2200 + 800 >= 3000 - 2
    scroll();
    expect(result.current).toBe('c');
  });

  it('does not jump to the last section on a page that fits the screen (scrollY 0 at "bottom")', () => {
    addSections(['a', 'b']);
    setPage({ scrollY: 0, scrollHeight: 800 });
    const { result } = renderHook(() => useScrollSpy(['a', 'b'], OFFSET));
    expect(result.current).toBe('a');
  });

  it('skips ids with no element yet and picks among the ones that exist', () => {
    addSections(['a', 'c']); // b is still loading
    const { result } = renderHook(() => useScrollSpy(['a', 'b', 'c'], OFFSET));
    tops = { a: -500, b: 0, c: 50 };
    scroll();
    expect(result.current).toBe('c');
  });

  it('falls back to the first id when none of the sections exist', () => {
    const { result } = renderHook(() => useScrollSpy(['a', 'b'], OFFSET));
    expect(result.current).toBe('a');
  });

  it('coalesces a burst of scroll events into one frame, and stops listening and cancels the frame on unmount', () => {
    addSections(['a', 'b']);
    const raf = vi.fn((cb: FrameRequestCallback) => setTimeout(() => cb(0), 0));
    vi.stubGlobal('requestAnimationFrame', raf);
    const cancel = vi.fn((id: number) => clearTimeout(id));
    vi.stubGlobal('cancelAnimationFrame', cancel);
    const { unmount } = renderHook(() => useScrollSpy(['a', 'b'], OFFSET));
    raf.mockClear();
    act(() => { for (let i = 0; i < 5; i++) window.dispatchEvent(new Event('scroll')); });
    expect(raf).toHaveBeenCalledTimes(1);
    unmount();
    expect(cancel).toHaveBeenCalledTimes(1); // the pending frame
    raf.mockClear();
    window.dispatchEvent(new Event('scroll'));
    expect(raf).not.toHaveBeenCalled();
  });
});
