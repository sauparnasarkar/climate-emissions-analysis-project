import { useEffect, useId, useRef, useState } from 'react';
import { Button, InlineAlert, Progress, PromptBar, useReducedMotion } from 'design-system';
import { AnswerSection, QuestionHeading } from '../agent/AnswerSection';
import { AnswerSkeleton } from '../agent/AnswerSkeleton';
import { FollowUpChips } from '../agent/FollowUpChips';
import { StarterPromptColumns } from '../agent/StarterPromptColumns';
import { categoryFor } from '../agent/starterPrompts';
import { useAgentStream } from '../agent/useAgentStream';
import type { AgentQueryResult } from '../agent/types';

// The Ask the Agent page (design handoff `design/ask-the-agent/`; ENHANCEMENTS.md decisions 102-109 and "Step 3.5d-2").
// Landing: a title, the input with its hint, and three columns of starter prompts under it. After the first question the input is pinned to the
// bottom with follow-up chips above it, and the answers stack above it in the order they were asked (the newest scrolls into view).

interface AnswerEntry {
  id: number;
  query: string;
  result: AgentQueryResult;
}

const COLUMN: React.CSSProperties = { width: '100%', maxWidth: 960, margin: '0 auto', boxSizing: 'border-box', padding: '0 24px' };

function PendingAnswer({ query, label, percent }: { query: string; label: string; percent: number }) {
  const headingId = useId();
  return (
    <section aria-busy="true" aria-labelledby={headingId} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <QuestionHeading query={query} category={categoryFor(query, [])} id={headingId} />
      <Progress value={percent} label={label} />
      <AnswerSkeleton />
    </section>
  );
}

function FailedAnswer({ query, message, onRetry }: { query: string; message: string; onRetry: () => void }) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <QuestionHeading query={query} category={categoryFor(query, [])} id={headingId} />
      <InlineAlert variant="error">{message}</InlineAlert>
      <div>
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </section>
  );
}

export function AgentPage() {
  const [value, setValue] = useState('');
  const [answers, setAnswers] = useState<AnswerEntry[]>([]);
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const threadIdRef = useRef<string | null>(null);
  // Identity-compared against the hook's own `result`, not a "have we consumed this yet" flag: useAgentStream returns a fresh object per submit()
  // and holds it steady across re-renders in between, so this is the correct signal for "a new result just arrived".
  const lastResultRef = useRef<AgentQueryResult | null>(null);
  const nextIdRef = useRef(0);
  const promptBarRef = useRef<HTMLTextAreaElement>(null);
  const newestRef = useRef<HTMLElement | null>(null);
  const reduceMotion = useReducedMotion();
  const { submit, progress, result, error, loading, reset } = useAgentStream();

  const hasSubmitted = answers.length > 0 || loading || error != null;

  const handleSubmit = (query: string) => {
    setPendingQuery(query);
    submit(query, threadIdRef.current);
    setValue('');
  };

  useEffect(() => {
    if (!result || result === lastResultRef.current) return;
    lastResultRef.current = result;
    threadIdRef.current = result.thread_id;
    const id = nextIdRef.current++;
    // pendingQuery is a dependency for freshness, not as a second trigger: the effect only *acts* when `result` is new (the guard above). Including it
    // makes sure the closure reads the latest submitted query on the rapid-second-submit path where pendingQuery updates slightly ahead of the result.
    setAnswers((prev) => [...prev, { id, query: pendingQuery ?? '', result }]);
  }, [result, pendingQuery]);

  // A new answer scrolls into view (the input is pinned below, so the newest answer is the last one). Instant under reduced motion; jsdom has no
  // scrollIntoView, hence the optional call.
  const answerCount = answers.length;
  useEffect(() => {
    if (answerCount > 0) newestRef.current?.scrollIntoView?.({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  }, [answerCount, reduceMotion]);

  // The field is cleared on submit; if the question then fails, put the text back so it is not lost (design handoff: "the input keeps the text").
  useEffect(() => {
    if (error && pendingQuery) setValue((current) => current || pendingQuery);
  }, [error, pendingQuery]);

  // Prefill + focus, shared by the starter cards, the follow-up chips and the "Try instead" tiles: one behaviour for every prompt the page offers
  // (ENHANCEMENTS.md decision 102). The user lands in the textarea with the prompt ready to edit or send.
  const prefillAndFocus = (prompt: string) => {
    setValue(prompt);
    promptBarRef.current?.focus();
  };

  const handleRetry = () => {
    if (!pendingQuery) return;
    submit(pendingQuery, threadIdRef.current);
    setValue('');
  };

  const handleNewQuestion = () => {
    reset();
    setAnswers([]);
    setPendingQuery(null);
    threadIdRef.current = null;
    lastResultRef.current = null;
    setValue('');
  };

  const latest = answers[answers.length - 1]?.result;
  const chips = hasSubmitted && !loading ? (latest?.follow_up_prompts ?? []) : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, minHeight: 'calc(100vh - 140px)', padding: hasSubmitted ? '16px 0 0' : '48px 24px' }}>
      {!hasSubmitted && (
        <div style={{ textAlign: 'center', margin: '0 auto', maxWidth: 680 }}>
          <h1 className="__s9cmpx-headline3" style={{ margin: '0 0 8px' }}>
            Ask about emissions and climate outcomes
          </h1>
          <p className="__s9cmpx-body3" style={{ margin: 0, color: 'var(--__s9cmpx-static-text-weak)' }}>
            Answers from emissions data for 1990–2024, global temperature and CO₂ records, and the platform&apos;s forecasts. Every chart shows its source.
          </p>
        </div>
      )}

      {hasSubmitted && (
        <>
          <div style={{ ...COLUMN, display: 'flex', justifyContent: 'flex-end' }}>
            <Button variant="ghost-blue" onClick={handleNewQuestion}>
              + New question
            </Button>
          </div>
          <div style={{ ...COLUMN, display: 'flex', flexDirection: 'column', gap: 36, flex: 1 }}>
            {answers.map((entry, index) => (
              <AnswerSection
                key={entry.id}
                ref={index === answers.length - 1 ? newestRef : undefined}
                query={entry.query}
                result={entry.result}
                showSuggestedPrompts={entry.result === result && !loading}
                onSuggestedPromptClick={prefillAndFocus}
              />
            ))}
            {loading && pendingQuery && <PendingAnswer query={pendingQuery} label={progress?.label ?? 'Thinking…'} percent={progress?.percent ?? 0} />}
            {error && pendingQuery && !loading && <FailedAnswer query={pendingQuery} message={error} onRetry={handleRetry} />}
          </div>
        </>
      )}

      <PromptBar
        ref={promptBarRef}
        value={value}
        onChange={setValue}
        onSubmit={handleSubmit}
        variant={hasSubmitted ? 'docked' : 'landing'}
        pinned={hasSubmitted}
        loading={loading}
        ariaLabel="Ask about climate emissions"
        placeholder={hasSubmitted ? 'Ask a follow-up…' : 'Ask about emissions, warming or pathways…'}
        hint={hasSubmitted ? undefined : 'Enter to send · Shift + Enter for a new line'}
        belowContent={hasSubmitted ? undefined : <StarterPromptColumns onSelect={prefillAndFocus} />}
        aboveContent={chips.length > 0 ? <FollowUpChips prompts={chips} onSelect={prefillAndFocus} /> : undefined}
      />
    </div>
  );
}
