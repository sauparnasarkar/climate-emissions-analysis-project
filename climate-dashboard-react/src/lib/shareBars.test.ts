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

  it('makes Rest of world what the selected leave of 100, never negative', () => {
    const f = buildShareFrames(resp)!;
    expect(f.restStock[1]).toBeCloseTo(60.5);
    expect(f.restFlow![1]).toBeCloseTo(55.5);
    const over = buildShareFrames(shareResponse([['USA', 'United States', [[2024, 60, 60]]], ['CHN', 'China', [[2024, 41, 41]]]]))!;
    expect(over.restStock[0]).toBe(0);
  });

  it('treats a year a country has no point for as 0 (it had not started reporting)', () => {
    const f = buildShareFrames(shareResponse([['USA', 'United States', [[2023, 20, 10], [2024, 21, 11]]], ['SSD', 'South Sudan', [[2024, 0.1, 0.2]]]]))!;
    expect(f.stock[0]).toEqual([20, 0]);
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
