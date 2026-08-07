import type { MoverRow } from '../api/types';

// Below this many rows with usable (non-null) figures, the "most stable" clause is suppressed
// -- with very few countries selected, "stayed comparatively flat" reads as a meaningless
// distinction rather than a genuine standout (SPEC.md §5.18.1).
const MIN_SELECTION_FOR_STABLE_CLAUSE = 4;

interface HeadlineRow {
  country: string;
  absoluteChange: number;
  pctChange: number;
}

// Hand-rolled instead of lodash (no such dependency exists in this project) -- linear scan with
// strict >/< so ties deterministically keep the first element in `rows`' given order, rather
// than depending on Array.sort's stability (which only the decliners list below actually needs).
function maxBy<T>(rows: T[], key: (row: T) => number): T {
  return rows.reduce((best, row) => (key(row) > key(best) ? row : best));
}
function minBy<T>(rows: T[], key: (row: T) => number): T {
  return rows.reduce((best, row) => (key(row) < key(best) ? row : best));
}

function formatMt(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function formatPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`;
}

/**
 * Builds the Overview page's deterministic "Since 1990" headline sentence from
 * `headline_movers`. Returns `null` when there's nothing usable to say (no rows with both
 * figures present).
 *
 * `scope` is a caller-supplied clause describing which countries are in view (e.g. "the top 10
 * emitters by 2024 output") -- kept out of this function for the same reason the "Since 1990"
 * eyebrow label is: it's a rendering/wording concern, not a derived fact, so the pure function's
 * output stays independently testable against arbitrary scope text (SPEC.md §5.18.5).
 *
 * Derives every fact itself rather than trusting `headlineMovers`' given order -- "sorted
 * descending by co2_latest" is a server-side (Python) contract not encoded in `MoverRow` itself,
 * so a `headlineMovers[0]` shortcut would silently break if that contract ever changed.
 */
export function buildHeadlineSentence(headlineMovers: MoverRow[], scope: string): string | null {
  const rows: HeadlineRow[] = headlineMovers
    .filter((m): m is MoverRow & { absolute_change: number; pct_change: number } =>
      m.absolute_change != null && m.pct_change != null,
    )
    .map((m) => ({ country: m.country, absoluteChange: m.absolute_change, pctChange: m.pct_change }));

  if (rows.length === 0) return null;

  const absGrower = maxBy(rows, (r) => r.absoluteChange);
  const pctGrower = maxBy(rows, (r) => r.pctChange);
  const mostStable = minBy(rows, (r) => Math.abs(r.pctChange));
  const decliners = rows
    .filter((r) => r.pctChange < 0)
    .sort((a, b) => a.pctChange - b.pctChange)
    .slice(0, 2);

  // First sentence: who grew the most (absolute vs. rate), collapsed to one clause when the
  // same country tops both. Doesn't repeat "since 1990" inline -- the caller's "Since 1990"
  // eyebrow already carries that timeframe, and stating it twice in the same three lines reads
  // as a copy-editing miss rather than emphasis. "Among {scope}, " is fused onto the front via a
  // plain comma splice -- the clause that follows already starts with a capitalized proper noun
  // (a country name), so no further capitalization/punctuation adjustment is needed at the join.
  const growthSentence =
    absGrower.country === pctGrower.country
      ? `Among ${scope}, ${absGrower.country} has grown the most, both in absolute terms (+${formatMt(absGrower.absoluteChange)} MtCO₂) and by growth rate (${formatPct(absGrower.pctChange)}%).`
      : `Among ${scope}, ${absGrower.country} has grown the most in absolute terms (+${formatMt(absGrower.absoluteChange)} MtCO₂), while ${pctGrower.country} has the fastest growth rate (${formatPct(pctGrower.pctChange)}%).`;

  // Second sentence: stability + declines. Either half (or the whole sentence) may be omitted.
  const secondClauses: string[] = [];
  if (rows.length >= MIN_SELECTION_FOR_STABLE_CLAUSE) {
    secondClauses.push(`${mostStable.country} has stayed comparatively flat (${formatPct(mostStable.pctChange)}%)`);
  }
  if (decliners.length === 1) {
    secondClauses.push(`${decliners[0].country} shows the steepest decline (${formatPct(decliners[0].pctChange)}%)`);
  } else if (decliners.length === 2) {
    secondClauses.push(
      `${decliners[0].country} and ${decliners[1].country} show the steepest declines (${formatPct(decliners[0].pctChange)}%, ${formatPct(decliners[1].pctChange)}%)`,
    );
  }

  if (secondClauses.length === 0) return growthSentence;
  return `${growthSentence} ${secondClauses.join(', while ')}.`;
}
