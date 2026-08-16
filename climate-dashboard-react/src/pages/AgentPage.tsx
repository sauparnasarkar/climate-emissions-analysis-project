import { useEffect, useRef, useState } from 'react';
import { InlineAlert, Progress, PromptBar } from 'design-system';
import { StarterPromptTile } from '../components/StarterPromptTile';
import { useAgentStream } from '../agent/useAgentStream';
import { MarkdownText } from '../agent/MarkdownText';
import { WidgetRenderer } from '../agent/WidgetRenderer';
import { toolNameFromSourceTaggedCall } from '../agent/types';
import type { AgentQueryResult } from '../agent/types';

// SPEC.md §4's four starter prompts. All four prefill PromptBar's value for the user to edit
// before submitting -- previously the two forecast ones submitted immediately on click, which
// read as an inconsistent surprise next to the two country-specific ones (direct instruction:
// clicking either row should behave the same way).
const STARTER_PROMPTS: Array<{ kicker: string; prompt: string }> = [
  {
    kicker: 'Historical trends',
    prompt: "What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?",
  },
  {
    kicker: 'Historical trends',
    prompt: "How has India's emissions grown compared to other countries?",
  },
  { kicker: 'Forecasts', prompt: 'What are the top 10 forecasted emitters in 2040?' },
  {
    kicker: 'Forecasts',
    prompt: 'Considering the top 10 emitters now and the forecasted ones in 2040, show the comparative trend for the countries.',
  },
];

interface ResultSection {
  id: number;
  query: string;
  result: AgentQueryResult;
}

// A section renders as plain response text (no intro paragraph above it, no widgets grid) when
// its one widget's own content already *is* response_text, so showing both would repeat the same
// paragraph twice -- true for general_climate_node's fixed text widget and, since SPEC.md
// correction #22, ui_selection_node's "context_reuse" widget (a zero-tool-call turn that answered
// from prior context) -- both set response_text directly from the same raw text as their widget.
// Deliberately NOT any single text-intent widget: get_methodology_notes, for example, also
// produces exactly one text widget, but its response_text is compose_response_node's own separate
// summary of it, not a copy -- showing both there is intentional, not a duplicate.
const TEXT_ANSWER_TAGS = new Set(['general_climate', 'context_reuse']);

// Explicit column target, not auto-fit -- the user wants widget count to drive layout directly:
// 1/2/3 widgets get that many columns each, 4 widgets deliberately drops to 2 (a 4-up row reads
// as cramped at this card size) rather than the naive next step of 4, and 5+ caps at 3 so cards
// stay legible regardless of how many widgets a turn produces. See the .agent-widget-grid media
// query below for the mobile collapse this doesn't handle on its own (a repeat(N, ...) grid
// doesn't shrink its own column count the way auto-fit does).
function widgetColumnCount(count: number): number {
  if (count <= 3) return count;
  if (count === 4) return 2;
  return 3;
}

function isTextOnlyAnswer(result: AgentQueryResult): boolean {
  return (
    result.widgets.length === 1 &&
    result.widgets[0].intent === 'text' &&
    TEXT_ANSWER_TAGS.has(toolNameFromSourceTaggedCall(result.widgets[0].source_tool_call))
  );
}

// Same "explicit count, not auto-fit" reasoning as widgetColumnCount below, capped at 2x2 or 3x3
// specifically (not widgetColumnCount's 1/2/3/2/3 curve) -- this grid now lives inside PromptBar's
// own expandedContent, a fixed-width container, not a full-page one, so a squarer cap reads
// better there than a wide flat row would.
function starterPromptColumnCount(count: number): number {
  return count <= 4 ? 2 : 3;
}

function StarterPromptsGrid({ onSelect }: { onSelect: (item: (typeof STARTER_PROMPTS)[number]) => void }) {
  return (
    <div
      className="starter-prompt-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${starterPromptColumnCount(STARTER_PROMPTS.length)}, 1fr)`,
        gap: 12,
        width: '100%',
      }}
    >
      {STARTER_PROMPTS.map((item) => (
        <StarterPromptTile key={item.prompt} kicker={item.kicker} prompt={item.prompt} onClick={() => onSelect(item)} />
      ))}
    </div>
  );
}

function ResultSectionView({
  section,
  onSuggestedPromptClick,
  showSuggestedPrompts,
}: {
  section: ResultSection;
  onSuggestedPromptClick: (prompt: string) => void;
  // Only the single current result's own "Try instead" tiles stay actionable (direct report:
  // every past turn's tiles remained clickable forever, unlike the starter grid which disappears
  // once you've moved past it). False for every section behind the current result, and for that
  // one too while a new submission is in flight -- matching the starter grid's own
  // collapse-on-loading behavior rather than waiting for the new section to land. This is keyed
  // to the hook's current result identity, not just sections[0], so a just-finished new result
  // doesn't briefly re-expose the previous turn's stale tiles during the render before the effect
  // prepends its new section.
  showSuggestedPrompts: boolean;
}) {
  const { query, result } = section;
  const hasWidgets = result.widgets.length > 0;
  const textOnly = hasWidgets && isTextOnlyAnswer(result);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Same size as the answer text (MarkdownText's own <p> uses __s9cmpx-body3) -- only the
          weaker color, not a smaller size, distinguishes the user's own query from the answer
          below it. */}
      <div className="__s9cmpx-body3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
        {query}
      </div>
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
          <div
            className="agent-widget-grid"
            style={{ display: 'grid', gridTemplateColumns: `repeat(${widgetColumnCount(result.widgets.length)}, 1fr)`, gap: 16 }}
          >
            {result.widgets.map((widget, i) => (
              <div key={`${widget.source_tool_call}-${i}`} style={{ minWidth: 0 }}>
                <WidgetRenderer widget={widget} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function AgentPage() {
  const [value, setValue] = useState('');
  const [sections, setSections] = useState<ResultSection[]>([]);
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const threadIdRef = useRef<string | null>(null);
  // Identity-compared against the hook's own `result`, not a "have we consumed this yet" flag
  // gated on a separate ref -- useAgentStream returns a fresh object per submit() and holds it
  // steady across re-renders in between, so this is the correct signal for "a new result just
  // arrived" without depending on handleSubmit having run first in the same render cycle.
  const lastResultRef = useRef<AgentQueryResult | null>(null);
  const nextSectionIdRef = useRef(0);
  const promptBarRef = useRef<HTMLTextAreaElement>(null);
  const { submit, progress, result, error, loading } = useAgentStream();

  const hasSubmitted = sections.length > 0 || result != null || loading || error != null;

  const handleSubmit = (query: string) => {
    setPendingQuery(query);
    submit(query, threadIdRef.current);
    setValue('');
  };

  useEffect(() => {
    if (!result || result === lastResultRef.current) return;
    lastResultRef.current = result;
    threadIdRef.current = result.thread_id;
    const id = nextSectionIdRef.current++;
    setSections((prev) => [{ id, query: pendingQuery ?? '', result }, ...prev]);
    // pendingQuery is a dependency for freshness, not as a second trigger condition -- this
    // effect still only *acts* when `result` is new (the guard above). Including it just makes
    // sure the closure reads the latest submitted query rather than a stale one captured the
    // last time `result` changed, on the rapid-second-submit path where pendingQuery updates
    // slightly ahead of the corresponding result arriving.
  }, [result, pendingQuery]);

  // SPEC.md §4/§6: prefill + focus, shared by the starter grid and the §6 suggested-prompt
  // "Try instead" tiles -- both used to diverge (starter grid always prefilled, suggested
  // prompts auto-submitted instead), which read as the same inconsistency in two different
  // places. PromptBar exposes the textarea via ref (design-system PR #44, closing "Corrections
  // applied" #18's previously flagged gap), so the focus half isn't just aspirational -- the
  // user lands in the textarea with the prefilled text ready to edit, not stuck on the tile
  // they just clicked.
  const prefillAndFocus = (prompt: string) => {
    setValue(prompt);
    promptBarRef.current?.focus();
  };

  const handleStarterClick = (item: (typeof STARTER_PROMPTS)[number]) => prefillAndFocus(item.prompt);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: hasSubmitted ? '24px 24px 48px' : '48px 24px' }}>
      {/* Placed once here, not per-section -- ResultSectionView renders one .agent-widget-grid
          per turn, and they all want the identical collapse rule. A fixed repeat(N, 1fr) grid
          doesn't shrink its own column count on a narrow viewport the way auto-fit does (SPEC.md
          confirmed this repo's minmax(min(X,100%),1fr) pattern doesn't help here either -- with a
          FIXED track count, every track's minimum resolves against the same container width, so
          N>1 tracks still overflow instead of collapsing); one explicit breakpoint straight to a
          single column is simpler and more predictable than trying to make the N-column math
          responsive on its own. */}
      {/* Same reasoning as .agent-widget-grid's own media query below, applied to the starter
          grid now that it lives inside PromptBar's expandedContent -- a fixed 2- or 3-column
          grid doesn't shrink its own column count on a narrow viewport the way auto-fit did in
          its previous standalone placement. */}
      <style>
        {'@media (max-width: 768px) { .agent-widget-grid, .starter-prompt-grid { grid-template-columns: 1fr !important; } }'}
      </style>
      {!hasSubmitted && (
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <h1 className="__s9cmpx-headline3">Ask about climate emissions</h1>
          <p className="__s9cmpx-body3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
            Historical trends, forecasts, and scenario comparisons -- backed by real data, not a generic chatbot.
          </p>
        </div>
      )}

      <PromptBar
        ref={promptBarRef}
        value={value}
        onChange={setValue}
        onSubmit={handleSubmit}
        variant={hasSubmitted ? 'docked' : 'landing'}
        loading={loading}
        ariaLabel="Ask about climate emissions"
        expandedContent={<StarterPromptsGrid onSelect={handleStarterClick} />}
      />

      {loading && <Progress value={progress?.percent ?? 0} label={progress?.label ?? 'Thinking…'} />}

      {error && <InlineAlert variant="error">{error}</InlineAlert>}

      {sections.map((section) => (
        <ResultSectionView
          key={section.id}
          section={section}
          onSuggestedPromptClick={prefillAndFocus}
          showSuggestedPrompts={section.result === result && !loading}
        />
      ))}
    </div>
  );
}
