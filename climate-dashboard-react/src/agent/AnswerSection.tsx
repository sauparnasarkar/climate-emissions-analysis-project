import { forwardRef, useId } from 'react';
import { InlineAlert } from 'design-system';
import { StarterPromptTile } from '../components/StarterPromptTile';
import { FollowUpLinks } from './FollowUpLinks';
import { KpiRow } from './KpiRow';
import { MarkdownText } from './MarkdownText';
import { ScenarioBadge } from './SourceLine';
import { WidgetRenderer } from './WidgetRenderer';
import { categoryFor } from './starterPrompts';
import { toolNameFromSourceTaggedCall } from './types';
import type { AgentQueryResult } from './types';

// A section renders as plain response text (no intro paragraph above it) when its one widget's own content already *is* response_text, so showing
// both would repeat the same paragraph twice -- true for general_climate_node's fixed text widget and, since SPEC.md correction #22,
// ui_selection_node's "context_reuse" widget (a zero-tool-call turn that answered from prior context). Deliberately NOT any single text-intent
// widget: get_methodology_notes, for example, also produces exactly one text widget, but its response_text is compose_response_node's own separate
// summary of it, not a copy -- showing both there is intentional.
const TEXT_ANSWER_TAGS = new Set(['general_climate', 'context_reuse']);

function isTextOnlyAnswer(result: AgentQueryResult): boolean {
  return (
    result.widgets.length === 1 &&
    result.widgets[0].intent === 'text' &&
    TEXT_ANSWER_TAGS.has(toolNameFromSourceTaggedCall(result.widgets[0].source_tool_call))
  );
}

const CATEGORY_STYLE = {
  fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)',
  fontSize: 11,
  letterSpacing: '.06em',
  textTransform: 'uppercase',
  color: 'var(--__s9cmpx-static-text-weak)',
} as const;

/** The heading block shared by an answer, a pending answer and a failed one: the category label and the question as an h2 (design handoff A2). */
export function QuestionHeading({ query, category, id }: { query: string; category: string | null; id: string }) {
  return (
    <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {category && <div style={CATEGORY_STYLE}>{category}</div>}
      <h2 id={id} className="__s9cmpx-headline5" style={{ margin: 0, fontWeight: 600 }}>
        {query}
      </h2>
    </header>
  );
}

export interface AnswerSectionProps {
  query: string;
  result: AgentQueryResult;
  // Only the single current result's own "Try instead" tiles stay actionable (direct report: every past turn's tiles remained clickable forever).
  // False for every section behind the current result, and for that one too while a new submission is in flight. Keyed to the hook's current result
  // identity by the page, so a just-finished new result never briefly re-exposes the previous turn's stale tiles.
  showSuggestedPrompts: boolean;
  onSuggestedPromptClick: (prompt: string) => void;
}

/**
 * One answer in the thread (design handoff A2/A3; ENHANCEMENTS.md "Step 3.5d-2"): category label and the question as an h2, the scenario chip, the
 * scope notes, the lead, the KPI row, the widgets stacked in one column (each with its source line), and the deep links. The guardrail replies
 * (off-topic, opinion) have no widgets: their text is an alert, with the "Try instead" tiles.
 */
export const AnswerSection = forwardRef<HTMLElement, AnswerSectionProps>(function AnswerSection(
  { query, result, showSuggestedPrompts, onSuggestedPromptClick },
  ref,
) {
  const headingId = useId();
  const hasWidgets = result.widgets.length > 0;
  const textOnly = hasWidgets && isTextOnlyAnswer(result);
  const badge = result.widgets.find((w) => w.badge)?.badge;
  return (
    <section ref={ref} aria-labelledby={headingId} style={{ display: 'flex', flexDirection: 'column', gap: 14, scrollMarginTop: 80 }}>
      <QuestionHeading query={query} category={categoryFor(query, result.widgets)} id={headingId} />
      <ScenarioBadge text={badge} />
      {result.scope_notes.map((note, i) => (
        <InlineAlert key={i} variant="default">
          {note}
        </InlineAlert>
      ))}
      {!hasWidgets ? (
        <>
          <InlineAlert variant="default">{result.response_text}</InlineAlert>
          {showSuggestedPrompts && result.suggested_prompts.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {result.suggested_prompts.map((prompt) => (
                <StarterPromptTile key={prompt} kicker="Try instead" prompt={prompt} onClick={() => onSuggestedPromptClick(prompt)} />
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {!textOnly && <MarkdownText text={result.response_text} />}
          <KpiRow kpis={result.kpis ?? []} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {result.widgets.map((widget, i) => (
              <div key={`${widget.source_tool_call}-${i}`} style={{ minWidth: 0 }}>
                <WidgetRenderer widget={widget} />
              </div>
            ))}
          </div>
        </>
      )}
      <FollowUpLinks links={result.follow_up_links ?? []} />
    </section>
  );
});
