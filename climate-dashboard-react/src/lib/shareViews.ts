import type { CorrelationCountryShareResponse } from '../api/correlationTypes';
import type { HistoricalCumulativeResponse } from '../api/types';

// The agent's country-share widget draws the dashboard's own cumulative pictures (SPEC.md §5.28, Release 24.6) from the share tool's result, so an answer and the
// Historical Trends / Country Profile pages cannot disagree. The share endpoint's series start at each country's first published year, each on its own; the
// Release 23 builders want one shared year axis, so this lines them up (null where a country has no value yet) and takes the World total for each year from
// the remainder the endpoint publishes beside any OWID series. Pure, so the alignment is unit-tested without rendering a chart.

export const SHARE_VIEWS = ['share_lines', 'cumulative_area', 'share_vs_annual', 'emitted_lines'] as const;
export type ShareView = (typeof SHARE_VIEWS)[number];

/** The colour of a single-country line, as on Country Profile (the chart panel is dark in every theme). */
export const SINGLE_LINE_COLOR = '#ecf0f6';

/**
 * The result on the Release 23 shape (one `years` axis; `cumulative_co2` in Mt; shares in percent; the World's cumulative per year), for `cumulativeAreaSeries`.
 * Null when it cannot be drawn honestly: not OWID (a PRIMAP-hist share has no World total to leave a Rest of world), no World totals, or no points.
 */
/** What a "since YYYY" answer subtracts to draw emissions in the period from zero: each country's cumulative total the year before (by name; absent = it had emitted nothing) and the World's. */
export interface SinceRebase {
  base: Record<string, number>;
  world: number;
}

/** The rebase from the tool's `summary.since`, or null when the answer is not a since-answer or lacks the World base. */
export function sinceRebase(summary: Record<string, unknown> | null | undefined): SinceRebase | null {
  const since = (summary as { since?: { world_base_cumulative_mt?: number; countries?: Array<{ name: string; base_cumulative_mt?: number }> } } | null | undefined)?.since;
  if (!since || typeof since.world_base_cumulative_mt !== 'number') return null;
  return { base: Object.fromEntries((since.countries ?? []).map((c) => [c.name, c.base_cumulative_mt ?? 0])), world: since.world_base_cumulative_mt };
}

export function shareToCumulative(result: CorrelationCountryShareResponse, rebase?: SinceRebase | null): HistoricalCumulativeResponse | null {
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
  const sub = (v: number | null | undefined, base: number): number | null => (v == null ? null : Math.max(0, v - base));
  return {
    years,
    series: series.map((s) => {
      const byYear = new Map(s.points.map((p) => [p.year, p]));
      const base = rebase?.base[s.name] ?? 0;
      return {
        name: s.name,
        cumulative_co2: years.map((y) => sub(byYear.get(y)?.cumulative_mt, base)),
        share_of_world_cumulative: years.map((y) => byYear.get(y)?.share_pct ?? null),
        share_of_world_annual: years.map((y) => byYear.get(y)?.annual_share_pct ?? null),
      };
    }),
    world_cumulative_co2: years.map((y) => sub(world.get(y), rebase?.world ?? 0)),
  };
}

/**
 * One line per country of what it has emitted in the period so far, in Gt (the lifetime total minus the total the year before the period, never below zero): the since-answer
 * chart for a source with no World total to leave a Rest of world (PRIMAP-hist). Any source; null without points or without the base values.
 */
export function sinceEmittedLines(result: CorrelationCountryShareResponse, rebase: SinceRebase | null): Array<{ name: string; years: number[]; gt: number[] }> | null {
  const series = (result.series ?? []).filter((s) => s.points.length > 0);
  if (!rebase || series.length === 0) return null;
  return series.map((s) => ({ name: s.name, years: s.points.map((p) => p.year), gt: s.points.map((p) => Math.max(0, p.cumulative_mt - (rebase.base[s.name] ?? 0)) / 1000) }));
}

/** The two lines of the single-country comparison: share of everything emitted so far (solid) against share of each year's emissions (dotted). Null without an annual share. */
export function shareVsAnnualLines(result: CorrelationCountryShareResponse): { name: string; years: number[]; cumulative: number[]; annual: Array<number | null> } | null {
  const s = (result.series ?? [])[0];
  if (!s || s.points.length === 0 || !s.points.some((p) => p.annual_share_pct != null)) return null;
  return { name: s.name, years: s.points.map((p) => p.year), cumulative: s.points.map((p) => p.share_pct), annual: s.points.map((p) => p.annual_share_pct) };
}
