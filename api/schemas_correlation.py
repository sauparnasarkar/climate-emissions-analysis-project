"""Response models for `/api/correlation/*` (ENHANCEMENTS.md Release 21, decisions 46-53). Kept apart from `schemas.py`, which covers the dashboard endpoints.

Every response carries the common envelope (decision 46) so licence, attribution and the interpretive-context note travel with the numbers.
"""

from typing import Any

from pydantic import BaseModel


class CorrelationEnvelope(BaseModel):
    schema_version: int = 1
    generated_at: str | None = None
    note: str
    caveats: list[str] = []
    attribution: list[dict[str, Any]] = []
    source_vintage: dict[str, Any] | None = None


class IndicatorInfo(BaseModel):
    id: str
    name: str
    unit: str
    kind: str
    decimals: int | None = None
    description: str | None = None


class SeriesPoint(BaseModel):
    year: int
    month: int | None = None
    value: float | None = None
    uncertainty: float | None = None
    deseasonalized: float | None = None


class CorrelationSeriesResponse(CorrelationEnvelope):
    """Shared by /concentration and /temperature."""

    indicator: IndicatorInfo
    view: str
    baseline: str | None = None
    resolution: str = "annual"
    start_year: int | None = None
    end_year: int | None = None
    coverage: list[int] | None = None
    points: list[SeriesPoint]
    notes: list[str] = []
    details: dict[str, Any] = {}


CorrelationConcentrationResponse = CorrelationSeriesResponse
CorrelationTemperatureResponse = CorrelationSeriesResponse


class CorrelationMetaResponse(CorrelationEnvelope):
    sources: list[dict[str, Any]]
    baselines: dict[str, Any]
    temperature_offset: dict[str, Any] | None = None
    two_global_totals: str
    source_baseline_matrix: list[dict[str, Any]]
    indicators: list[dict[str, Any]]
    outputs: dict[str, dict[str, Any]]
    pipeline_last_run: dict[str, Any] | None = None
    endpoints: list[str]
