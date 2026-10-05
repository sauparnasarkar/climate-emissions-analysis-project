import type {
  CorrelationConcentrationResponse,
  CorrelationEmissionsTemperatureResponse,
  CorrelationTemperatureResponse,
  SeriesPoint,
} from '../api/correlationTypes';

// The numbers behind the landing page's "climate signal" banner (Area 2, requirements §2.1): the headline
// temperature-vs-cumulative-CO₂ relationship plus the latest temperature and CO₂ concentration. Every
// figure is read from the correlation API; nothing here is typed in.

export type Era = 'pre1900' | 'y1900_1969' | 'y1970plus';

export interface ScatterPoint {
  year: number;
  /** Cumulative CO₂ since 1850, GtCO₂ (the API gives Mt) */
  gt: number;
  /** °C above the pre-industrial (1850–1900) average */
  temp: number;
  era: Era;
}

export interface ClimateSignal {
  points: ScatterPoint[];
  fit: { slope: number; ciLow: number; ciHigh: number; rSquared: number | null; unit: string; start: number; end: number; nYears: number };
  /** Least-squares line through the points, as two end points in chart units */
  line: { x0: number; y0: number; x1: number; y1: number };
  temperature: { value: number; year: number };
  concentration: { value: number; year: number };
  /** The full annual series behind the two latest values, nulls dropped (for sparklines) */
  series: { concentration: YearValue[]; temperature: YearValue[] };
  /** First year of NOAA's direct measurements; before it the record is the Law Dome ice core */
  spliceYear: number | null;
  /** How the NOAA Mauna Loa record is joined to the Law Dome ice core, as the concentration response documents it; null when it publishes none */
  splice: { year: number; overlapYears: [number, number] | null; gapPpm: number | null; maxAbsOverlapGapPpm: number | null } | null;
  /** Concentration in 1850, the pre-industrial reference for "up x% on 1850" */
  ppm1850: number | null;
  /** Years the pair left out, with no reason text (the baseline card says "None" when it is empty) */
  omittedYears: number[];
  /** The Berkeley Earth file-vintage caveat, while the ~0.1 °C discrepancy is unreconciled (requirements §1.3.1); null once reconciled */
  vintageCaveat: string | null;
}

export interface YearValue {
  year: number;
  value: number;
}

export function yearValues(points: SeriesPoint[]): YearValue[] {
  return points.filter((p): p is SeriesPoint & { value: number } => p.value != null && Number.isFinite(p.value)).map((p) => ({ year: p.year, value: p.value }));
}

export function eraOf(year: number): Era {
  if (year < 1900) return 'pre1900';
  if (year < 1970) return 'y1900_1969';
  return 'y1970plus';
}

/** Ordinary least squares y = intercept + slope·x. Needs at least two distinct x values. */
export function olsFit(xs: number[], ys: number[]): { slope: number; intercept: number } | null {
  const n = xs.length;
  if (n < 2 || ys.length !== n) return null;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let sxx = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    sxx += (xs[i] - mx) ** 2;
    sxy += (xs[i] - mx) * (ys[i] - my);
  }
  if (sxx === 0) return null;
  const slope = sxy / sxx;
  return { slope, intercept: my - slope * mx };
}

/** The most recent point that has a value (the API returns explicit nulls, never zeros). */
export function latestValue(points: SeriesPoint[]): { value: number; year: number } | null {
  for (let i = points.length - 1; i >= 0; i--) {
    const v = points[i].value;
    if (v != null && Number.isFinite(v)) return { value: v, year: points[i].year };
  }
  return null;
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** Null when any required piece is missing, so the banner is left out rather than shown with gaps or zeros. */
export function buildClimateSignal(
  pair: CorrelationEmissionsTemperatureResponse,
  temperature: CorrelationTemperatureResponse,
  concentration: CorrelationConcentrationResponse,
): ClimateSignal | null {
  const slope = num(pair.fit?.slope);
  const ci = Array.isArray(pair.fit?.ci95_hac) ? (pair.fit!.ci95_hac as unknown[]) : [];
  const ciLow = num(ci[0]);
  const ciHigh = num(ci[1]);
  const start = num(pair.fit?.start);
  const end = num(pair.fit?.end);
  const nYears = num(pair.fit?.n_years);
  const temp = latestValue(temperature.points);
  const ppm = latestValue(concentration.points);
  if (slope == null || ciLow == null || ciHigh == null || start == null || end == null || nYears == null || !temp || !ppm || pair.points.length < 2) return null;

  const points: ScatterPoint[] = pair.points.map((p) => ({ year: p.year, gt: p.cumulative_emissions / 1000, temp: p.temperature, era: eraOf(p.year) }));
  const ols = olsFit(points.map((p) => p.gt), points.map((p) => p.temp));
  if (!ols) return null;
  const xs = points.map((p) => p.gt);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  return {
    points,
    fit: {
      slope, ciLow, ciHigh, rSquared: num(pair.fit?.r_squared), unit: typeof pair.fit?.unit === 'string' ? pair.fit.unit : '°C per 1,000 GtCO₂', start, end, nYears,
    },
    line: { x0, y0: ols.intercept + ols.slope * x0, x1, y1: ols.intercept + ols.slope * x1 },
    temperature: temp,
    concentration: ppm,
    series: { concentration: yearValues(concentration.points), temperature: yearValues(temperature.points) },
    spliceYear: num((concentration.details?.splice as Record<string, unknown> | undefined)?.splice_year),
    splice: spliceInfo(concentration.details?.splice),
    ppm1850: yearValues(concentration.points).find((p) => p.year === 1850)?.value ?? null,
    omittedYears: (pair.omitted_years ?? []).map((o) => o.year),
    vintageCaveat: vintageCaveat(pair),
  };
}

function spliceInfo(raw: unknown): ClimateSignal['splice'] {
  const s = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : null;
  const year = num(s?.splice_year);
  if (!s || year === null) return null;
  const ov = Array.isArray(s.overlap_years) ? s.overlap_years.map(num) : [];
  return {
    year,
    overlapYears: ov.length === 2 && ov[0] !== null && ov[1] !== null ? [ov[0], ov[1]] : null,
    gapPpm: num(s.gap_at_splice_ppm),
    maxAbsOverlapGapPpm: num(s.max_abs_overlap_gap_ppm),
  };
}

function vintageCaveat(pair: CorrelationEmissionsTemperatureResponse): string | null {
  const v = pair.source_vintage;
  return v && v.reconciled === false && typeof v.caveat === 'string' && v.caveat ? v.caveat : null;
}

/** "+1.62 °C" -- the sign is explicit because the value is a departure from a reference. */
export function fmtAnomaly(v: number): string {
  return `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)} °C`;
}

/** A "nice" axis step for a 0..max range: 500 for the cumulative-CO₂ axis, 0.5 for °C. */
export function niceTicks(max: number, step: number, min = 0): number[] {
  const ticks: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 1e6) / 1e6 + 0); // + 0 turns -0 into 0
  return ticks;
}
