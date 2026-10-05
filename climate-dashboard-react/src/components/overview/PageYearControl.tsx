import { Button, Select } from 'design-system';

/**
 * The sticky Year control in the Overview's anchor bar (ENHANCEMENTS.md decision 64): a select over the decade stops plus Play. It sets the same
 * value as the map's stops, Play and slider. A year picked by the slider that isn't a stop is listed too, so the select always shows the truth.
 */
export function PageYearControl({ stops, year, isPlaying, onSelect, onToggle }: { stops: number[]; year: number; isPlaying: boolean; onSelect: (year: number) => void; onToggle: () => void }) {
  const years = stops.includes(year) ? stops : [...stops, year].sort((a, b) => a - b);
  return (
    <div role="group" aria-label="Page year" style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
      <span className="__s9cmpx-label4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>Year</span>
      <div style={{ minWidth: 96 }}>
        <Select size="small" suppressSearch ariaLabel="Page year" value={String(year)} onChange={(v) => onSelect(Number(v))} options={years.map((y) => ({ value: String(y), label: String(y) }))} />
      </div>
      <Button variant="ghost-blue" onClick={onToggle}>{isPlaying ? 'Pause' : 'Play'}</Button>
    </div>
  );
}
