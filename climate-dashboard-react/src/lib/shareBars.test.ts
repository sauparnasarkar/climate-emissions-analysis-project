import { describe, expect, it } from 'vitest';
import { shareResponse } from '../test/shareFixtures';
import { SHARE_PALETTE, buildShareFrames, segmentLabel } from './shareBars';

describe('buildShareFrames', () => {
  const resp = shareResponse([
    ['CHN', 'China', [[2023, 15, 30], [2024, 16, 32]]],
    ['USA', 'United States', [[2023, 24, 13], [2024, 23.5, 12.5]]],
  ]);

  it('orders countries by the last year\'s stock share and fixes a colour per country by that order', () => {
    const f = buildShareFrames(resp)!;
    expect(f.order.map((c) => c.code)).toEqual(['USA', 'CHN']); // although CHN came first in the response
    expect(f.order.map((c) => c.color)).toEqual(SHARE_PALETTE.slice(0, 2));
    expect(f.years).toEqual([2023, 2024]);
    expect(f.stock).toEqual([[24, 15], [23.5, 16]]);
    expect(f.flow).toEqual([[13, 30], [12.5, 32]]);
  });

  it('makes Rest of world what the selected leave of 100', () => {
    const f = buildShareFrames(resp)!;
    expect(f.restStock[1]).toBeCloseTo(60.5);
    expect(f.restFlow![1]).toBeCloseTo(55.5);
    expect(f.signed).toBe(false);
  });

  it('is signed when a published share is negative or the countries add up to more than 100, so the bars are not drawn', () => {
    expect(buildShareFrames(shareResponse([['USA', 'United States', [[2024, 24, -1]]], ['CHN', 'China', [[2024, 16, 10]]]]))!.signed).toBe(true);
    const over = buildShareFrames(shareResponse([['USA', 'United States', [[2024, 60, 60]]], ['CHN', 'China', [[2024, 41, 41]]]]))!;
    expect(over.restStock[0]).toBeCloseTo(-1);
    expect(over.signed).toBe(true);
  });

  it('leaves out a country the API answered with no rows (and says so), instead of showing it as 0', () => {
    const f = buildShareFrames(shareResponse([['USA', 'United States', [[2023, 24, 13], [2024, 23, 12]]], ['TWN', 'Taiwan', []]]))!;
    expect(f.order.map((c) => c.code)).toEqual(['USA']);
    expect(f.missing).toEqual([{ code: 'TWN', name: 'Taiwan' }]);
    expect(buildShareFrames(shareResponse([['TWN', 'Taiwan', []]]))).toBeNull();
  });

  it('treats a year a country has no point for as 0 (it had not started reporting)', () => {
    const f = buildShareFrames(shareResponse([['USA', 'United States', [[2023, 20, 10], [2024, 21, 11]]], ['SSD', 'South Sudan', [[2024, 0.1, 0.2]]]]))!;
    expect(f.stock[0]).toEqual([20, 0]);
  });

  it('covers the requested range from its start through the latest year, even when a country starts reporting later', () => {
    const f = buildShareFrames({ ...shareResponse([['USA', 'United States', [[1972, 20, 10], [1973, 21, 11]]], ['SSD', 'South Sudan', [[1973, 0.1, 0.2]]]]), start_year: 1970 })!;
    expect(f.years).toEqual([1970, 1971, 1972, 1973]);
    expect(f.stock[0]).toEqual([0, 0]); // before either country's first observation
    expect(f.stock[3]).toEqual([21, 0.1]);
  });

  it('prints a remainder within rounding of zero as 0, not -0.0', () => {
    const f = buildShareFrames(shareResponse([['USA', 'United States', [[2024, 60.02, 50]]], ['CHN', 'China', [[2024, 40, 50]]]]))!;
    expect(f.restStock[0]).toBe(0);
    expect(f.signed).toBe(false);
  });

  it('has no flow when the data release predates the annual columns', () => {
    const f = buildShareFrames(shareResponse([['USA', 'United States', [[2023, 20, null], [2024, 21, null]]]]))!;
    expect(f.flow).toBeNull();
    expect(f.restFlow).toBeNull();
    expect(f.restStock[1]).toBeCloseTo(79);
    expect(f.cumulativeFrom).toBe(1750);
  });

  it('is null without any points', () => {
    expect(buildShareFrames(null)).toBeNull();
    expect(buildShareFrames(shareResponse([]))).toBeNull();
    expect(buildShareFrames(shareResponse([['USA', 'United States', []]]))).toBeNull();
  });
});

describe('segmentLabel', () => {
  it('shows code and value when wide, the code when narrow, nothing when too narrow to read', () => {
    expect(segmentLabel('USA', 24.34)).toBe('USA 24.3%');
    expect(segmentLabel('DEU', 5.4)).toBe('DEU');
    expect(segmentLabel('JPN', 2.9)).toBe('');
  });
});
