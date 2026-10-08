import { createContext, useContext } from 'react';
import type { UseAgentStreamResult } from './useAgentStream';
import type { AgentQueryResult } from './types';

export interface AnswerEntry {
  id: number;
  query: string;
  result: AgentQueryResult;
}

export interface AskThread {
  answers: AnswerEntry[];
  pendingQuery: string | null;
  /** The input's text -- kept with the thread so a half-typed question survives leaving the page too. */
  value: string;
  setValue: (value: string) => void;
  submit: (query: string) => void;
  retry: () => void;
  newQuestion: () => void;
  /** The window scroll position when the Ask page was last left, restored when it is opened again. */
  scrollYRef: { current: number };
  progress: UseAgentStreamResult['progress'];
  /** The stream's current result: identity-compared by the page to know which answer is the live one. */
  result: UseAgentStreamResult['result'];
  error: UseAgentStreamResult['error'];
  loading: UseAgentStreamResult['loading'];
}

export const AskThreadContext = createContext<AskThread | null>(null);

export function useAskThread(): AskThread {
  const thread = useContext(AskThreadContext);
  if (!thread) throw new Error('useAskThread must be used inside AskThreadProvider');
  return thread;
}
