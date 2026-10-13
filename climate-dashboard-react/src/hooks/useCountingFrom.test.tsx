import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { COUNTING_FROM_MIN_YEAR, useCountingFrom } from './useCountingFrom';

const at = (url: string) => renderHook(() => useCountingFrom(), { wrapper: ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter> }).result.current[0];

describe('useCountingFrom', () => {
  it('is null (since records began) when ?from= is absent, and the year when it is a recognised one', () => {
    expect(COUNTING_FROM_MIN_YEAR).toBe(1970);
    expect(at('/historical')).toBeNull();
    expect(at('/historical?from=1990')).toBe(1990);
    expect(at('/historical?from=1970&view=cumulative')).toBe(1970);
  });

  it('reads an unrecognised or out-of-window year as absent, never as a request the API would refuse', () => {
    for (const bad of ['1969', '1850', 'abc', '', '19900', '3000', '1990.5']) expect(at(`/historical?from=${bad}`)).toBeNull();
  });
});
