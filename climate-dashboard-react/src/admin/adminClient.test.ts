import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminApi } from './adminClient';
import { ApiError } from '../api/types';

function mockFetchOnce(body: unknown, init: { ok?: boolean; status?: number; statusText?: string } = {}) {
  const { ok = true, status = 200, statusText = 'OK' } = init;
  const response = {
    ok,
    status,
    statusText,
    json: () => Promise.resolve(body),
  } as Response;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
  return response;
}

const CHOICE = { provider: 'anthropic', model: 'claude-sonnet-5', label: 'Claude Sonnet 5 (Anthropic)', updated_at: '2026-01-01T00:00:00+00:00' };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('adminApi', () => {
  it('getLlmChoice() fetches /agent/admin/llm with no body', async () => {
    mockFetchOnce(CHOICE);
    const result = await adminApi.getLlmChoice();
    expect(fetch).toHaveBeenCalledWith('/agent/admin/llm', undefined);
    expect(result).toEqual(CHOICE);
  });

  it('setLlmChoice() POSTs the id as a JSON body', async () => {
    mockFetchOnce(CHOICE);
    await adminApi.setLlmChoice('ollama-qwen14b-ctx8k');
    expect(fetch).toHaveBeenCalledWith('/agent/admin/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: 'ollama-qwen14b-ctx8k' }),
    });
  });

  it('throws ApiError with the response detail on a non-ok response', async () => {
    mockFetchOnce({ detail: 'Unknown LLM choice id.' }, { ok: false, status: 422 });
    await expect(adminApi.setLlmChoice('not-a-real-id')).rejects.toBeInstanceOf(ApiError);
    await expect(adminApi.setLlmChoice('not-a-real-id')).rejects.toMatchObject({ status: 422, message: 'Unknown LLM choice id.' });
  });

  it('falls back to statusText when the error response has no JSON body', async () => {
    const response = { ok: false, status: 502, statusText: 'Bad Gateway', json: () => Promise.reject(new Error('no body')) } as unknown as Response;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    await expect(adminApi.getLlmChoice()).rejects.toMatchObject({ status: 502, message: 'Bad Gateway' });
  });

  it('falls back to statusText, not a TypeError, when the error response body is a literal null', async () => {
    // res.json() legally resolves to null for a `null` JSON body -- it doesn't reject, so a
    // .catch()-only fallback wouldn't cover this; reading .detail off null would throw and mask
    // the real HTTP error entirely.
    mockFetchOnce(null, { ok: false, status: 503, statusText: 'Service Unavailable' });
    await expect(adminApi.getLlmChoice()).rejects.toMatchObject({ status: 503, message: 'Service Unavailable' });
  });
});
