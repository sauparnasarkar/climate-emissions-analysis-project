import { describe, expect, it } from 'vitest';
import type { WorldMapTimeSeries } from '../api/types';
import { latestWorldTotal, sliceMapSeries, worldTotals } from './mapSeries';

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

describe('latestWorldTotal', () => {
  const series = (values: Array<Array<number | null>>): WorldMapTimeSeries => ({ iso_codes: ['AAA', 'BBB'], countries: ['A', 'B'], years: values.map((_, i) => 2022 + i), values, value_range: [0, 1] });

  it('is the latest year\'s total when that year has data (missing cells are not zero)', () => {
    expect(latestWorldTotal(series([[1, 2], [3, null]]))).toEqual({ year: 2023, total: 3 });
  });
  it('skips a trailing year in which every cell is null, instead of reporting a total of zero', () => {
    expect(latestWorldTotal(series([[1, 2], [3, 4], [null, null]]))).toEqual({ year: 2023, total: 7 });
  });
  it('is null when no year has any data, or there are no years', () => {
    expect(latestWorldTotal(series([[null, null], [null, null]]))).toBeNull();
    expect(latestWorldTotal(series([]))).toBeNull();
  });
});
