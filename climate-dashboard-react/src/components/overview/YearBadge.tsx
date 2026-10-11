import { VISUALLY_HIDDEN } from '../../lib/visuallyHidden';

/** The page year shown in a section's header (ENHANCEMENTS.md decision 64), so every section that follows it says which year it is showing.
 * The word "Year" is visually hidden text, not an `aria-label`: ARIA prohibits naming a role-less `span`, so screen
 * readers ignored the label and announced a bare number (ENHANCEMENTS.md Release 22). */
export function YearBadge({ year }: { year: number }) {
  return (
    <span
      className="__s9cmpx-label4"
      style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 3, fontVariantNumeric: 'tabular-nums', background: 'var(--__s9cmpx-static-background-strong, rgba(127,127,127,0.18))', color: 'var(--__s9cmpx-static-text-standard)' }}
    >
      {/* Leading space: every call site puts the badge straight after heading text ("By Country<YearBadge/>"),
          so without it the accessible name ran together as "By CountryYear 2024". */}
      <span style={VISUALLY_HIDDEN}>{' Year '}</span>
      {year}
    </span>
  );
}
