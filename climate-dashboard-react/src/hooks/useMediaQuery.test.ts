import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PHONE_QUERY, useMediaQuery } from './useMediaQuery';

afterEach(() => vi.unstubAllGlobals());

function stub(matches: boolean) {
  let listener: (() => void) | undefined;
  const mq = { matches, addEventListener: vi.fn((_: string, l: () => void) => { listener = l; }), removeEventListener: vi.fn() };
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mq));
  return { mq, fire: (m: boolean) => { mq.matches = m; listener?.(); } };
}

describe('useMediaQuery', () => {
  it('reports whether the query matches and follows it as it changes', () => {
    const s = stub(false);
    const { result } = renderHook(() => useMediaQuery(PHONE_QUERY));
    expect(result.current).toBe(false);
    act(() => s.fire(true));
    expect(result.current).toBe(true);
    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 640px)');
  });
  it('stops listening on unmount', () => {
    const s = stub(true);
    const { result, unmount } = renderHook(() => useMediaQuery(PHONE_QUERY));
    expect(result.current).toBe(true);
    unmount();
    expect(s.mq.removeEventListener).toHaveBeenCalled();
  });
  it('is false where matchMedia does not exist', () => {
    vi.stubGlobal('matchMedia', undefined);
    expect(renderHook(() => useMediaQuery(PHONE_QUERY)).result.current).toBe(false);
  });
});
