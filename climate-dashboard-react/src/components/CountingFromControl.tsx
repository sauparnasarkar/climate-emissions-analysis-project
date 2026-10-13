import { Select, SegmentedControl } from 'design-system';
import { BASELINE_YEAR } from '../constants';
import { COUNTING_FROM_MIN_YEAR } from '../hooks/useCountingFrom';

const ITEMS = [
  { value: 'records', label: 'Since records began' },
  { value: 'year', label: 'From a year' },
];

/**
 * The counting-from choice of the cumulative views (ENHANCEMENTS.md Release 24.8): the default is the total since each country's records began; "From a year" counts
 * only the emissions from that year (each total minus its total the year before), the same figure the agent gives for "since 1990". `lastYear` is the last year
 * with data, so no year the API would refuse is offered.
 */
export function CountingFromControl({ from, onChange, lastYear, name }: { from: number | null; onChange: (year: number | null) => void; lastYear: number; name: string }) {
  // Up to the last year with data, or the requested year if it is later (a hand-edited ?from=2025): the control must show what was asked for, not a different year,
  // while the page shows the API's own message about the range (the hook only knows the calendar year, not where the data ends).
  const top = Math.max(lastYear, from ?? 0);
  const years = Array.from({ length: Math.max(0, top - COUNTING_FROM_MIN_YEAR + 1) }, (_, i) => COUNTING_FROM_MIN_YEAR + i);
  const defaultYear = Math.min(Math.max(BASELINE_YEAR, COUNTING_FROM_MIN_YEAR), lastYear);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '8px 12px', margin: '0 0 12px' }}>
      <SegmentedControl name={name} items={ITEMS} value={from == null ? 'records' : 'year'} onChange={(v) => onChange(v === 'records' ? null : (from ?? defaultYear))} />
      {from != null && (
        <Select
          label="From year"
          options={years.map((y) => ({ value: String(y), label: String(y) }))}
          value={String(from)}
          onChange={(v) => onChange(Number(v))}
        />
      )}
    </div>
  );
}
