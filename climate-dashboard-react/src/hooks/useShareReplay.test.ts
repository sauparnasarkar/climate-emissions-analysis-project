import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useShareReplay } from './useShareReplay';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('useShareReplay', () => {
  it('is idle until started, then steps a year per interval from the first year to the target and hands back', () => {
    const { result } = renderHook(() => useShareReplay(1970, 1973, false, 250));
    expect(result.current.replayYear).toBeNull();
    act(() => result.current.start());
    expect(result.current.replayYear).toBe(1970);
    act(() => { vi.advanceTimersByTime(250); });
    expect(result.current.replayYear).toBe(1971);
    act(() => { vi.advanceTimersByTime(500); });
    expect(result.current.replayYear).toBe(1973); // the target frame is shown
    act(() => { vi.advanceTimersByTime(250); });
    expect(result.current.replayYear).toBeNull(); // then it is over
    expect(result.current.replaying).toBe(false);
  });

  it('does nothing when the target is not after the first year', () => {
    const { result } = renderHook(() => useShareReplay(1970, 1970, false, 250));
    act(() => result.current.start());
    expect(result.current.replayYear).toBeNull();
  });

  it('stops on request, when the target changes, and when the page starts playing', () => {
    const { result, rerender } = renderHook(({ target, cancel }) => useShareReplay(1970, target, cancel, 250), { initialProps: { target: 2000, cancel: false } });
    act(() => result.current.start());
    act(() => result.current.stop());
    expect(result.current.replayYear).toBeNull();
    act(() => result.current.start());
    rerender({ target: 2010, cancel: false });
    expect(result.current.replayYear).toBeNull();
    act(() => result.current.start());
    expect(result.current.replayYear).toBe(1970);
    rerender({ target: 2010, cancel: true });
    expect(result.current.replayYear).toBeNull();
  });
});
