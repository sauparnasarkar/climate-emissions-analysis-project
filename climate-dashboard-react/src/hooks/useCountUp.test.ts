import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCountUp } from './useCountUp';

function mockReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? matches : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useCountUp', () => {
  it('does not jump straight to the target when motion is not reduced', () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useCountUp(100, 1000));
    // Synchronously after mount, before any rAF frame has run -- still the initial value,
    // proving the animation path was taken rather than the reduced-motion shortcut.
    expect(result.current).toBe(0);
  });

  it('jumps straight to the target when prefers-reduced-motion is set (SPEC.md §5.10)', () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useCountUp(100, 1500));
    expect(result.current).toBe(100);
  });

  it('jumps straight to the next target on a later update too, not just first mount', () => {
    mockReducedMotion(true);
    const { result, rerender } = renderHook(({ value }) => useCountUp(value, 1500), {
      initialProps: { value: 100 },
    });
    expect(result.current).toBe(100);
    rerender({ value: 250 });
    expect(result.current).toBe(250);
  });
});
