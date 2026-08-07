"""Pydantic response models — one per endpoint shape."""

from typing import Literal, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class CountryValue(BaseModel):
    country: str
    value: Optional[float]


class WorldMapPoint(BaseModel):
    country: str
    # A couple of real OWID entries have no ISO-3 code (Kosovo, bare "Ryukyu Islands") --
    # Plotly's choropleth simply omits a location it can't place, no crash.
    iso_code: Optional[str]
    value: Optional[float]


class MoverRow(BaseModel):
    country: str
    co2_1990: Optional[float]
    co2_latest: Optional[float]
    absolute_change: Optional[float]
    pct_change: Optional[float]


class OverviewTierMetrics(BaseModel):
    label: Literal["All Countries", "Expanded", "Selected"]
    countries_count: int
    latest_year: int
    latest_co2_total: float
    co2_1990_total: float
    pct_change_since_1990: float
    # Per-year CO2 total, parallel to WorldMapTimeSeries.years (SPEC.md §5.17.5) -- lets the
    # Overview page's animated choropleth drive its KPI numbers from the same year the map is
    # currently showing, instead of a decorative 0-to-final count-up. Populated for All
    # Countries/Expanded only (see overview.py's _tier_metrics); Selected is summed client-side
    # from the same WorldMapTimeSeries payload instead, since it changes with the user's
    # country selection and re-fetching it per selection change would defeat the point of a
    # selection-invariant, fetch-once series endpoint.
    co2_by_year: list[float] = []


class OverviewResponse(BaseModel):
    all_countries: OverviewTierMetrics
    expanded_countries: OverviewTierMetrics
    selected: OverviewTierMetrics
    selected_country_list: list[str]
    latest_year_bar: list[CountryValue]
    top_movers: list[MoverRow]
    # Fixed top TOP_N_HEADLINE sovereign countries by latest-year CO2 -- always the same set
    # regardless of `countries`/Selected (SPEC.md §5.18.5), backing the Overview page's
    # always-on headline sentence. Sorted by co2_latest descending (biggest emitters first,
    # matching how the set itself was selected) -- deliberately NOT by pct_change like
    # top_movers; the frontend's buildHeadlineSentence derives every fact itself regardless of
    # input order, so this ordering is a response-shape clarity choice, not something frontend
    # correctness depends on.
    headline_movers: list[MoverRow]
    fastest_growth: MoverRow
    largest_reduction: MoverRow
    # Always every sovereign country's own latest year -- unfiltered, independent of
    # `countries`/Selected, matching the All Countries tier's own "never gets its own chart"
    # framing (the tier table already shows an aggregate; the map shows the full breakdown).
    world_map: list[WorldMapPoint]


class WorldMapTimeSeries(BaseModel):
    """SPEC.md §5.17.1 -- the animated choropleth's full 1990-2024 payload. Columnar (values
    indexed [yearIdx][countryIdx]), not a per-year list of WorldMapPoint objects: measured at
    8.3x smaller (50KB vs 414KB) for the full country x year grid, and it's the shape Plotly
    wants per animation frame, so the frontend does no reshaping. Selection-invariant --
    deliberately not part of OverviewResponse, which re-fetches on every country-selection
    change; this is fetched once and cached (see load_world_map_series)."""

    iso_codes: list[str]
    countries: list[str]  # parallel to iso_codes, for hover labels
    years: list[int]
    values: list[list[Optional[float]]]  # values[yearIdx][countryIdx], Mt CO2
    # Global min/max across ALL years, not just one -- load-bearing for SyChart's colorRange
    # prop, which must stay fixed across every animation frame or the color scale re-normalizes
    # per frame and hides real magnitude growth (SPEC.md §5.17.2). The minimum excludes exact
    # zero (see load_world_map_series): a handful of real entries (Antarctica) report literal
    # 0.0 co2, which log10 can't represent -- the floor here is the smallest genuinely positive
    # value, safe to pass straight through to a zLog-scaled colorRange without a null zmin.
    value_range: tuple[float, float]


class TimeseriesSeries(BaseModel):
    name: str
    years: list[int]
    values: list[Optional[float]]


class HistoricalTimeseriesResponse(BaseModel):
    gas: str
    gas_label: str
    series: list[TimeseriesSeries]


class DecadeGasShare(BaseModel):
    gas: str
    gas_label: str
    share: list[float]


class HistoricalDecadeCompositionResponse(BaseModel):
    decades: list[int]
    series: list[DecadeGasShare]


class CountryProfileTableRow(BaseModel):
    year: int
    co2: Optional[float]
    co2_per_capita: Optional[float]
    co2_yoy_pct_change: Optional[float]
    ghg_intensity: Optional[float]


class CountryProfileResponse(BaseModel):
    country: str
    years: list[int]
    co2: list[Optional[float]]
    co2_per_capita: list[Optional[float]]
    yoy_years: list[int]
    yoy_values: list[float]
    table: list[CountryProfileTableRow]


class ForecastCountryResponse(BaseModel):
    country: str
    hist_years: list[int]
    hist_co2: list[Optional[float]]
    holdout_years: list[int]
    holdout_co2: list[Optional[float]]
    forecast_years: list[int]
    forecast_mean: list[float]
    ci_upper: list[float]
    ci_lower: list[float]


class ForecastSummaryRow(BaseModel):
    country: str
    forecast_2030: Optional[float]
    forecast_2035: Optional[float]
    forecast_2040: Optional[float]
    actual_2020: Optional[float]
    pct_change_2020_2040: Optional[float]


class ForecastSummaryResponse(BaseModel):
    rows: list[ForecastSummaryRow]


class ModelComparisonResponse(BaseModel):
    columns: list[str]
    rows: list[dict]


class EtsParameterRow(BaseModel):
    country: str
    alpha: float
    beta_star: float
    phi: float


class EtsParametersResponse(BaseModel):
    rows: list[EtsParameterRow]


class FeatureImportanceRow(BaseModel):
    feature: str
    importance: float


class FeatureImportanceResponse(BaseModel):
    rows: list[FeatureImportanceRow]


class ScenarioSeries(BaseModel):
    name: str
    years: list[int]
    values: list[float]


class ScenarioTimeseriesResponse(BaseModel):
    title_suffix: str
    historical: Optional[ScenarioSeries]
    scenarios: list[ScenarioSeries]
    level_1990: Optional[float]


class ScenarioCumulativeRow(BaseModel):
    country: str
    values: dict[str, Optional[float]]
    # Per-scenario single-year 2040 value and the country's current/latest actual level --
    # `values` above is only ever a 2025-2040 sum, with no year-level or baseline figure the
    # frontend can compare a scenario's future trajectory against.
    year_2040: dict[str, Optional[float]]
    current_level: Optional[float]


class ScenarioCumulativeResponse(BaseModel):
    sort_by: str
    order: list[str]
    scenarios: list[str]
    rows: list[ScenarioCumulativeRow]


class ScenarioCompareResponse(BaseModel):
    countries: list[str]
    # One list of ScenarioSeries per scenario ("BAU"/"Moderate"/"Aggressive"); each list has
    # one series per requested country (name=country), historical (<=2019) concatenated with
    # that scenario's own 2020-2040 projection into a single continuous line -- not summed
    # across countries, unlike /scenarios/cumulative and the view=global /scenarios/timeseries.
    scenarios: dict[str, list[ScenarioSeries]]


class CountriesResponse(BaseModel):
    featured: list[str]
    expanded: list[str]


class ExplorerMetaResponse(BaseModel):
    countries: list[str]
    columns: list[str]
    year_min: int
    year_max: int


class ExplorerDataResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    total_rows: int
    page: int
    page_size: int
