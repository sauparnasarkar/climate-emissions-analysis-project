import type { CorrelationMetaResponse } from '../api/correlationTypes';

export const METHODOLOGY_ANCHOR = 'methodology';

export interface SourceRow {
  name: string;
  /** What the platform uses it for: the only fixed copy in the sources table */
  usedFor: string | null;
  coverage: string | null;
  /** The release/publication date the API gives, or the retrieval date, labelled as which */
  vintage: string | null;
  /** The licence wording as the API states it (more than one when a source's datasets differ) */
  licences: string[];
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const day = (iso: string) => iso.slice(0, 10);

// Short "used for" phrases keyed by dataset id; everything else in the table is the API's. The annual and monthly NOAA datasets are separate sources
// with separate uses: only the annual one is joined to the Law Dome record (the splice year is the API's, shown in the derivation); the monthly one supplies the latest reading.
const USED_FOR: Array<[matches: (id: string) => boolean, usedFor: string]> = [
  [(id) => id.startsWith('owid'), 'Country CO₂, the World row, the long-run relationship'],
  [(id) => id.startsWith('primap'), 'All-gas view, gas composition, country shares'],
  [(id) => id.startsWith('temperature'), 'Global temperature anomaly'],
  [(id) => id === 'co2_concentration_annual', 'Atmospheric CO₂ (joined to the ice-core record)'],
  [(id) => id === 'co2_concentration_monthly_mlo', 'Latest CO₂ reading (Mauna Loa monthly)'],
];

/** A vintage with the date it is compared by (ISO, so the string order is the time order) and the label shown. */
interface Vintage {
  date: string;
  label: string;
}

function vintageOf(entry: Record<string, unknown>): Vintage | null {
  const release = rec(entry.source_release);
  const published = str(release?.published);
  if (published) return { date: day(published), label: `published ${day(published)}${str(release?.version) ? ` (${str(release?.version)})` : ''}` };
  const modified = str(release?.http_last_modified) ?? str(release?.noaa_last_modified);
  if (modified) return { date: day(modified), label: `file of ${day(modified)}` };
  const retrieved = str(entry.retrieved_at);
  return retrieved ? { date: day(retrieved), label: `retrieved ${day(retrieved)}` } : null;
}

/** The sources table from `/meta.sources`: dataset-level entries merged by source name, derived metadata (the country crosswalk) left out because it is
 * not a data source. Coverage spans the merged datasets; the vintage is the most recent the API states; licences are the API's own wording. */
export function buildSources(meta: CorrelationMetaResponse | null | undefined): SourceRow[] {
  const groups = new Map<string, Array<Record<string, unknown>>>();
  for (const raw of meta?.sources ?? []) {
    const e = rec(raw);
    const name = str(e?.source);
    if (!e || !name || /^derived/i.test(str(e.license) ?? '')) continue;
    groups.set(name, [...(groups.get(name) ?? []), e]);
  }
  return [...groups.entries()].map(([name, entries]) => {
    const spans = entries.flatMap((e) => (Array.isArray(e.coverage) ? [e.coverage.map(num)] : [])).filter((c) => c.length === 2 && c[0] !== null && c[1] !== null) as number[][];
    // The newest by the underlying date -- not by the label text, whose prefix (published / file of / retrieved) would decide the order -- keeping that entry's label.
    const vintages = entries.map(vintageOf).filter((v): v is Vintage => v !== null).sort((a, b) => a.date.localeCompare(b.date));
    const id = str(entries[0].id) ?? '';
    return {
      name,
      usedFor: USED_FOR.find(([matches]) => matches(id))?.[1] ?? null,
      coverage: spans.length ? `${Math.min(...spans.map((s) => s[0]))}–${Math.max(...spans.map((s) => s[1]))}` : null,
      vintage: vintages.length ? vintages[vintages.length - 1].label : null,
      licences: [...new Set(entries.map((e) => str(e.license)).filter((l): l is string => l !== null))],
    };
  });
}

export interface TemperatureOffset {
  valueC: number;
  years: number;
  from: number;
  to: number;
}

/** The computed 1850–1900 reference offset, from `/meta.temperature_offset`; null when not published. */
export function buildTemperatureOffset(meta: CorrelationMetaResponse | null | undefined): TemperatureOffset | null {
  const o = rec(meta?.temperature_offset);
  const range = Array.isArray(o?.reference_period) ? o!.reference_period.map(num) : [];
  const valueC = num(o?.value_c);
  const years = num(o?.years);
  if (valueC === null || years === null || range.length !== 2 || range[0] === null || range[1] === null) return null;
  return { valueC, years, from: range[0], to: range[1] };
}
