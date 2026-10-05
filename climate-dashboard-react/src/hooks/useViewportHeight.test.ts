import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useViewportHeight } from './useViewportHeight';

const original = window.innerHeight;
afterEach(() => { Object.defineProperty(window, 'innerHeight', { configurable: true, value: original }); });

describe('useViewportHeight', () => {
  it('starts at the window height and follows resizes', () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 });
    const { result } = renderHook(() => useViewportHeight());
    expect(result.current).toBe(800);
    act(() => { Object.defineProperty(window, 'innerHeight', { configurable: true, value: 640 }); window.dispatchEvent(new Event('resize')); });
    expect(result.current).toBe(640);
  });
});
