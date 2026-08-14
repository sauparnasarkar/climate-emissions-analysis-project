import { Tile, Icon } from 'design-system';

export interface StarterPromptTileProps {
  /** e.g. "Historical trends", "Forecasts" (SPEC.md §4) */
  kicker: string;
  prompt: string;
  onClick: () => void;
}

// SPEC.md "Corrections applied" #3: Tile is a plain container with no built-in kicker/prompt/
// arrow composition, so this small local composition covers both call sites that need one --
// the landing starter-prompt grid (§4) and the opinion-guardrail's suggested reframes (§6).
// Tile always renders a <div> (no polymorphic `as` prop), so button semantics/keyboard
// activation are added by hand rather than reaching for a native <button>.
export function StarterPromptTile({ kicker, prompt, onClick }: StarterPromptTileProps) {
  return (
    <Tile
      interactive
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, cursor: 'pointer' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
        <span className="__s9cmpx-label3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
          {kicker}
        </span>
        <span className="__s9cmpx-body4">{prompt}</span>
      </div>
      <Icon name="chevron-right" size={18} style={{ flexShrink: 0, color: 'var(--__s9cmpx-static-text-weak)' }} />
    </Tile>
  );
}
