import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AskThreadContext } from './askThread';
import type { AnswerEntry, AskThread } from './askThread';
import { useAgentStream } from './useAgentStream';
import type { AgentQueryResult } from './types';

/**
 * Holds the Ask page's conversation above the routes, so leaving the page (a deep link, the sidebar) and coming back finds the thread as it was:
 * the answers, the thread id, a question still in flight (it keeps streaming, and lands while the user is elsewhere) and the half-typed input.
 * In memory only -- a browser reload starts a fresh thread (ENHANCEMENTS.md "Step 3.5d-2").
 */
export function AskThreadProvider({ children }: { children: ReactNode }) {
  const { submit: streamSubmit, progress, result, error, loading, reset } = useAgentStream();
  const [value, setValue] = useState('');
  const [answers, setAnswers] = useState<AnswerEntry[]>([]);
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const threadIdRef = useRef<string | null>(null);
  // Identity-compared against the hook's own `result`, not a "have we consumed this yet" flag: useAgentStream returns a fresh object per submit()
  // and holds it steady across re-renders in between, so this is the correct signal for "a new result just arrived".
  const lastResultRef = useRef<AgentQueryResult | null>(null);
  const nextIdRef = useRef(0);
  const scrollYRef = useRef(0);

  const submit = useCallback(
    (query: string) => {
      setPendingQuery(query);
      streamSubmit(query, threadIdRef.current);
      setValue('');
    },
    [streamSubmit],
  );

  useEffect(() => {
    if (!result || result === lastResultRef.current) return;
    lastResultRef.current = result;
    threadIdRef.current = result.thread_id;
    const id = nextIdRef.current++;
    // pendingQuery is a dependency for freshness, not as a second trigger: the effect only *acts* when `result` is new (the guard above). Including it
    // makes sure the closure reads the latest submitted query on the rapid-second-submit path where pendingQuery updates slightly ahead of the result.
    setAnswers((prev) => [...prev, { id, query: pendingQuery ?? '', result }]);
  }, [result, pendingQuery]);

  // The field is cleared on submit; if the question then fails, put the text back so it is not lost (design handoff: "the input keeps the text").
  useEffect(() => {
    if (error && pendingQuery) setValue((current) => current || pendingQuery);
  }, [error, pendingQuery]);

  const retry = useCallback(() => {
    if (!pendingQuery) return;
    streamSubmit(pendingQuery, threadIdRef.current);
    setValue('');
  }, [pendingQuery, streamSubmit]);

  const newQuestion = useCallback(() => {
    reset();
    setAnswers([]);
    setPendingQuery(null);
    threadIdRef.current = null;
    lastResultRef.current = null;
    setValue('');
  }, [reset]);

  const thread = useMemo<AskThread>(
    () => ({ answers, pendingQuery, value, setValue, submit, retry, newQuestion, scrollYRef, progress, result, error, loading }),
    [answers, pendingQuery, value, submit, retry, newQuestion, progress, result, error, loading],
  );
  return <AskThreadContext.Provider value={thread}>{children}</AskThreadContext.Provider>;
}
