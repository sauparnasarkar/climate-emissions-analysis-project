import type { CorrelationScenarioTemperatureResponse } from '../api/correlationTypes';

export const PATHWAYS_ANCHOR = 'pathways';

export type PathwayName = 'BAU' | 'Moderate' | 'Aggressive';

export interface PathwayCard {
  name: PathwayName;
  label: string;
  method: string;
  /** Global annual CO₂ (Mt) in the horizon year: covered countries' pathway plus the rest of world held at its last-observed share. */
  emissionsMt: number;
  /** Implied temperature anomaly (°C above 1850–1900) in the horizon year: the anchor plus the slope × the cumulative increment. */
  levelC: number;
  color: string;
}

export interface Pathways {
  /** The horizon year the cards describe. */
  year: number;
  /** First scenario year, the last observed year the pathways start from, and the year the rest of the world's share is held at -- all read from the response. */
  startYear: number;
  lastObservedYear: number;
  restOfWorldYear: number;
  cards: PathwayCard[];
  /** The generated one-line reading, or null when the pathways do not diverge enough for the API to publish one. */
  summary: string | null;
}

const META: Record<PathwayName, { label: string; method: (countries: number | null, startYear: number) => string; color: string }> = {
  BAU: { label: 'Business as usual', method: (n) => `ETS trend, ${n ?? 'all'} covered countries`, color: '#B07A10' },
  Moderate: { label: 'Moderate', method: (_, from) => `−2% a year from ${from}`, color: '#0A6E8C' },
  Aggressive: { label: 'Aggressive', method: (_, from) => `−5% a year from ${from}`, color: '#1D726B' },
};
const ORDER: PathwayName[] = ['BAU', 'Moderate', 'Aggressive'];

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);

/** The Overview's closing "where today's patterns lead" block from /scenario-temperature, or null when the scenario output is not there (the
 * section is then omitted -- never zeros). Every figure is read from the response; only the scenario names' method wording is fixed copy. */
export function buildPathways(resp: CorrelationScenarioTemperatureResponse | null | undefined): Pathways | null {
  if (!resp) return null;
  const rows = (name: PathwayName) => (resp.scenarios?.[name] ?? []).flatMap((r) => (rec(r) ? [rec(r)!] : []));
  const year = Math.max(0, ...ORDER.flatMap((n) => rows(n).map((r) => num(r.year) ?? 0)));
  if (year === 0) return null;
  const startYear = Math.min(...ORDER.flatMap((n) => rows(n).map((r) => num(r.year) ?? Infinity)));
  const lastObservedYear = num(rec(resp.base)?.last_observed_year) ?? startYear - 1;
  const restOfWorldYear = num(rec(rec(resp.assumptions)?.rest_of_world)?.year) ?? lastObservedYear;
  const countries = Array.isArray(resp.covered_countries) ? resp.covered_countries.length || null : null;
  const cards: PathwayCard[] = [];
  for (const name of ORDER) {
    const row = rows(name).find((r) => r.year === year);
    const emissionsMt = num(row?.global_fossil_mt);
    const levelC = num(rec(row?.headline)?.level_c);
    if (emissionsMt === null || levelC === null) return null; // a scenario without its horizon figures: show nothing rather than a partial comparison
    cards.push({ name, label: META[name].label, method: META[name].method(countries, startYear), emissionsMt, levelC, color: META[name].color });
  }
  const facts = rec(resp.spread?.reading_note_facts);
  const ratio = num(facts?.emissions_ratio);
  const gap = num(facts?.gap_end_c);
  const range = Array.isArray(facts?.already_observed_pct_range) ? (facts!.already_observed_pct_range as unknown[]).map(num) : [];
  let summary: string | null = null;
  if (facts && ratio !== null && gap !== null) {
    const observed = range.length === 2 && range[0] !== null && range[1] !== null ? `, because ${Math.round(range[0])}–${Math.round(range[1])}% of the ${year} implied level is warming already observed` : '';
    summary = `By ${year} the pathways diverge ${ratio.toFixed(1)}× in annual emissions, yet their implied temperatures differ by only ${gap.toFixed(2)} °C${observed}.`;
  }
  return { year, startYear, lastObservedYear, restOfWorldYear, cards, summary };
}
