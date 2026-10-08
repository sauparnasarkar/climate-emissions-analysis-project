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
  // Answer-block fields (services/agent SPEC.md §15.11). Optional: an older agent build does not send them.
  /** The "Source: ..." line under the chart. */
  source_line?: string | null
  /** The scenario answer's warning chip text. */
  badge?: string | null
  /** The widget's key figures (what the lead quotes). */
  summary?: Record<string, unknown> | null
}

/** One card of an answer's KPI row; `value` is a number, formatted by the card. */
export interface Kpi {
  label: string
  value: number
  unit: string
  decimals: number
  /** The data year the card is labelled with. */
  year: number | null
  sub: string | null
  /** A scenario name (BAU / Moderate / Aggressive), so the card takes that series' colour. */
  series: string | null
}

/** A real in-app navigation link (route may carry ?query and #anchor), distinct from a follow-up prompt. */
export interface FollowUpLink {
  label: string
  route: string
}

export interface AgentQueryResult {
  thread_id: string
  widgets: WidgetSpec[]
  response_text: string
  scope_notes: string[]
  suggested_prompts: string[]
  // Answer blocks (services/agent SPEC.md §15.11); optional so a response from an older agent still parses.
  kpis?: Kpi[]
  follow_up_links?: FollowUpLink[]
  /** Prompt chips for the docked input: prompts, not links. */
  follow_up_prompts?: string[]
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
