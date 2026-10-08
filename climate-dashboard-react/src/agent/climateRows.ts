import type { CorrelationGhgCompositionResponse } from '../api/correlationTypes';

// Pure row builders for the Area 2 table widgets, kept apart from the components (a component file exports components only) and tested directly:
// AG Grid renders no cell text in jsdom, so the values cannot be asserted through the rendered table.

/** One year's gases as table rows: name, MtCO₂e (rounded) and share, with a dash for a gas with no value that year (never zero). */
export function singleYearRows(result: CorrelationGhgCompositionResponse): Array<{ gas: string; mtco2e: string; share: string }> {
  return (result.years?.[0]?.values ?? []).map((v) => ({
    gas: v.name,
    mtco2e: v.mtco2e == null ? '—' : Math.round(v.mtco2e).toLocaleString(),
    share: v.share_pct == null ? '—' : `${v.share_pct.toFixed(1)}%`,
  }));
}

/** The sources table: id, coverage years as "a–b", retrieval date, licence; a dash where the pipeline recorded none. */
export function sourceRows(
  sources: Array<{ id: string; coverage?: number[] | null; retrieved_at?: string | null; license?: string | null }>,
): Array<{ source: string; coverage: string; retrieved: string; licence: string }> {
  return sources.map((s) => ({
    source: s.id,
    coverage: Array.isArray(s.coverage) && s.coverage.length === 2 ? `${s.coverage[0]}–${s.coverage[1]}` : '—',
    retrieved: s.retrieved_at ? String(s.retrieved_at).slice(0, 10) : '—',
    licence: s.license ?? '—',
  }));
}

