import type { CorrelationCountryShareResponse } from '../api/correlationTypes';
import { SHARE_PALETTE } from './shareBars';

export const COUNTRY_VIEW_ANCHOR = 'country-view';
/** How many countries the picker starts with (the largest cumulative emitters) and allows at once (past ten lines stop being readable). */
export const COUNTRY_VIEW_DEFAULT = 5;
export const COUNTRY_VIEW_MAX = 10;

export interface CountryLine {
  code: string;
  name: string;
  color: string;
  points: Array<{ year: number; share: number }>;
}

export interface CountryLines {
  lines: CountryLine[];
  /** Countries the API answered with no rows for (it says why in `notes`); left out, never drawn as zero */
  missing: Array<{ code: string; name: string }>;
  cumulativeFrom: number | null;
  label: string;
  notes: string[];
}

/** One line per selected country, coloured by its place in the selection, from a `/country-share` series response; null only when the response has no
 * series at all. When every selected country lacks rows, `lines` is empty but `missing` and the API's `notes` are kept so the view can say why. */
export function buildCountryLines(resp: CorrelationCountryShareResponse | null | undefined): CountryLines | null {
  const series = resp?.series ?? [];
  if (!resp || series.length === 0) return null;
  const lines: CountryLine[] = [];
  const missing: Array<{ code: string; name: string }> = [];
  series.forEach((s) => {
    if (s.points.length === 0) missing.push({ code: s.country, name: s.name });
    else lines.push({ code: s.country, name: s.name, color: SHARE_PALETTE[lines.length % SHARE_PALETTE.length], points: s.points.map((p) => ({ year: p.year, share: p.share_pct })) });
  });
  return { lines, missing, cumulativeFrom: resp.cumulative_from, label: resp.label, notes: resp.notes ?? [] };
}

/** The picker's starting selection: the largest cumulative emitters in the all-countries snapshot, which the API returns ranked. */
export function defaultCountries(snapshot: CorrelationCountryShareResponse | null | undefined, n: number = COUNTRY_VIEW_DEFAULT): string[] {
  return (snapshot?.rows ?? []).slice(0, n).map((r) => r.country);
}
