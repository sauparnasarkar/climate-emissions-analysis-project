import type { CorrelationCountryShareResponse } from '../api/correlationTypes';
import type { WorldMapTimeSeries } from '../api/types';

/**
 * Cumulative CO₂ per country per year for the map's Cumulative mode (requirements §2.6, design 3a): the cumulative at the last year
 * BEFORE the series (a snapshot from /api/correlation/country-share, Mt) plus the running sum of the annual values the map already
 * holds. A year missing from a country's record counts as zero, exactly as the pipeline does, so this equals the pipeline's own
 * cumulative at every year (checked against the API: relative difference ~1e-16). Returns GtCO₂, `[yearIdx][countryIdx]`.
 */
export function buildCumulative(series: WorldMapTimeSeries, baseMtByIso: Record<string, number>): Array<Array<number | null>> {
  const running = series.iso_codes.map((iso) => baseMtByIso[iso] ?? 0);
  return series.values.map((row) => {
    return row.map((v, i) => {
      running[i] += v ?? 0;
      // Nothing emitted yet (no earlier history and nothing so far) is "no data", not a zero: it draws grey, like a country that never
      // reports, and keeps the colour axis (logarithmic) free of zeros.
      return running[i] > 0 ? running[i] / 1000 : null;
    });
  });
}

/** The smallest positive and the largest value anywhere in a matrix: the fixed range of a log-scaled colour axis (zero has no log). */
export function positiveRange(matrix: ReadonlyArray<ReadonlyArray<number | null>>): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const row of matrix) {
    for (const v of row) {
      if (v == null) continue;
      if (v > 0 && v < min) min = v;
      if (v > max) max = v;
    }
  }
  return [Number.isFinite(min) ? min : 0, Number.isFinite(max) ? max : 0];
}

export interface Leader {
  name: string;
  iso: string;
  value: number;
  /** The country's share of the row's total, % */
  sharePct: number;
}

/** The `k` largest values in one year's row, with each one's share of the row total. Missing and non-positive values are skipped. */
export function leaders(row: ReadonlyArray<number | null | undefined>, names: string[], isos: string[], k = 5): Leader[] {
  let total = 0;
  const entries: Array<{ i: number; value: number }> = [];
  row.forEach((v, i) => {
    if (v == null || !(v > 0)) return;
    total += v;
    entries.push({ i, value: v });
  });
  return entries
    .sort((a, b) => b.value - a.value || a.i - b.i)
    .slice(0, k)
    .map(({ i, value }) => ({ name: names[i], iso: isos[i], value, sharePct: total ? (value / total) * 100 : 0 }));
}

/** GtCO₂ for display: one decimal below 10, whole numbers above ("0.4", "9.8", "435"). */
export function fmtGt(v: number): string {
  return v < 10 ? v.toFixed(1) : Math.round(v).toLocaleString('en-US');
}

export interface CumulativeBase {
  /** Cumulative CO₂ in Mt at `year`, by ISO3 country */
  byIso: Record<string, number>;
  /** First year the cumulative counts from (the API's `cumulative_from`); null if it did not say */
  from: number | null;
}

/**
 * The base for Cumulative mode from an all-countries snapshot at `year`, or null when the snapshot cannot be trusted as one.
 * /country-share answers a year outside its coverage with 200 and `rows: []` (a note, not an error), and an empty base would silently
 * drop everything emitted before the map's range from every displayed total -- so an empty snapshot, a response for a different year,
 * or a year outside the published coverage is "unavailable" and the toggle stays on Absolute.
 */
export function cumulativeBaseFrom(snapshot: CorrelationCountryShareResponse | null | undefined, year: number): CumulativeBase | null {
  if (!snapshot || snapshot.mode !== 'ranking' || snapshot.limit !== null || snapshot.year !== year || snapshot.rows.length === 0) return null;
  const [lo, hi] = snapshot.coverage ?? [];
  if (lo != null && hi != null && (year < lo || year > hi)) return null;
  return { byIso: Object.fromEntries(snapshot.rows.map((r) => [r.country, r.cumulative_mt])), from: snapshot.cumulative_from };
}
