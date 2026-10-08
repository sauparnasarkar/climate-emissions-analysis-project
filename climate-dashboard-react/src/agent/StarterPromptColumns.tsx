import { Tag } from 'design-system';
import { STARTER_COLUMNS } from './starterPrompts';

const CSS = `
.ask-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; text-align: left; }
@media (max-width: 768px) { .ask-columns { grid-template-columns: minmax(0, 1fr); gap: 12px; } }
.ask-column { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.ask-column__label { display: flex; align-items: center; gap: 8px; font-family: var(--__s9cmpx-font-families-mono, ui-monospace, monospace); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--__s9cmpx-static-text-weak); }
.ask-card { display: flex; flex-direction: column; justify-content: space-between; gap: 8px; width: 100%; min-height: 84px; box-sizing: border-box; padding: 14px 16px; text-align: left; font: inherit; font-size: 14px; line-height: 1.45; color: inherit; cursor: pointer;
  background: var(--__s9cmpx-static-background-standard); border: 1px solid var(--__s9cmpx-interactive-outline-secondary-default); border-radius: 10px; }
.ask-card:hover { border-color: var(--__s9cmpx-interactive-outline-focus); }
.ask-card:focus-visible { outline: 2px solid var(--__s9cmpx-interactive-outline-focus); outline-offset: 2px; }
.ask-card__arrow { align-self: flex-end; color: var(--__s9cmpx-static-text-weak); }
@media (max-width: 768px) { .ask-card { min-height: 56px; } }
`;

/**
 * The three starter-prompt columns under the landing input (design handoff; ENHANCEMENTS.md decision 102): a mono category label (a NEW tag on
 * Climate outcomes) over two prompt cards. A card PREFILLS the input and focuses it; it never submits. One column on phones.
 */
export function StarterPromptColumns({ onSelect }: { onSelect: (prompt: string) => void }) {
  return (
    <div className="ask-columns">
      <style>{CSS}</style>
      {STARTER_COLUMNS.map((column) => (
        <section key={column.label} className="ask-column" aria-label={column.label}>
          <div className="ask-column__label">
            {column.label}
            {column.isNew && <Tag color="green" size="small">NEW</Tag>}
          </div>
          {column.prompts.map((prompt) => (
            <button key={prompt} type="button" className="ask-card" onClick={() => onSelect(prompt)}>
              <span>{prompt}</span>
              <span className="ask-card__arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </section>
      ))}
    </div>
  );
}
