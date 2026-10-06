import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { nextStableViewport, useStableViewportHeight, useViewportHeight } from './useViewportHeight';

const original = window.innerHeight;
const originalWidth = window.innerWidth;
afterEach(() => {
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: original });
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
});

describe('useViewportHeight', () => {
  it('starts at the window height and follows resizes', () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 });
    const { result } = renderHook(() => useViewportHeight());
    expect(result.current).toBe(800);
    act(() => { Object.defineProperty(window, 'innerHeight', { configurable: true, value: 640 }); window.dispatchEvent(new Event('resize')); });
    expect(result.current).toBe(640);
  });
});

describe('nextStableViewport', () => {
  it('takes a rotation (width changed) as it is, even when the height grew', () => {
    expect(nextStableViewport({ w: 430, h: 700 }, { w: 932, h: 400 })).toEqual({ w: 932, h: 400 });
    expect(nextStableViewport({ w: 932, h: 400 }, { w: 430, h: 700 })).toEqual({ w: 430, h: 700 });
  });
  it('takes a shrink, but ignores height-only growth (Safari collapsing its toolbar while scrolling)', () => {
    const prev = { w: 430, h: 700 };
    expect(nextStableViewport(prev, { w: 430, h: 640 })).toEqual({ w: 430, h: 640 });
    expect(nextStableViewport(prev, { w: 430, h: 780 })).toBe(prev);
  });
});

describe('useStableViewportHeight', () => {
  it('starts at the window height, keeps it when the toolbar collapses (height grows), follows a shrink', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 430 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 700 });
    const { result } = renderHook(() => useStableViewportHeight());
    expect(result.current).toBe(700);
    act(() => { Object.defineProperty(window, 'innerHeight', { configurable: true, value: 780 }); window.dispatchEvent(new Event('resize')); });
    expect(result.current).toBe(700);
    act(() => { Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 }); window.dispatchEvent(new Event('resize')); });
    expect(result.current).toBe(600);
  });
});
