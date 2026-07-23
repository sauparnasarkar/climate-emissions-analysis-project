// Hand-written mirrors of api/schemas.py — one interface per response shape.

export interface CountryValue {
  country: string;
  value: number | null;
}

export interface MoverRow {
  country: string;
  co2_1990: number | null;
  co2_latest: number | null;
  absolute_change: number | null;
  pct_change: number | null;
}

export interface OverviewResponse {
  latest_year: number;
  latest_co2_total: number;
  co2_1990_total: number;
  pct_change_since_1990: number;
  countries_count: number;
  focus_countries: string[];
  latest_year_bar: CountryValue[];
  top_movers: MoverRow[];
  fastest_growth: MoverRow;
  largest_reduction: MoverRow;
}

export interface TimeseriesSeries {
  name: string;
  years: number[];
  values: Array<number | null>;
}

export interface HistoricalTimeseriesResponse {
  gas: string;
  gas_label: string;
  series: TimeseriesSeries[];
}

export interface DecadeGasShare {
  gas: string;
  gas_label: string;
  share: number[];
}

export interface HistoricalDecadeCompositionResponse {
  decades: number[];
  series: DecadeGasShare[];
}

export interface CountryProfileTableRow {
  year: number;
  co2: number | null;
  co2_per_capita: number | null;
  co2_yoy_pct_change: number | null;
  ghg_intensity: number | null;
}

export interface CountryProfileResponse {
  country: string;
  years: number[];
  co2: Array<number | null>;
  co2_per_capita: Array<number | null>;
  yoy_years: number[];
  yoy_values: number[];
  table: CountryProfileTableRow[];
}

export interface ForecastCountryResponse {
  country: string;
  hist_years: number[];
  hist_co2: Array<number | null>;
  holdout_years: number[];
  holdout_co2: Array<number | null>;
  forecast_years: number[];
  forecast_mean: number[];
  ci_upper: number[];
  ci_lower: number[];
}

export interface ForecastSummaryRow {
  country: string;
  forecast_2030: number | null;
  forecast_2035: number | null;
  forecast_2040: number | null;
  actual_2020: number | null;
  pct_change_2020_2040: number | null;
}

export interface ForecastSummaryResponse {
  rows: ForecastSummaryRow[];
}

export interface ModelComparisonResponse {
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface EtsParameterRow {
  country: string;
  alpha: number;
  beta_star: number;
  phi: number;
}

export interface EtsParametersResponse {
  rows: EtsParameterRow[];
}

export interface FeatureImportanceRow {
  feature: string;
  importance: number;
}

export interface FeatureImportanceResponse {
  rows: FeatureImportanceRow[];
}

export interface ScenarioSeries {
  name: string;
  years: number[];
  values: number[];
}

export interface ScenarioTimeseriesResponse {
  title_suffix: string;
  historical: ScenarioSeries | null;
  scenarios: ScenarioSeries[];
  level_1990: number | null;
}

export interface ScenarioCumulativeRow {
  country: string;
  values: Record<string, number | null>;
}

export interface ScenarioCumulativeResponse {
  sort_by: string;
  order: string[];
  scenarios: string[];
  rows: ScenarioCumulativeRow[];
}

export interface ExplorerMetaResponse {
  countries: string[];
  columns: string[];
  year_min: number;
  year_max: number;
}

export interface ExplorerDataResponse {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  total_rows: number;
  page: number;
  page_size: number;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
