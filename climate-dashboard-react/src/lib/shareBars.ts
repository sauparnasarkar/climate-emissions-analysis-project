import type { CorrelationCountryShareResponse } from '../api/correlationTypes';

/** The Share section's three measures (ENHANCEMENTS.md decision 63): the (source, gas_scope) combinations /country-share publishes. */
export const SHARE_MEASURES = [
  { id: 'owid_co2', label: 'CO₂ · OWID', source: 'owid_co2', gasScope: 'co2' },
  { id: 'primap_co2', label: 'CO₂ · PRIMAP-hist', source: 'primap_hist', gasScope: 'co2' },
  { id: 'primap_ghg', label: 'All GHGs · PRIMAP-hist', source: 'primap_hist', gasScope: 'total_ghg' },
] as const;
export type ShareMeasureId = (typeof SHARE_MEASURES)[number]['id'];

/** First animation frame (requirements §2.2: the share bars play 1970 → latest). */
export const SHARE_START_YEAR = 1970;
/** Time on each year while playing. */
export const SHARE_STEP_MS = 250;

/** One colour per country, assigned by the fixed order and shared by both bars. Light enough that dark text reads on every segment, in both themes. */
export const SHARE_PALETTE = ['#5FD8F7', '#FFB54D', '#C89CFF', '#7791F8', '#F263F2', '#FF8F6B', '#D7E740', '#5AB4AC', '#EA5B62', '#8BD17C'];

export interface ShareCountry {
  code: string;
  name: string;
  color: string;
}

export interface ShareFrames {
  years: number[];
  /** Fixed for every frame: sorted by the last year's stock share, so segments never swap places while playing. */
  order: ShareCountry[];
  /** [year index][country index] in %, 0 where a country has no point that year. */
  stock: number[][];
  /** Same shape; null when the pipeline output predates the annual columns (decision 60), so the flow bar is omitted. */
  flow: number[][] | null;
  /** Rest of world = what the selected countries leave of 100, per year (exact: the denominator is the national sum). */
  restStock: number[];
  restFlow: number[] | null;
  cumulativeFrom: number | null;
  label: string;
  /** True when any published share is negative (the pipeline records a deviation but still publishes it) or the countries add up to more than
   * 100 %: stacked bars cannot show that honestly, so the view falls back to the table. */
  signed: boolean;
  /** Selected countries the API answered with no rows for this measure/range (it says why in `notes`); they are left out of the bars, never shown as 0. */
  missing: Array<{ code: string; name: string }>;
  notes: string[];
}

// A remainder within rounding of zero is zero (it would otherwise print as "-0.0%"); a real overshoot stays negative and makes the frame `signed`.
const rest = (row: number[]) => {
  const v = 100 - row.reduce((a, b) => a + b, 0);
  return Math.abs(v) < 0.05 ? 0 : v;
};

/** Per-year stock and flow shares for the selected countries from a /country-share series response, or null when it carries no points. */
export function buildShareFrames(resp: CorrelationCountryShareResponse | null | undefined): ShareFrames | null {
  const all = resp?.series ?? [];
  const series = all.filter((s) => s.points.length > 0);
  const missing = all.filter((s) => s.points.length === 0).map((s) => ({ code: s.country, name: s.name }));
  const observed = series.flatMap((s) => s.points.map((p) => p.year));
  if (!resp || series.length === 0 || observed.length === 0) return null;
  // A dense range from the requested start (not the first observation): a country that begins reporting after 1970 would otherwise shorten
  // everyone's range. Years before a country's first observation read as 0 for it.
  const from = Math.min(resp.start_year ?? SHARE_START_YEAR, ...observed);
  const to = Math.max(...observed);
  const years = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  const byYear = series.map((s) => new Map(s.points.map((p) => [p.year, p])));
  const last = years[years.length - 1];
  const idx = series.map((_, i) => i).sort((a, b) => (byYear[b].get(last)?.share_pct ?? 0) - (byYear[a].get(last)?.share_pct ?? 0) || series[a].country.localeCompare(series[b].country));
  const order = idx.map((i, rank) => ({ code: series[i].country, name: series[i].name, color: SHARE_PALETTE[rank % SHARE_PALETTE.length] }));
  const stock = years.map((y) => idx.map((i) => byYear[i].get(y)?.share_pct ?? 0));
  const hasFlow = series.some((s) => s.points.some((p) => p.annual_share_pct != null));
  const flow = hasFlow ? years.map((y) => idx.map((i) => byYear[i].get(y)?.annual_share_pct ?? 0)) : null;
  const restStock = stock.map(rest);
  const restFlow = flow ? flow.map(rest) : null;
  const rows = [...stock, ...(flow ?? [])];
  const signed = rows.some((r) => r.some((v) => v < 0)) || [...restStock, ...(restFlow ?? [])].some((v) => v < -0.05);
  return { years, order, stock, flow, restStock, restFlow, cumulativeFrom: resp.cumulative_from, label: resp.label, signed, missing, notes: resp.notes ?? [] };
}

/** Inline label for a segment of `pct` %: code and value when wide, the code alone when narrow, nothing when too narrow to read. */
export function segmentLabel(code: string, pct: number): string {
  if (pct >= 8) return `${code} ${pct.toFixed(1)}%`;
  if (pct >= 3) return code;
  return '';
}

export const fmtShare = (pct: number) => `${pct.toFixed(1)}%`;
