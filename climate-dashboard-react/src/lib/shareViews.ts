import type { CorrelationCountryShareResponse } from '../api/correlationTypes';
import type { HistoricalCumulativeResponse } from '../api/types';

// The agent's country-share widget draws the dashboard's own cumulative pictures (SPEC.md §5.28, Release 24.6) from the share tool's result, so an answer and the
// Historical Trends / Country Profile pages cannot disagree. The share endpoint's series start at each country's first published year, each on its own; the
// Release 23 builders want one shared year axis, so this lines them up (null where a country has no value yet) and takes the World total for each year from
// the remainder the endpoint publishes beside any OWID series. Pure, so the alignment is unit-tested without rendering a chart.

export const SHARE_VIEWS = ['share_lines', 'cumulative_area', 'share_vs_annual'] as const;
export type ShareView = (typeof SHARE_VIEWS)[number];

/** The colour of a single-country line, as on Country Profile (the chart panel is dark in every theme). */
export const SINGLE_LINE_COLOR = '#ecf0f6';

/**
 * The result on the Release 23 shape (one `years` axis; `cumulative_co2` in Mt; shares in percent; the World's cumulative per year), for `cumulativeAreaSeries`.
 * Null when it cannot be drawn honestly: not OWID (a PRIMAP-hist share has no World total to leave a Rest of world), no World totals, or no points.
 */
export function shareToCumulative(result: CorrelationCountryShareResponse): HistoricalCumulativeResponse | null {
  const series = result.series ?? [];
  const remainder = result.remainder_series ?? [];
  if (result.source !== 'owid_co2' || series.length === 0 || remainder.length === 0) return null;
  const pointYears = series.flatMap((s) => s.points.map((p) => p.year));
  if (pointYears.length === 0) return null;
  const lo = Math.min(...pointYears);
  const hi = Math.max(...pointYears);
  const world = new Map(remainder.map((r) => [r.year, r.world_cumulative_mt]));
  const years = [...world.keys()].filter((y) => y >= lo && y <= hi).sort((a, b) => a - b);
  if (years.length === 0) return null;
  return {
    years,
    series: series.map((s) => {
      const byYear = new Map(s.points.map((p) => [p.year, p]));
      return {
        name: s.name,
        cumulative_co2: years.map((y) => byYear.get(y)?.cumulative_mt ?? null),
        share_of_world_cumulative: years.map((y) => byYear.get(y)?.share_pct ?? null),
        share_of_world_annual: years.map((y) => byYear.get(y)?.annual_share_pct ?? null),
      };
    }),
    world_cumulative_co2: years.map((y) => world.get(y) ?? null),
  };
}

/** The two lines of the single-country comparison: share of everything emitted so far (solid) against share of each year's emissions (dotted). Null without an annual share. */
export function shareVsAnnualLines(result: CorrelationCountryShareResponse): { name: string; years: number[]; cumulative: number[]; annual: Array<number | null> } | null {
  const s = (result.series ?? [])[0];
  if (!s || s.points.length === 0 || !s.points.some((p) => p.annual_share_pct != null)) return null;
  return { name: s.name, years: s.points.map((p) => p.year), cumulative: s.points.map((p) => p.share_pct), annual: s.points.map((p) => p.annual_share_pct) };
}
