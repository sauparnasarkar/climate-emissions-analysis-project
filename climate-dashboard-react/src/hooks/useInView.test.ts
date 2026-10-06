import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useInView } from './useInView';

type Callback = (entries: Array<{ isIntersecting: boolean }>) => void;
let callback: Callback;
const observe = vi.fn();
const disconnect = vi.fn();

function stubObserver() {
  vi.stubGlobal('IntersectionObserver', class { constructor(cb: Callback) { callback = cb; } observe = observe; disconnect = disconnect; });
}

afterEach(() => { vi.unstubAllGlobals(); observe.mockClear(); disconnect.mockClear(); });

describe('useInView', () => {
  it('follows the observer: off screen -> false, back on screen -> true', () => {
    stubObserver();
    const el = document.createElement('div');
    const { result } = renderHook(() => useInView({ current: el }));
    expect(observe).toHaveBeenCalledWith(el);
    expect(result.current).toBe(true);
    act(() => callback([{ isIntersecting: false }]));
    expect(result.current).toBe(false);
    act(() => callback([{ isIntersecting: true }]));
    expect(result.current).toBe(true);
  });

  it('disconnects the observer on unmount', () => {
    stubObserver();
    const { unmount } = renderHook(() => useInView({ current: document.createElement('div') }));
    unmount();
    expect(disconnect).toHaveBeenCalled();
  });

  it('reports true where there is no IntersectionObserver, and with no element yet', () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    expect(renderHook(() => useInView({ current: document.createElement('div') })).result.current).toBe(true);
    stubObserver();
    expect(renderHook(() => useInView({ current: null })).result.current).toBe(true);
  });
});
