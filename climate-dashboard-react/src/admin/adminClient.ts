import { ApiError } from '../api/types';
import type { LlmChoice } from './types';

// Sibling to agent/useAgentStream.ts rather than folded into api/client.ts -- this targets
// services/agent's own backend (port 8766 in dev), not api/, and reuses the same
// agentProxyEntry Vite proxy useAgentStream.ts already relies on (vite.config.ts), so no
// proxy config change is needed for this to work in dev or prod.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}agent${path}`, init);
  if (!res.ok) {
    // res.json() can legally resolve to null (or any other non-object JSON value) without
    // rejecting -- e.g. a literal `null` body -- so `.catch()` alone doesn't cover every
    // shape. Guard the property access itself rather than assuming a parsed body is an object.
    const body: unknown = await res.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail?: unknown }).detail : undefined;
    throw new ApiError(res.status, typeof detail === 'string' ? detail : res.statusText);
  }
  return res.json() as Promise<T>;
}

export const adminApi = {
  getLlmChoice: () => request<LlmChoice>('/admin/llm'),

  setLlmChoice: (id: string) =>
    request<LlmChoice>('/admin/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    }),
};
