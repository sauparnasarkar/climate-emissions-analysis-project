/** The "Source: ..." line under a chart (design handoff: every chart states its source and scope, in 12px muted type). The text is the agent's
 * deterministic `source_line`, built from the tool result: coverage years, and whether land use is included. */
export function SourceLine({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <p className="__s9cmpx-body4" style={{ margin: '6px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
      {text}
    </p>
  );
}

/** The scenario answer's warning chip ("Illustrative · implied outcomes, not climate-model projections"): mono caps in the theme-aware amber the
 * module's own "illustrative" chips use (`--area2-warning`, ENHANCEMENTS.md decision 68), on a faint tint of the same colour. */
export function ScenarioBadge({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <span
      style={{
        display: 'inline-block',
        alignSelf: 'flex-start',
        fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)',
        fontSize: 11,
        letterSpacing: '.06em',
        textTransform: 'uppercase',
        color: 'var(--area2-warning, inherit)',
        background: 'color-mix(in srgb, var(--area2-warning, currentColor) 12%, transparent)',
        borderRadius: 3,
        padding: '3px 8px',
        margin: '0 0 8px',
      }}
    >
      {text}
    </span>
  );
}
