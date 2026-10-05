import type { CorrelationScenarioTemperatureResponse } from '../api/correlationTypes';

const row = (year: number, mt: number, level: number) => ({ year, covered_mt: mt * 0.89, rest_of_world_mt: mt * 0.11, global_fossil_mt: mt, land_use_mt: 4658, headline: { delta_t_c: level - 1.39, level_c: level }, fossil_only: { delta_t_c: 0, level_c: level } });

/** A /scenario-temperature response shaped like the real one (2025 and 2040 rows per scenario, spread facts, 40 covered countries). */
export const SCENARIO_TEMPERATURE = {
  schema_version: 1, generated_at: null, note: '', caveats: [], attribution: [], source_vintage: null,
  name: 'Scenario temperature translation', method: 'm', labels: [], line: 'both', selected_scenarios: ['BAU', 'Moderate', 'Aggressive'],
  scenarios: {
    BAU: [row(2025, 38953, 1.41), row(2040, 44877, 1.78)],
    Moderate: [row(2025, 38953, 1.41), row(2040, 33145, 1.73)],
    Aggressive: [row(2025, 38953, 1.41), row(2040, 20791, 1.67)],
  },
  assumptions: { rest_of_world: { share: 0.1068, year: 2024 } }, base: { last_observed_year: 2024, first_scenario_year_vs_last_observed_pct: { BAU: 0.9185, Moderate: 0.9185, Aggressive: 0.9185 } }, covered_countries: Array.from({ length: 40 }, (_, i) => ({ country: `C${i}`, co2_mt_last_observed_year: 1 })),
  scenario_source: null,
  spread: { per_year: [], min_ratio_for_reading_note: 1.25, reading_note_omitted_reason: null, reading_note_facts: { year: 2040, highest: 'BAU', lowest: 'Aggressive', emissions_ratio: 2.15847, already_observed_pct_range: [78.2, 83.2], gap_end_c: 0.107207 } },
  reading_note: 'long note', notes: [],
} as unknown as CorrelationScenarioTemperatureResponse;
