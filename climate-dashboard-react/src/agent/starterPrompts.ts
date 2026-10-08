import { toolNameFromSourceTaggedCall } from './types';
import type { WidgetSpec } from './types';

// The Ask page's starter prompts: three category columns, two prompts each (design handoff; ENHANCEMENTS.md decision 102). Clicking a card
// PREFILLS the input, it does not send. The Climate outcomes prompts are the owner's wording; the other four follow the handoff's copy.
export interface StarterColumn {
  label: string;
  /** Shown as a NEW tag beside the label, like the sidebar's NEW badge. */
  isNew?: boolean;
  prompts: string[];
}

export const STARTER_COLUMNS: StarterColumn[] = [
  {
    label: 'Historical trends',
    prompts: [
      "What are China's historical emissions trends, and how do they compare to the other top 10 emitters?",
      "How have India's emissions grown compared with other countries?",
    ],
  },
  {
    label: 'Climate outcomes',
    isNew: true,
    prompts: [
      'Show the relationship between cumulative emissions and warming.',
      'How do temperature outcomes vary based on different emissions pathways?',
    ],
  },
  {
    label: 'Forecasts',
    prompts: [
      'What are the top 10 forecasted emitters in 2040?',
      "How do today's top 10 emitters compare with the projected top 10 in 2040?",
    ],
  },
];

export const STARTER_PROMPTS: string[] = STARTER_COLUMNS.flatMap((c) => c.prompts);

const CLIMATE_TOOLS = new Set([
  'get_co2_concentration',
  'get_temperature_anomaly',
  'get_correlation_metadata',
  'get_emissions_temperature_relationship',
  'get_ghg_composition',
  'get_country_cumulative_share',
  'get_scenario_temperature',
]);
const FORECAST_TOOLS = new Set([
  'get_forecast',
  'get_forecast_comparison',
  'get_forecast_summary',
  'get_model_comparison',
  'get_scenario_projection',
  'get_scenario_cumulative_impact',
  'compare_scenarios_across_countries',
]);
// Answers that are text the model wrote, not data: they belong to no category.
const TEXT_ONLY = new Set(['general_climate', 'context_reuse', 'get_methodology_notes']);

/** The small category label above an answer's question: the starter column when the question IS a starter prompt, otherwise derived from the tools
 * that answered it (any climate-outcomes tool wins, then forecasts/scenarios, then everything else is a historical-trends answer); null when no data
 * tool answered (a guardrail reply or a text-only answer). */
export function categoryFor(query: string, widgets: WidgetSpec[]): string | null {
  const asked = query.trim();
  const starter = STARTER_COLUMNS.find((c) => c.prompts.includes(asked));
  if (starter) return starter.label;
  const tools = widgets.map((w) => toolNameFromSourceTaggedCall(w.source_tool_call)).filter((t) => !TEXT_ONLY.has(t));
  if (tools.length === 0) return null;
  if (tools.some((t) => CLIMATE_TOOLS.has(t))) return 'Climate outcomes';
  if (tools.some((t) => FORECAST_TOOLS.has(t))) return 'Forecasts';
  return 'Historical trends';
}
