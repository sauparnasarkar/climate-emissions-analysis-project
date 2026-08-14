// Mirrors services/agent/src/agent/state.py's WidgetSpec and server.py's stream_query result
// payload exactly (SPEC.md §5/§7) -- these are the wire shapes, not independently designed.

export type WidgetIntent = 'chart' | 'grid' | 'card' | 'text'
export type ChartKind = 'line' | 'bar' | 'band' | 'choropleth'

export interface WidgetSpec {
  intent: WidgetIntent
  chart_kind?: ChartKind | null
  title: string
  as_of?: string | null
  // source_tool_call is `${tool_name}:${json.dumps(args, sort_keys=True)}` (cache.py's
  // cache_key) -- no real tool name contains a colon, so splitting on the first one recovers it.
  source_tool_call: string
  props: Record<string, unknown>
}

export interface AgentQueryResult {
  thread_id: string
  widgets: WidgetSpec[]
  response_text: string
  scope_notes: string[]
  suggested_prompts: string[]
  percent: number
}

export interface AgentProgress {
  label: string
  percent: number
}

export interface AgentStreamError {
  message: string
}

export function toolNameFromSourceTaggedCall(sourceTaggedCall: string): string {
  const colonIndex = sourceTaggedCall.indexOf(':')
  return colonIndex === -1 ? sourceTaggedCall : sourceTaggedCall.slice(0, colonIndex)
}
