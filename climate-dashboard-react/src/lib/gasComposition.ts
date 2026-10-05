import type { CorrelationGhgCompositionResponse } from '../api/correlationTypes';
import { SHARE_PALETTE } from './shareBars';

export const GAS_COMPOSITION_ANCHOR = 'gas-composition';

export interface GasInfo {
  id: string;
  name: string;
  /** Short label for a bar segment */
  short: string;
  color: string;
}

export interface Composition {
  years: number[];
  gases: GasInfo[];
  /** MtCO₂e, [gas index][year index] */
  mt: number[][];
  /** Share of the year's included gases in %, [year index][gas index] */
  shares: number[][];
  basis: string;
  units: string;
  /** How far the included gases' sum sits from PRIMAP-hist's own national total, in %, per year (null where not published) */
  residualPct: Array<number | null>;
  /** The API's own reconciliation check across all years: the largest gap and the tolerance it is held to, when published */
  reconciliation: { maxAbsResidualPct: number; tolerancePct: number } | null;
  /** Trailing years the API left out as incomplete (stated beside the chart) */
  excludedIncompleteYears: number[];
  /** The API's caveats that belong beside this chart; licences and sources stay with the methodology */
  caveats: string[];
}

const GAS_STYLE: Record<string, { short: string; color: string }> = {
  co2: { short: 'CO₂', color: '#FFB54D' },
  ch4: { short: 'CH₄', color: '#5AB4AC' },
  n2o: { short: 'N₂O', color: '#C89CFF' },
  fgas: { short: 'F-gas', color: '#EA5B62' },
};

const NEAR_CHART = /^(Excludes|Shares are each|Trailing years)/;
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** The gas composition (requirements §1.3.3) from `/ghg-composition`, or null when it cannot be drawn honestly: no gas list, or fewer than two years in
 * which every gas has a value and a share (a year with a gap is skipped, never filled with zero). */
export function buildComposition(resp: CorrelationGhgCompositionResponse | null | undefined): Composition | null {
  if (!resp) return null;
  const gases: GasInfo[] = resp.gases.flatMap((g, i) => {
    const id = typeof g.id === 'string' ? g.id : null;
    const name = typeof g.name === 'string' ? g.name : null;
    if (!id || !name) return [];
    const style = GAS_STYLE[id] ?? { short: name, color: SHARE_PALETTE[i % SHARE_PALETTE.length] };
    return [{ id, name, ...style }];
  });
  if (gases.length === 0 || gases.length !== resp.gases.length) return null;
  const years: number[] = [];
  const mt: number[][] = gases.map(() => []);
  const shares: number[][] = [];
  const residualPct: Array<number | null> = [];
  for (const y of resp.years) {
    const byGas = new Map(y.values.map((v) => [v.gas, v]));
    const mtRow = gases.map((g) => num(byGas.get(g.id)?.mtco2e));
    const shareRow = gases.map((g) => num(byGas.get(g.id)?.share_pct));
    if (mtRow.some((v) => v === null) || shareRow.some((v) => v === null)) continue;
    years.push(y.year);
    mtRow.forEach((v, i) => mt[i].push(v as number));
    shares.push(shareRow as number[]);
    residualPct.push(num(y.residual_pct));
  }
  if (years.length < 2) return null;
  const maxAbs = num((resp.reconciliation as Record<string, unknown> | null)?.max_abs_residual_pct);
  const tol = num((resp.reconciliation as Record<string, unknown> | null)?.tolerance_pct);
  return {
    years, gases, mt, shares, residualPct, reconciliation: maxAbs !== null && tol !== null ? { maxAbsResidualPct: maxAbs, tolerancePct: tol } : null,
    basis: resp.basis, units: resp.units,
    excludedIncompleteYears: resp.excluded_incomplete_years ?? [],
    caveats: (resp.caveats ?? []).filter((c): c is string => typeof c === 'string' && NEAR_CHART.test(c)),
  };
}
