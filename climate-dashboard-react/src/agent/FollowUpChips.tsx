const CSS = `
.ask-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.ask-chip { font: inherit; font-size: 13px; line-height: 1.3; padding: 6px 12px; color: inherit; cursor: pointer; background: transparent; border: 1px solid var(--__s9cmpx-interactive-outline-secondary-default); border-radius: 16px; text-align: left; }
.ask-chip:hover { border-color: var(--__s9cmpx-interactive-outline-focus); }
.ask-chip:focus-visible { outline: 2px solid var(--__s9cmpx-interactive-outline-focus); outline-offset: 2px; }
@media (max-width: 768px) {
  /* one row that scrolls sideways, each chip inside a 44px tap row */
  .ask-chips { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
  .ask-chips li { flex: none; display: flex; align-items: center; min-height: 44px; }
  .ask-chip { min-height: 36px; white-space: nowrap; }
}
`;

/** Up to three follow-up prompts above the docked input (design handoff): prompts, not links. Like the starter cards they PREFILL the input and focus
 * it rather than sending (ENHANCEMENTS.md decision 102; the handoff would send, one behaviour is used for every prompt the system offers). */
export function FollowUpChips({ prompts, onSelect }: { prompts: string[]; onSelect: (prompt: string) => void }) {
  if (prompts.length === 0) return null;
  return (
    <div role="group" aria-label="Suggested follow-up questions">
      <style>{CSS}</style>
      <ul className="ask-chips">
        {prompts.map((prompt) => (
          <li key={prompt}>
            <button type="button" className="ask-chip" onClick={() => onSelect(prompt)}>
              {prompt}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
