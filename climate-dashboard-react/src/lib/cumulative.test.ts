import { describe, expect, it } from 'vitest';
import type { WorldMapTimeSeries } from '../api/types';
import { buildCumulative, fmtGt, leaders, positiveRange } from './cumulative';

const S: WorldMapTimeSeries = {
  iso_codes: ['AAA', 'BBB', 'CCC'], countries: ['Alpha', 'Beta', 'Gamma'], years: [1970, 1971, 1972],
  values: [[10, 5, null], [20, null, 1], [30, 5, 1]], value_range: [1, 30],
};

describe('buildCumulative', () => {
  it('adds the running sum of the annual values to the snapshot before the series, in GtCO₂, counting a missing year as zero', () => {
    const m = buildCumulative(S, { AAA: 1000, BBB: 500 }); // snapshot in Mt; CCC has no history before 1970
    expect(m[0]).toEqual([1.01, 0.505, null]); // CCC: nothing emitted yet -> no data, not a zero
    expect(m[1]).toEqual([1.03, 0.505, 0.001]);
    expect(m[2][0]).toBeCloseTo(1.06);
    expect(m[2][1]).toBeCloseTo(0.51);
    expect(m[2][2]).toBeCloseTo(0.002);
  });
  it('never decreases for any country and does not touch the input', () => {
    const before = JSON.stringify(S);
    const m = buildCumulative(S, {});
    for (let i = 0; i < 3; i++) for (let y = 1; y < 3; y++) expect(m[y][i] ?? 0).toBeGreaterThanOrEqual(m[y - 1][i] ?? 0);
    expect(JSON.stringify(S)).toBe(before);
  });
});

describe('positiveRange', () => {
  it('is the smallest positive and the largest value; zeros do not set the floor', () => {
    expect(positiveRange([[0, 0.5], [2, 8]])).toEqual([0.5, 8]);
    expect(positiveRange([[0, 0]])).toEqual([0, 0]);
    expect(positiveRange([[null, 3], [null, 1]])).toEqual([1, 3]); // missing values are skipped
  });
});

describe('leaders', () => {
  it('ranks the largest values with their share of the whole row, skipping missing and non-positive ones', () => {
    const l = leaders([10, null, 30, 0, 60], ['a', 'b', 'c', 'd', 'e'], ['A', 'B', 'C', 'D', 'E'], 2);
    expect(l.map((x) => [x.name, x.iso, x.value])).toEqual([['e', 'E', 60], ['c', 'C', 30]]);
    expect(l[0].sharePct).toBeCloseTo(60); // 60 of 100
    expect(l[1].sharePct).toBeCloseTo(30);
  });
  it('breaks ties by position and returns fewer than k when there are fewer', () => {
    expect(leaders([5, 5], ['a', 'b'], ['A', 'B'], 5).map((x) => x.name)).toEqual(['a', 'b']);
    expect(leaders([null, 0], ['a', 'b'], ['A', 'B'])).toEqual([]);
  });
});

describe('fmtGt', () => {
  it('uses one decimal under 10 and whole numbers above', () => {
    expect([fmtGt(0.04), fmtGt(9.84), fmtGt(10.4), fmtGt(434.866)]).toEqual(['0.0', '9.8', '10', '435']);
  });
});
