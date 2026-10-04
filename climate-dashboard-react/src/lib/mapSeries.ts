import type { WorldMapTimeSeries } from '../api/types';

/** The series restricted to `fromYear` onward (the 1970 globe payload → the 1990 view the rest of the landing page uses).
 * `value_range` is recomputed for the kept years, with the same rule as the API: the minimum excludes exact zero (it feeds
 * a log-scaled colour axis). Returns the input unchanged when it already starts at `fromYear`. */
export function sliceMapSeries(series: WorldMapTimeSeries, fromYear: number): WorldMapTimeSeries {
  const start = series.years.findIndex((y) => y >= fromYear);
  if (start <= 0) return series;
  const years = series.years.slice(start);
  const values = series.values.slice(start);
  let min = Infinity;
  let max = -Infinity;
  for (const row of values) {
    for (const v of row) {
      if (v == null) continue;
      if (v > 0 && v < min) min = v;
      if (v > max) max = v;
    }
  }
  return { ...series, years, values, value_range: [Number.isFinite(min) ? min : series.value_range[0], Number.isFinite(max) ? max : series.value_range[1]] };
}

/** World total per year: the sum of every country's value (nulls are missing, not zero). Parallel to `series.years`.
 * Equals the Overview's "All Countries" total, which sums the same 218 ISO-coded countries. */
export function worldTotals(series: WorldMapTimeSeries): number[] {
  return series.values.map((row) => row.reduce<number>((a, v) => a + (v ?? 0), 0));
}
