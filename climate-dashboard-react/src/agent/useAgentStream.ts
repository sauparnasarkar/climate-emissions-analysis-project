import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { AgentProgress, AgentQueryResult, AgentStreamError } from './types';

// Thrown from onopen to make fetchEventSource stop retrying -- this is a single POST/response
// query-response exchange (SPEC.md §5), not a long-lived subscription the library's own
// indefinite-retry-on-error default is meant for. Any subclass of Error thrown from onopen or
// onmessage is fatal (no retry); returning from onerror (rather than throwing) is what would
// schedule a retry instead, so this module never does that.
class FatalStreamError extends Error {}

export interface UseAgentStreamResult {
  submit: (query: string, threadId: string | null) => void;
  progress: AgentProgress | null;
  result: AgentQueryResult | null;
  error: string | null;
  loading: boolean;
  reset: () => void;
}

// AgentPage's own SSE client for services/agent's POST /query (server.py's stream_query) --
// api/'s existing useAsync hook doesn't fit here since it wraps a single resolved Promise<T>,
// not a stream of progress events followed by one terminal result/error event. Native
// EventSource is GET-only and can't carry a POST body, hence @microsoft/fetch-event-source.
export function useAgentStream(): UseAgentStreamResult {
  const [progress, setProgress] = useState<AgentProgress | null>(null);
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Guards against a stale in-flight stream's events landing after a newer submit() call or
  // unmount -- same cancellation-guard discipline as hooks/useAsync.ts's `cancelled` closure.
  const requestIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setProgress(null);
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  const submit = useCallback((query: string, threadId: string | null) => {
    abortControllerRef.current?.abort();
    const requestId = ++requestIdRef.current;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setProgress(null);
    setResult(null);
    setError(null);
    setLoading(true);

    const isCurrent = () => requestIdRef.current === requestId;

    fetchEventSource(`${import.meta.env.BASE_URL}agent/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ query, thread_id: threadId }),
      signal: controller.signal,
      openWhenHidden: true,
      async onopen(response) {
        if (!response.ok) {
          const body = await response.json().catch(() => ({ detail: response.statusText }));
          throw new FatalStreamError(body.detail ?? response.statusText);
        }
      },
      onmessage(ev) {
        if (!isCurrent()) return;
        if (ev.event === 'progress') {
          setProgress(JSON.parse(ev.data) as AgentProgress);
        } else if (ev.event === 'result') {
          setResult(JSON.parse(ev.data) as AgentQueryResult);
          setLoading(false);
        } else if (ev.event === 'error') {
          setError((JSON.parse(ev.data) as AgentStreamError).message);
          setLoading(false);
        }
      },
      onerror(err) {
        // Returning nothing/undefined from onerror would schedule a retry; throwing here (and
        // for every other error path in this call) is what stops it -- this hook always wants
        // exactly one attempt per submit(), matching services/agent's own non-idempotent query
        // semantics (a retried POST could double a real MCP tool call).
        if (isCurrent()) setError(err instanceof Error ? err.message : 'Connection to the agent failed.');
        throw err instanceof Error ? err : new FatalStreamError(String(err));
      },
    }).catch(() => {
      // onerror above already recorded a message; this only prevents an unhandled promise
      // rejection from the throw inside it (fetchEventSource re-throws whatever onerror threw).
      if (isCurrent()) setLoading(false);
    });
  }, []);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  return { submit, progress, result, error, loading, reset };
}
