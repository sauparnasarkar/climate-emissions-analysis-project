import { useEffect, useId, useLayoutEffect, useRef } from 'react';
import { Button, InlineAlert, Progress, PromptBar, useReducedMotion } from 'design-system';
import { AnswerSection, QuestionHeading } from '../agent/AnswerSection';
import { AnswerSkeleton } from '../agent/AnswerSkeleton';
import { FollowUpChips } from '../agent/FollowUpChips';
import { StarterPromptColumns } from '../agent/StarterPromptColumns';
import { categoryFor } from '../agent/starterPrompts';
import { useAskThread } from '../agent/askThread';

// The Ask the Agent page (design handoff `design/ask-the-agent/`; ENHANCEMENTS.md decisions 102-109 and "Step 3.5d-2").
// Landing: a title, the input with its hint, and three columns of starter prompts under it. After the first question the input is pinned to the
// bottom with follow-up chips above it, and the answers stack above it in the order they were asked (the newest scrolls into view).

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
  // The conversation lives in AskThreadProvider (above the routes), so it survives navigating away and back.
  const { answers, pendingQuery, value, setValue, submit, retry, newQuestion, scrollYRef, progress, result, error, loading } = useAskThread();
  const promptBarRef = useRef<HTMLTextAreaElement>(null);
  const newestRef = useRef<HTMLElement | null>(null);
  const reduceMotion = useReducedMotion();

  const hasSubmitted = answers.length > 0 || loading || error != null;

  // Coming back to a thread: put the page where it was left, and leave the position alone (below) rather than scrolling to the newest answer.
  useLayoutEffect(() => {
    if (scrollYRef.current > 0) window.scrollTo?.(0, scrollYRef.current);
    return () => {
      scrollYRef.current = window.scrollY;
    };
  }, [scrollYRef]);

  // A NEW answer scrolls into view (the input is pinned below, so the newest answer is the last one). Instant under reduced motion; jsdom has no
  // scrollIntoView, hence the optional call. Answers already there when the page opened do not count as new.
  const answerCount = answers.length;
  const seenCountRef = useRef(answerCount);
  useEffect(() => {
    if (answerCount === seenCountRef.current) return;
    seenCountRef.current = answerCount;
    if (answerCount > 0) newestRef.current?.scrollIntoView?.({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  }, [answerCount, reduceMotion]);

  // Prefill + focus, shared by the starter cards, the follow-up chips and the "Try instead" tiles: one behaviour for every prompt the page offers
  // (ENHANCEMENTS.md decision 102). The user lands in the textarea with the prompt ready to edit or send.
  const prefillAndFocus = (prompt: string) => {
    setValue(prompt);
    promptBarRef.current?.focus();
  };

  const handleSubmit = submit;
  const handleRetry = retry;
  const handleNewQuestion = newQuestion;

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
