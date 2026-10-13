import { useCallback, useMemo } from 'react';
import { useUrlChoice } from './useUrlChoice';

/** The first year "counting from a year" can start at: the cumulative views' window (the API holds 1969 as the base, ENHANCEMENTS.md Release 24.8). */
export const COUNTING_FROM_MIN_YEAR = 1970;
// Valid values for `?from=`; the API rejects a year after its last data year (a 422 the page shows as its error).
const FROM_OPTIONS = Array.from({ length: new Date().getFullYear() - COUNTING_FROM_MIN_YEAR + 1 }, (_, i) => String(COUNTING_FROM_MIN_YEAR + i));

/**
 * Where cumulative CO₂ is counted from, kept in `?from=YYYY` (absent = since records began, the default; an unrecognised value is read as absent) so a link, such as
 * the agent's "Open in Historical Trends", opens on the same numbers as its answer. Returns the year or null, and a setter that takes a year or null.
 */
export function useCountingFrom(): [number | null, (year: number | null) => void] {
  const [raw, setRaw] = useUrlChoice('from', FROM_OPTIONS, '');
  const from = useMemo(() => (raw === '' ? null : Number(raw)), [raw]);
  const setFrom = useCallback((year: number | null) => setRaw(year == null ? '' : String(year)), [setRaw]);
  return [from, setFrom];
}
