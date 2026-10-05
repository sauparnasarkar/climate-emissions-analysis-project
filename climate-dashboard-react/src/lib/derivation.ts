import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';

export const DERIVATION_ANCHOR = 'derivation';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const list = (v: unknown): Record<string, unknown>[] => (Array.isArray(v) ? v.flatMap((x) => (rec(x) ? [rec(x)!] : [])) : []);
const pair = (v: unknown): [number, number] | null => {
  const a = Array.isArray(v) ? v.map(num) : [];
  return a.length === 2 && a[0] !== null && a[1] !== null ? [a[0], a[1]] : null;
};

export interface Regression {
  label: string;
  unit: string;
  xName: string;
  xDescription: string | null;
  yName: string;
  yDescription: string | null;
  method: string | null;
  methodology: string | null;
  start: number;
  end: number;
  n: number;
  slope: number;
  rSquared: number | null;
}
export interface Uncertainty {
  seOls: number | null;
  seHac: number | null;
  maxlags: number | null;
  lag1: number | null;
  durbinWatson: number | null;
  /** The API's own statement of how the lag length and the interval are chosen */
  rule: string | null;
  sensitivity: Array<{ maxlags: number; seHac: number | null; ciLow: number; ciHigh: number }>;
}
export interface Sensitivity {
  landUseScale: Array<{ scale: number; slope: number }>;
  weightScan: { definition: string | null; note: string | null; rows: Array<{ weight: number; slope: number; rSquared: number | null; holdoutRmse: number | null }>; split: number | null } | null;
}
export interface Stability {
  method: string | null;
  seed: number | null;
  resamples: number | null;
  bootstrap: { blockYears: number; low: number; high: number; median: number | null } | null;
  hac: [number, number] | null;
  blockSensitivity: Array<{ blockYears: number; low: number; high: number; median: number | null }>;
  holdouts: Array<{ split: number; train: [number, number] | null; test: [number, number] | null; trainSlope: number | null; rmse: number; baselineRmse: number | null }>;
  summary: string | null;
  note: string | null;
}
export interface Ar6 {
  best: number;
  low: number;
  high: number;
  source: string | null;
  note: string | null;
  within: boolean | null;
  overlaps: boolean | null;
  ratio: number | null;
}
export interface AttributionEntry {
  series: string | null;
  source: string;
  license: string | null;
  citations: string[];
  requiredFormat: string | null;
  note: string | null;
}
export interface Derivation {
  regression: Regression;
  uncertainty: Uncertainty | null;
  sensitivity: Sensitivity | null;
  stability: Stability | null;
  ar6: Ar6 | null;
  attribution: AttributionEntry[];
}

/** "How this number was derived" (requirements §1.3.1; ENHANCEMENTS.md decision 67, part 9b), read from the headline response: the fit, its `fit_context`
 * (uncertainty, sensitivity, stability, the AR6 comparison) and its attribution. Every part is optional except the regression itself, and a part whose
 * numbers are incomplete is left out whole rather than shown with blanks. The fit-quality note the response also carries is not read here: its wording
 * waits for the owner (decision 41). */
export function buildDerivation(resp: CorrelationEmissionsTemperatureResponse | null | undefined): Derivation | null {
  const fit = rec(resp?.fit);
  const ctx = rec(resp?.fit_context);
  if (!resp || !fit) return null;
  const slope = num(fit.slope);
  const start = num(fit.start);
  const end = num(fit.end);
  const n = num(fit.n_years) ?? num((rec(ctx?.fit) ?? {}).n);
  const label = str(fit.label);
  const unit = str(fit.unit);
  if (slope === null || start === null || end === null || n === null || !label || !unit) return null;
  const full = rec(ctx?.fit);
  const seOls = num(full?.se_ols);
  const seHac = num(full?.se_hac);
  const maxlags = num(full?.maxlags) ?? num(fit.maxlags);
  const lag1 = num(full?.residual_lag1_autocorrelation);
  const durbinWatson = num(full?.durbin_watson);
  const rule = str(full?.rule);

  const hac = list(ctx?.hac_sensitivity).flatMap((r) => {
    const ci = pair(r.ci95_hac);
    const maxlags = num(r.maxlags);
    return ci && maxlags !== null ? [{ maxlags, seHac: num(r.se_hac), ciLow: ci[0], ciHigh: ci[1] }] : [];
  });
  const hasUncertaintyData =
    (seOls !== null && seHac !== null) ||
    rule !== null ||
    lag1 !== null ||
    durbinWatson !== null ||
    hac.length > 0;
  const uncertainty: Uncertainty | null = hasUncertaintyData
    ? { seOls, seHac, maxlags, lag1, durbinWatson, rule, sensitivity: hac }
    : null;

  const scale = list(ctx?.land_use_sensitivity).flatMap((r) => (num(r.land_use_scale) !== null && num(r.slope) !== null ? [{ scale: num(r.land_use_scale)!, slope: num(r.slope)! }] : []));
  const scan = rec(ctx?.land_use_weight_scan);
  const scanRows = list(scan?.weights).flatMap((r) => (num(r.land_use_weight) !== null && num(r.slope) !== null ? [{ weight: num(r.land_use_weight)!, slope: num(r.slope)!, rSquared: num(r.r_squared), holdoutRmse: num(r.holdout_rmse_c), split: num(r.holdout_split_year) }] : []));
  const sensitivity: Sensitivity | null = scale.length || scanRows.length
    ? { landUseScale: scale, weightScan: scanRows.length ? { definition: str(scan?.definition), note: str(scan?.note), rows: scanRows, split: scanRows[0]?.split ?? null } : null }
    : null;

  const st = rec(ctx?.stability);
  const bootRec = rec(st?.bootstrap);
  const bootCi = pair(bootRec?.ci95);
  const holdouts = list(st?.holdouts).flatMap((h) => (num(h.split_year) !== null && num(h.rmse_c) !== null ? [{ split: num(h.split_year)!, train: pair(h.train_range), test: pair(h.test_range), trainSlope: num(h.train_slope), rmse: num(h.rmse_c)!, baselineRmse: num(h.baseline_rmse_train_mean_c) }] : []));
  const blocks = list(st?.block_length_sensitivity).flatMap((b) => {
    const ci = pair(b.ci95);
    return ci && num(b.block_years) !== null ? [{ blockYears: num(b.block_years)!, low: ci[0], high: ci[1], median: num(b.median) }] : [];
  });
  const stability: Stability | null = st && (bootCi || holdouts.length || blocks.length)
    ? {
        method: str(st.method), seed: num(st.seed), resamples: num(st.resamples),
        bootstrap: bootCi && num(bootRec?.block_years) !== null ? { blockYears: num(bootRec!.block_years)!, low: bootCi[0], high: bootCi[1], median: num(bootRec?.median) } : null,
        hac: pair(st.hac_ci95), blockSensitivity: blocks, holdouts, summary: str(st.summary), note: str(st.note),
      }
    : null;

  const ref = rec(ctx?.ar6_reference);
  const vs = rec(ctx?.vs_ar6);
  const range = pair(ref?.very_likely_range);
  const best = num(ref?.best_estimate);
  const ar6: Ar6 | null = ref && range && best !== null
    ? { best, low: range[0], high: range[1], source: str(ref.source), note: str(ref.note), within: typeof vs?.within_very_likely_range === 'boolean' ? vs.within_very_likely_range : null, overlaps: typeof vs?.ci_overlaps_range === 'boolean' ? vs.ci_overlaps_range : null, ratio: num(vs?.ratio_to_best_estimate) }
    : null;

  const attribution = (resp.attribution ?? []).flatMap((a): AttributionEntry[] => {
    const source = str(a.source);
    return source
      ? [{ series: str(a.series), source, license: str(a.license), citations: Array.isArray(a.citations) ? a.citations.filter((c): c is string => typeof c === 'string') : [], requiredFormat: str(a.required_citation_format), note: str(a.land_use_license_note) }]
      : [];
  });

  return {
    regression: { label, unit, xName: resp.x.name, xDescription: resp.x.description ?? null, yName: resp.y.name, yDescription: resp.y.description ?? null, method: str(ctx?.method), methodology: str(ctx?.methodology), start, end, n, slope, rSquared: num(fit.r_squared) },
    uncertainty, sensitivity, stability, ar6, attribution,
  };
}
