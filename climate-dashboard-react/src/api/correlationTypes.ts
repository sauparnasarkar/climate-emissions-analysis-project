// Hand-written mirrors of api/schemas_correlation.py (ENHANCEMENTS.md Release 21, decisions 46-53).
// The endpoints return a common envelope plus a per-resource body; free-form blocks that the
// pipeline owns (fit, details, sources...) stay loosely typed here and are narrowed by the page
// that reads them, so a pipeline-side addition never breaks this file.

export interface CorrelationEnvelope {
  schema_version: number;
  generated_at: string | null;
  note: string;
  caveats: string[];
  attribution: Array<Record<string, unknown>>;
  source_vintage: Record<string, unknown> | null;
}

export interface IndicatorInfo {
  id: string;
  name: string;
  unit: string;
  kind: string;
  decimals: number | null;
  description: string | null;
}

export interface SeriesPoint {
  year: number;
  month: number | null;
  value: number | null;
  uncertainty: number | null;
  deseasonalized: number | null;
}

/** Shared by /concentration and /temperature. */
export interface CorrelationSeriesResponse extends CorrelationEnvelope {
  indicator: IndicatorInfo;
  view: string;
  baseline: string | null;
  resolution: string;
  start_year: number | null;
  end_year: number | null;
  coverage: number[] | null;
  points: SeriesPoint[];
  notes: string[];
  details: Record<string, unknown>;
}
export type CorrelationConcentrationResponse = CorrelationSeriesResponse;
export type CorrelationTemperatureResponse = CorrelationSeriesResponse;

export interface CorrelationMetaResponse extends CorrelationEnvelope {
  sources: Array<Record<string, unknown>>;
  baselines: Record<string, unknown>;
  temperature_offset: Record<string, unknown> | null;
  two_global_totals: string;
  source_baseline_matrix: Array<Record<string, unknown>>;
  indicators: Array<Record<string, unknown>>;
  outputs: Record<string, Record<string, unknown>>;
  pipeline_last_run: Record<string, unknown> | null;
  endpoints: string[];
  freshness: Record<string, unknown>;
}

export interface PairPoint {
  year: number;
  cumulative_emissions: number;
  temperature: number;
}

export interface OmittedYear {
  year: number;
  reason: string;
}

export interface CorrelationEmissionsTemperatureResponse extends CorrelationEnvelope {
  source: string;
  variant: string | null;
  baseline: string;
  window: number[];
  x: IndicatorInfo;
  y: IndicatorInfo;
  n_years: number;
  points: PairPoint[];
  omitted_years: OmittedYear[];
  fit: Record<string, unknown> | null;
  fit_context: Record<string, unknown>;
  warnings: string[];
  notes: string[];
}

export interface GasValue {
  gas: string;
  name: string;
  mtco2e: number | null;
  share_pct: number | null;
}

export interface CompositionYear {
  year: number;
  gases_included: string[];
  components_total_mtco2e: number | null;
  national_total_mtco2e: number | null;
  residual_pct: number | null;
  values: GasValue[];
}

export interface CorrelationGhgCompositionResponse extends CorrelationEnvelope {
  name: string;
  basis: string;
  units: string;
  gases: Array<Record<string, unknown>>;
  coverage: number[] | null;
  start_year: number | null;
  end_year: number | null;
  year: number | null;
  years: CompositionYear[];
  reconciliation: Record<string, unknown> | null;
  excluded_incomplete_years: number[];
  notes: string[];
}

export interface ShareRow {
  rank: number;
  country: string;
  name: string;
  cumulative_mt: number;
  share_pct: number;
  /** The year's own emissions and share of the national sum; null when the pipeline output predates them (decision 60). */
  annual_mt: number | null;
  annual_share_pct: number | null;
}

export interface SharePoint {
  year: number;
  cumulative_mt: number;
  share_pct: number;
  annual_mt: number | null;
  annual_share_pct: number | null;
}

export interface ShareSeries {
  country: string;
  name: string;
  points: SharePoint[];
}

export interface CorrelationCountryShareResponse extends CorrelationEnvelope {
  name: string;
  method: string;
  source: string;
  gas_scope: string;
  label: string;
  unit: string;
  mode: string;
  year: number | null;
  limit: number | null;
  start_year: number | null;
  end_year: number | null;
  coverage: number[] | null;
  cumulative_from: number | null;
  total_cumulative_mt: number | null;
  annual_total_mt: number | null;
  rows: ShareRow[];
  series: ShareSeries[];
  denominator: Record<string, unknown> | null;
  reconciliation: Record<string, unknown> | null;
  details: Record<string, unknown>;
  notes: string[];
}

export interface CorrelationScenarioTemperatureResponse extends CorrelationEnvelope {
  name: string;
  method: string;
  labels: string[];
  line: string;
  selected_scenarios: string[];
  scenarios: Record<string, Array<Record<string, unknown>>>;
  assumptions: Record<string, unknown>;
  base: Record<string, unknown>;
  covered_countries: Array<Record<string, unknown>>;
  scenario_source: Record<string, unknown> | null;
  spread: Record<string, unknown> | null;
  reading_note: string | null;
  notes: string[];
}

// Query-parameter vocabularies, mirroring the Literals in api/routers/correlation.py.
export type ConcentrationView = 'level' | 'yoy_pct' | 'mean5y' | 'index';
export type IndexBaseline = 'preindustrial' | '1970' | '1990';
export type SeriesResolution = 'annual' | 'monthly';
export type TemperatureView = 'level' | 'mean5y';
export type TemperatureBaseline = '1850_1900' | '1951_1980';
export type PairSource = 'owid_co2' | 'primap_ghg';
export type PairVariant = 'total' | 'fossil';
export type ScenarioName = 'BAU' | 'Moderate' | 'Aggressive';
export type ScenarioLine = 'both' | 'headline' | 'fossil_only';
