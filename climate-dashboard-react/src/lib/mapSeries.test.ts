import { describe, expect, it } from 'vitest';
import type { WorldMapTimeSeries } from '../api/types';
import { sliceMapSeries, worldTotals } from './mapSeries';

const S: WorldMapTimeSeries = {
  iso_codes: ['AAA', 'BBB'], countries: ['Alpha', 'Beta'], years: [1988, 1989, 1990, 1991],
  values: [[1, null], [2, 0], [10, 5], [20, null]], value_range: [1, 20],
};

describe('sliceMapSeries', () => {
  it('keeps the years from `fromYear`, with the cells unchanged and a recomputed range', () => {
    const s = sliceMapSeries(S, 1990);
    expect(s.years).toEqual([1990, 1991]);
    expect(s.values).toEqual([[10, 5], [20, null]]);
    expect(s.value_range).toEqual([5, 20]); // the 1988 value 1 is no longer in range
    expect(s.iso_codes).toBe(S.iso_codes);
  });
  it('returns the input when it already starts at (or after) the year, and ignores exact zeros for the minimum', () => {
    expect(sliceMapSeries(S, 1980)).toBe(S);
    expect(sliceMapSeries(S, 1989).value_range).toEqual([2, 20]);
  });
});

describe('worldTotals', () => {
  it('sums each year across countries, counting a missing value as nothing', () => {
    expect(worldTotals(S)).toEqual([1, 2, 15, 20]);
  });
});
