/** The page year shown in a section's header (ENHANCEMENTS.md decision 64), so every section that follows it says which year it is showing. */
export function YearBadge({ year }: { year: number }) {
  return (
    <span
      aria-label={`Year ${year}`}
      className="__s9cmpx-label4"
      style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 3, fontVariantNumeric: 'tabular-nums', background: 'var(--__s9cmpx-static-background-strong, rgba(127,127,127,0.18))', color: 'var(--__s9cmpx-static-text-standard)' }}
    >
      {year}
    </span>
  );
}
