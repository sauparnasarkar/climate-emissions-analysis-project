import { describe, expect, it } from 'vitest';
import { computeAutoplayStops } from './yearStops';

describe('computeAutoplayStops', () => {
  it('gives the decade stops of the Area 2 map: 1970, 1980 … 2020, then the latest year', () => {
    expect(computeAutoplayStops(1970, 2024, 10)).toEqual([1970, 1980, 1990, 2000, 2010, 2020, 2024]);
  });
  it('does not repeat the last year when it falls on a boundary, and handles a range that is not decade-aligned', () => {
    expect(computeAutoplayStops(1990, 2020, 10)).toEqual([1990, 2000, 2010, 2020]);
    expect(computeAutoplayStops(1993, 2024, 10)).toEqual([1993, 2000, 2010, 2020, 2024]);
  });
  it('is a single stop for a degenerate range', () => {
    expect(computeAutoplayStops(2024, 2024, 10)).toEqual([2024]);
  });
});
