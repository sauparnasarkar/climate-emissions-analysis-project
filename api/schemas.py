"""Pydantic response models — one per endpoint shape."""

from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class CountryValue(BaseModel):
    country: str
    value: Optional[float]


class MoverRow(BaseModel):
    country: str
    co2_1990: Optional[float]
    co2_latest: Optional[float]
    absolute_change: Optional[float]
    pct_change: Optional[float]


class OverviewResponse(BaseModel):
    latest_year: int
    latest_co2_total: float
    co2_1990_total: float
    pct_change_since_1990: float
    countries_count: int
    focus_countries: list[str]
    latest_year_bar: list[CountryValue]
    top_movers: list[MoverRow]
    fastest_growth: MoverRow
    largest_reduction: MoverRow


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


class ScenarioCumulativeResponse(BaseModel):
    sort_by: str
    order: list[str]
    scenarios: list[str]
    rows: list[ScenarioCumulativeRow]
