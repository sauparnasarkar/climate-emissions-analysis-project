// Mirrors services/agent/src/agent/server.py's LlmChoiceResponse -- SPEC.md §14.4.
export interface LlmChoice {
  provider: string;
  model: string;
  label: string;
  updated_at: string;
}
