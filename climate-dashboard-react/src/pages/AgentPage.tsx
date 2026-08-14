import { useEffect, useRef, useState } from 'react';
import { InlineAlert, Progress, PromptBar } from 'design-system';
import { StarterPromptTile } from '../components/StarterPromptTile';
import { useAgentStream } from '../agent/useAgentStream';
import { WidgetRenderer } from '../agent/WidgetRenderer';
import { toolNameFromSourceTaggedCall } from '../agent/types';
import type { AgentQueryResult } from '../agent/types';

// SPEC.md §4's four starter prompts. The two country-specific ones prefill PromptBar's value
// for the user to edit before submitting; the two forecast ones submit immediately.
const STARTER_PROMPTS: Array<{ kicker: string; prompt: string; prefill: boolean }> = [
  {
    kicker: 'Historical trends',
    prompt: "What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?",
    prefill: true,
  },
  {
    kicker: 'Historical trends',
    prompt: "How has India's emissions grown compared to other countries?",
    prefill: true,
  },
  { kicker: 'Forecasts', prompt: 'What are the top 10 forecasted emitters in 2040?', prefill: false },
  {
    kicker: 'Forecasts',
    prompt: 'Considering the top 10 emitters now and the forecasted ones in 2040, show the comparative trend for the countries.',
    prefill: false,
  },
];

interface ResultSection {
  id: number;
  query: string;
  result: AgentQueryResult;
}

// A section renders as plain response text (no intro paragraph above it, no widgets grid) when
// it's exactly the shape general_climate_node produces (graph.py) -- a single text widget whose
// own content already *is* response_text, so showing both would repeat the same paragraph twice.
function isGeneralClimateOnly(result: AgentQueryResult): boolean {
  return (
    result.widgets.length === 1 &&
    result.widgets[0].intent === 'text' &&
    toolNameFromSourceTaggedCall(result.widgets[0].source_tool_call) === 'general_climate'
  );
}

function StarterPromptsGrid({ onSelect }: { onSelect: (item: (typeof STARTER_PROMPTS)[number]) => void }) {
  return (
    <div
      style={{
        display: 'grid',
        // minmax(280px, 1fr) alone doesn't shrink below 280px per track even inside a
        // narrower viewport -- auto-fit's intrinsic sizing still reserves room for as many
        // fixed-280px columns as there are items, which forces this grid (and every flex
        // ancestor up to <main>, none of which have min-width:0) wider than the screen.
        // minmax(min(280px, 100%), 1fr) caps each track's minimum at the container's own
        // available width, so it collapses to one column instead of overflowing. Confirmed
        // live on a real narrow viewport: without this, <main> rendered at 968px on a 500px
        // viewport; with it, 484px.
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))',
        gap: 16,
        maxWidth: 900,
        margin: '0 auto',
        width: '100%',
      }}
    >
      {STARTER_PROMPTS.map((item) => (
        <StarterPromptTile key={item.prompt} kicker={item.kicker} prompt={item.prompt} onClick={() => onSelect(item)} />
      ))}
    </div>
  );
}

function ResultSectionView({ section, onSuggestedPromptClick }: { section: ResultSection; onSuggestedPromptClick: (prompt: string) => void }) {
  const { query, result } = section;
  const hasWidgets = result.widgets.length > 0;
  const textOnly = hasWidgets && isGeneralClimateOnly(result);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="__s9cmpx-label3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
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
          {result.suggested_prompts.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {result.suggested_prompts.map((prompt) => (
                <StarterPromptTile key={prompt} kicker="Try instead" prompt={prompt} onClick={() => onSuggestedPromptClick(prompt)} />
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {!textOnly && <div className="__s9cmpx-body3">{result.response_text}</div>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            {result.widgets.map((widget, i) => (
              <div key={`${widget.source_tool_call}-${i}`} style={{ flex: '1 1 420px', minWidth: 0 }}>
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
  const [starterGridDismissed, setStarterGridDismissed] = useState(false);
  const threadIdRef = useRef<string | null>(null);
  // Identity-compared against the hook's own `result`, not a "have we consumed this yet" flag
  // gated on a separate ref -- useAgentStream returns a fresh object per submit() and holds it
  // steady across re-renders in between, so this is the correct signal for "a new result just
  // arrived" without depending on handleSubmit having run first in the same render cycle.
  const lastResultRef = useRef<AgentQueryResult | null>(null);
  const nextSectionIdRef = useRef(0);
  const { submit, progress, result, error, loading } = useAgentStream();

  const hasSubmitted = sections.length > 0 || result != null || loading || error != null;
  // PromptBar exposes no focus/blur hook (see handleStarterClick's own comment below), so
  // "the user is about to enter another prompt" is approximated as "the docked input is idle
  // and empty" on a fresh turn only: once they've typed or picked anything, keep the grid
  // dismissed until a new response lands, even if they clear the text while still editing.
  const showStarterGridBetweenTurns = hasSubmitted && !loading && !starterGridDismissed && value.trim() === '';

  const handleSubmit = (query: string) => {
    setStarterGridDismissed(true);
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
    setStarterGridDismissed(false);
    // pendingQuery is a dependency for freshness, not as a second trigger condition -- this
    // effect still only *acts* when `result` is new (the guard above). Including it just makes
    // sure the closure reads the latest submitted query rather than a stale one captured the
    // last time `result` changed, on the rapid-second-submit path where pendingQuery updates
    // slightly ahead of the corresponding result arriving.
  }, [result, pendingQuery]);

  const handleValueChange = (nextValue: string) => {
    if (hasSubmitted) setStarterGridDismissed(true);
    setValue(nextValue);
  };

  const handleStarterClick = (item: (typeof STARTER_PROMPTS)[number]) => {
    setStarterGridDismissed(true);
    // SPEC.md §4: prefill + focus for the country-specific prompts -- PromptBar's own prop
    // surface (value/onChange/onSubmit/variant/placeholder/loading/disabled/actions/ariaLabel/
    // className) has no imperative focus method, so only the prefill half is achievable here;
    // the user still has to click into the textarea themselves. Flagged, not silently assumed
    // fixed -- see SPEC.md "Corrections applied" #18.
    if (item.prefill) {
      setValue(item.prompt);
    } else {
      handleSubmit(item.prompt);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: hasSubmitted ? '24px 24px 48px' : '48px 24px' }}>
      {!hasSubmitted && (
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <h1 className="__s9cmpx-headline3">Ask about climate emissions</h1>
          <p className="__s9cmpx-body3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
            Historical trends, forecasts, and scenario comparisons -- backed by real data, not a generic chatbot.
          </p>
        </div>
      )}

      <PromptBar
        value={value}
        onChange={handleValueChange}
        onSubmit={handleSubmit}
        variant={hasSubmitted ? 'docked' : 'landing'}
        loading={loading}
        ariaLabel="Ask about climate emissions"
      />

      {(!hasSubmitted || showStarterGridBetweenTurns) && <StarterPromptsGrid onSelect={handleStarterClick} />}

      {loading && <Progress value={progress?.percent ?? 0} label={progress?.label ?? 'Thinking…'} />}

      {error && <InlineAlert variant="error">{error}</InlineAlert>}

      {sections.map((section) => (
        <ResultSectionView key={section.id} section={section} onSuggestedPromptClick={handleSubmit} />
      ))}
    </div>
  );
}
