import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useAgentStream } from './useAgentStream';

// fetchEventSource drives its callbacks itself over real network I/O -- these tests capture the
// options object each call passes and drive onopen/onmessage/onerror by hand, the same way
// api/client.test.ts stubs fetch rather than standing up a real server.
const fetchEventSourceMock = vi.fn();
vi.mock('@microsoft/fetch-event-source', () => ({
  fetchEventSource: (...args: unknown[]) => fetchEventSourceMock(...args),
}));

function lastCallOptions() {
  return fetchEventSourceMock.mock.calls[fetchEventSourceMock.mock.calls.length - 1][1];
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('useAgentStream', () => {
  it('posts to agent/query with the query and thread_id, and sets loading', () => {
    fetchEventSourceMock.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAgentStream());

    act(() => result.current.submit('top emitters?', 'thread-1'));

    expect(fetchEventSourceMock).toHaveBeenCalledWith(
      `${import.meta.env.BASE_URL}agent/query`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ query: 'top emitters?', thread_id: 'thread-1' }) }),
    );
    expect(result.current.loading).toBe(true);
  });

  it('accumulates progress events and resolves on a result event', async () => {
    fetchEventSourceMock.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAgentStream());
    act(() => result.current.submit('q', null));
    const options = lastCallOptions();

    await act(async () => options.onopen({ ok: true }));
    act(() => options.onmessage({ event: 'progress', data: JSON.stringify({ label: 'Fetching…', percent: 15 }) }));
    expect(result.current.progress).toEqual({ label: 'Fetching…', percent: 15 });
    expect(result.current.loading).toBe(true);

    const payload = { thread_id: 't1', widgets: [], response_text: 'done', scope_notes: [], suggested_prompts: [], percent: 100 };
    act(() => options.onmessage({ event: 'result', data: JSON.stringify(payload) }));

    expect(result.current.result).toEqual(payload);
    expect(result.current.loading).toBe(false);
  });

  it('surfaces an error event without throwing', () => {
    fetchEventSourceMock.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAgentStream());
    act(() => result.current.submit('q', null));
    const options = lastCallOptions();

    act(() => options.onmessage({ event: 'error', data: JSON.stringify({ message: 'graph failed' }) }));

    expect(result.current.error).toBe('graph failed');
    expect(result.current.loading).toBe(false);
  });

  it('onopen throws on a non-ok response, so fetchEventSource does not retry', async () => {
    fetchEventSourceMock.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAgentStream());
    act(() => result.current.submit('q', null));
    const options = lastCallOptions();

    await expect(options.onopen({ ok: false, status: 503, statusText: 'Service Unavailable', json: () => Promise.resolve({ detail: 'busy' }) })).rejects.toThrow(
      'busy',
    );
  });

  it('a stale in-flight stream cannot clobber a newer submit()', () => {
    fetchEventSourceMock.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAgentStream());
    act(() => result.current.submit('first', null));
    const firstOptions = lastCallOptions();

    act(() => result.current.submit('second', null));
    const secondOptions = lastCallOptions();

    // The first stream's onmessage fires late (after the second submit already started) --
    // its result must not land, since requestIdRef has already moved on.
    const stalePayload = { thread_id: 'stale', widgets: [], response_text: 'stale', scope_notes: [], suggested_prompts: [], percent: 100 };
    act(() => firstOptions.onmessage({ event: 'result', data: JSON.stringify(stalePayload) }));
    expect(result.current.result).toBeNull();

    const freshPayload = { thread_id: 'fresh', widgets: [], response_text: 'fresh', scope_notes: [], suggested_prompts: [], percent: 100 };
    act(() => secondOptions.onmessage({ event: 'result', data: JSON.stringify(freshPayload) }));
    expect(result.current.result).toEqual(freshPayload);
  });
});
