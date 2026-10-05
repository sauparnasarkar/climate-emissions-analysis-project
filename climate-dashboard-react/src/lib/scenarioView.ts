import type { CorrelationEmissionsTemperatureResponse, CorrelationScenarioTemperatureResponse } from '../api/correlationTypes';
import type { YearValue } from './climateSignal';
import { buildPathways, type PathwayName } from './pathways';

export const SCENARIOS_ANCHOR = 'scenarios';

export interface PathwayLine {
  name: PathwayName;
  label: string;
  color: string;
  method: string;
  /** Global annual CO₂ in GtCO₂, from the first scenario year to the horizon */
  emissions: YearValue[];
  /** Implied temperature anomaly in °C above 1850–1900 */
  temperature: YearValue[];
}

export interface ScenarioView {
  startYear: number;
  lastObservedYear: number;
  horizon: number;
  pathways: PathwayLine[];
  /** Observed world fossil + cement CO₂ in GtCO₂ a year (the pathways' own basis), a decade up to the last observed year; empty when unavailable */
  observedEmissions: YearValue[];
  observedTemperature: YearValue[];
  observedMean5y: YearValue[];
  /** The anchor the implied temperatures start from: the trailing 5-year mean at the last observed year */
  anchor: { year: number; value: number } | null;
  /** The API's own generated reading of the output, verbatim; null when it published none (the pathways do not diverge enough) */
  readingNote: string | null;
  /** The API's required labels for scenario output (requirements §1.3.5) */
  labels: string[];
  /** The assumptions behind the numbers, as the API states them */
  assumptions: { slope: number | null; slopeLabel: string | null; slopeUnit: string | null; restOfWorldPct: number | null; restOfWorldYear: number | null; landUseGt: number | null; landUseWindow: [number, number] | null };
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const HISTORY_YEARS = 10;

/** World fossil + cement CO₂ per year (Mt): the year-to-year step of the cumulative series, which is OWID's World total (international aviation and shipping
 * included) -- the same basis the scenario pathways are built on. */
function annualFromCumulative(pair: CorrelationEmissionsTemperatureResponse | null | undefined): YearValue[] {
  const pts = pair?.points ?? [];
  const out: YearValue[] = [];
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].year === pts[i - 1].year + 1) out.push({ year: pts[i].year, value: pts[i].cumulative_emissions - pts[i - 1].cumulative_emissions });
  }
  return out;
}

/** The module's scenario section from `/scenario-temperature`, with the observed history it continues from; null when the scenario output is not usable (the
 * section is then omitted). Observed pieces that are missing are left empty, never zero. */
export function buildScenarioView(
  resp: CorrelationScenarioTemperatureResponse | null | undefined,
  fossil: CorrelationEmissionsTemperatureResponse | null | undefined,
  temperature: YearValue[],
  mean5y: YearValue[],
): ScenarioView | null {
  const pathways = buildPathways(resp);
  if (!resp || !pathways) return null;
  const { startYear, lastObservedYear, year: horizon } = pathways;
  const lines: PathwayLine[] = pathways.cards.map((card) => {
    const rows = (resp.scenarios[card.name] ?? []).flatMap((r) => (rec(r) ? [rec(r)!] : []));
    const emissions: YearValue[] = [];
    const temp: YearValue[] = [];
    for (const r of rows) {
      const year = num(r.year);
      const mt = num(r.global_fossil_mt);
      const level = num(rec(r.headline)?.level_c);
      if (year === null) continue;
      if (mt !== null) emissions.push({ year, value: mt / 1000 });
      if (level !== null) temp.push({ year, value: level });
    }
    return { name: card.name, label: card.label, color: card.color, method: card.method, emissions, temperature: temp };
  });
  const from = lastObservedYear - HISTORY_YEARS + 1;
  const anchorValue = num(rec(rec(resp.base)?.anchor)?.value_c);
  const rest = rec(rec(resp.assumptions)?.rest_of_world);
  const land = rec(rec(resp.assumptions)?.land_use);
  const slope = rec(rec(resp.assumptions)?.slope);
  const slopeHeadline = rec(slope?.headline);
  const win = Array.isArray(land?.window) ? (land!.window as unknown[]).map(num) : [];
  const note = typeof resp.reading_note === 'string' && resp.reading_note.trim() ? resp.reading_note : null;
  const restShare = num(rest?.share);
  const landMt = num(land?.mt_per_year);
  return {
    startYear, lastObservedYear, horizon, pathways: lines,
    observedEmissions: annualFromCumulative(fossil).filter((p) => p.year >= from && p.year <= lastObservedYear).map((p) => ({ year: p.year, value: p.value / 1000 })),
    observedTemperature: temperature.filter((p) => p.year >= from && p.year <= lastObservedYear),
    observedMean5y: mean5y.filter((p) => p.year >= from && p.year <= lastObservedYear),
    anchor: anchorValue !== null ? { year: lastObservedYear, value: anchorValue } : null,
    readingNote: note,
    labels: (resp.labels ?? []).filter((l): l is string => typeof l === 'string' && l.length > 0),
    assumptions: {
      slope: num(slopeHeadline?.slope),
      slopeLabel: typeof slopeHeadline?.label === 'string' ? slopeHeadline.label : null,
      slopeUnit: typeof slope?.unit === 'string' ? slope.unit : null,
      restOfWorldPct: restShare !== null ? restShare * 100 : null,
      restOfWorldYear: num(rest?.year),
      landUseGt: landMt !== null ? landMt / 1000 : null,
      landUseWindow: win.length === 2 && win[0] !== null && win[1] !== null ? [win[0], win[1]] : null,
    },
  };
}
