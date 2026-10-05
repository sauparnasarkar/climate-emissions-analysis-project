import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import { eraOf, olsFit, type ScatterPoint } from './climateSignal';

export const ALL_GAS_ANCHOR = 'recent-all-gas';

export interface AllGas {
  points: ScatterPoint[];
  line: { x0: number; y0: number; x1: number; y1: number };
  slope: number;
  ciLow: number;
  ciHigh: number;
  rSquared: number;
  start: number;
  end: number;
  nYears: number;
  /** "°C per 1,000 GtCO2e" as the API words it (never a frontend-authored fallback) */
  unit: string;
  /** The API's name for this fit ("Recent all-gas relationship: …") */
  label: string;
  xName: string;
  xDescription: string | null;
  /** Moving-block bootstrap 95% interval for the slope and its block length, when published (distinct from the Newey–West interval) */
  bootstrap: { low: number; high: number; blockYears: number } | null;
  /** The API's own plain-language reading of how stable the estimate is */
  stabilitySummary: string | null;
  /** Years the pair left out */
  omittedYears: number[];
  /** The API's caveats for this view, in its order */
  caveats: string[];
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);

/** The recent all-gas relationship (PRIMAP-hist, 1970 onward; requirements §1.3.1, decision 35) from `/emissions-temperature?source=primap_ghg`, or null
 * when the fit or the points are missing so the view is left out rather than shown with gaps. Never called TCRE and never compared with the AR6 range. */
export function buildAllGas(resp: CorrelationEmissionsTemperatureResponse | null | undefined): AllGas | null {
  if (!resp || resp.source !== 'primap_ghg' || !resp.fit || resp.points.length < 2) return null;
  const slope = num(resp.fit.slope);
  const ci = Array.isArray(resp.fit.ci95_hac) ? (resp.fit.ci95_hac as unknown[]) : [];
  const ciLow = num(ci[0]);
  const ciHigh = num(ci[1]);
  const start = num(resp.fit.start);
  const end = num(resp.fit.end);
  const nYears = num(resp.fit.n_years);
  const rSquared = num(resp.fit.r_squared);
  const unit = typeof resp.fit.unit === 'string' && resp.fit.unit ? resp.fit.unit : null;
  const label = typeof resp.fit.label === 'string' && resp.fit.label ? resp.fit.label : null;
  // Every figure and the fit's own wording are the API's: a fit missing any of them is incomplete and the view is left out, not filled in.
  if (slope === null || ciLow === null || ciHigh === null || start === null || end === null || nYears === null || rSquared === null || unit === null || label === null) return null;
  const points: ScatterPoint[] = resp.points.map((p) => ({ year: p.year, gt: p.cumulative_emissions / 1000, temp: p.temperature, era: eraOf(p.year) }));
  const ols = olsFit(points.map((p) => p.gt), points.map((p) => p.temp));
  if (!ols) return null;
  const xs = points.map((p) => p.gt);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const stability = rec(resp.fit_context?.stability);
  const boot = rec(stability?.bootstrap);
  const bootCi = Array.isArray(boot?.ci95) ? (boot!.ci95 as unknown[]) : [];
  const bootLow = num(bootCi[0]);
  const bootHigh = num(bootCi[1]);
  const blockYears = num(boot?.block_years);
  return {
    points,
    line: { x0, y0: ols.intercept + ols.slope * x0, x1, y1: ols.intercept + ols.slope * x1 },
    slope, ciLow, ciHigh, rSquared, start, end, nYears, unit, label,
    xName: resp.x.name,
    xDescription: resp.x.description ?? null,
    bootstrap: bootLow !== null && bootHigh !== null && blockYears !== null ? { low: bootLow, high: bootHigh, blockYears } : null,
    stabilitySummary: typeof stability?.summary === 'string' && stability.summary ? stability.summary : null,
    omittedYears: (resp.omitted_years ?? []).map((o) => o.year),
    caveats: (resp.caveats ?? []).filter((c): c is string => typeof c === 'string'),
  };
}
