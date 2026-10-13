import { describe, expect, it } from 'vitest';
import type { CorrelationCountryShareResponse } from '../api/correlationTypes';
import { cumulativeAreaSeries } from './historicalCumulative';
import { shareToCumulative, shareVsAnnualLines } from './shareViews';

const pt = (year: number, cumulative_mt: number, share_pct: number, annual_share_pct: number | null = null) => ({ year, cumulative_mt, share_pct, annual_mt: null, annual_share_pct });
const rem = (year: number, world: number) => ({ year, world_cumulative_mt: world, world_annual_mt: 1, cumulative_mt: 0, share_pct: 0, annual_mt: null, annual_share_pct: null, international_transport_cumulative_mt: null, international_transport_annual_mt: null });

function result(over: Partial<CorrelationCountryShareResponse> = {}): CorrelationCountryShareResponse {
  return {
    source: 'owid_co2', mode: 'series', rows: [],
    series: [
      { country: 'CHN', name: 'China', points: [pt(1998, 100, 5, 8), pt(1999, 110, 5.5, 9), pt(2000, 125, 6, 10)] },
      { country: 'IND', name: 'India', points: [pt(1999, 40, 2, 4), pt(2000, 45, 2.2, 4.5)] }, // starts a year later
    ],
    remainder_series: [rem(1997, 1000), rem(1998, 1500), rem(1999, 1600), rem(2000, 1700), rem(2001, 1800)],
    ...over,
  } as unknown as CorrelationCountryShareResponse;
}

describe('shareToCumulative', () => {
  it("puts every country on one year axis, null before a country's first year, within the years the series cover", () => {
    const d = shareToCumulative(result())!;
    expect(d.years).toEqual([1998, 1999, 2000]); // the World totals of 1997 and 2001 are outside every series' range
    expect(d.series[0].cumulative_co2).toEqual([100, 110, 125]);
    expect(d.series[1].cumulative_co2).toEqual([null, 40, 45]); // India has no value in 1998
    expect(d.series[1].share_of_world_cumulative).toEqual([null, 2, 2.2]);
    expect(d.series[1].share_of_world_annual).toEqual([null, 4, 4.5]);
    expect(d.world_cumulative_co2).toEqual([1500, 1600, 1700]);
  });

  it('feeds the Release 23 stacked-area builder: Gt, largest first, and Rest of world is the World minus the countries shown', () => {
    const area = cumulativeAreaSeries(shareToCumulative(result())!, ['#aaa', '#bbb']);
    expect(area.map((s) => s.name)).toEqual(['China', 'India', 'Rest of world']);
    expect(area[0].y).toEqual([0.1, 0.11, 0.125]); // Mt to Gt
    expect(area[1].y).toEqual([0, 0.04, 0.045]); // not yet emitting: adds nothing to the stack
    expect(area[2].y[2]).toBeCloseTo((1700 - 125 - 45) / 1000); // 1.53 Gt
  });

  it('is null when it cannot be drawn honestly: PRIMAP-hist (no World total), no World totals, no points', () => {
    expect(shareToCumulative(result({ source: 'primap_hist', remainder_series: [] }))).toBeNull();
    expect(shareToCumulative(result({ remainder_series: [] }))).toBeNull();
    expect(shareToCumulative(result({ remainder_series: undefined }))).toBeNull();
    expect(shareToCumulative(result({ series: [{ country: 'CHN', name: 'China', points: [] }] }))).toBeNull();
    expect(shareToCumulative(result({ series: [] }))).toBeNull();
  });
});

describe('shareVsAnnualLines', () => {
  it("is the first country's share of the cumulative total against its share of each year, on its own years", () => {
    const l = shareVsAnnualLines(result())!;
    expect(l).toEqual({ name: 'China', years: [1998, 1999, 2000], cumulative: [5, 5.5, 6], annual: [8, 9, 10] });
  });

  it('is null without any annual share or points', () => {
    expect(shareVsAnnualLines(result({ series: [{ country: 'CHN', name: 'China', points: [pt(2000, 1, 1, null)] }] } as never))).toBeNull();
    expect(shareVsAnnualLines(result({ series: [] }))).toBeNull();
  });
});
