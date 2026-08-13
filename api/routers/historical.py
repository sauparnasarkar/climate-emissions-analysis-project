from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import FEATURED_COUNTRIES, GAS_COLUMNS
from ..data_loaders import DataNotFoundError, load_raw, load_raw_sovereign
from ..schemas import (
    DecadeGasShare,
    HistoricalDecadeCompositionResponse,
    HistoricalTimeseriesResponse,
    TimeseriesSeries,
)

router = APIRouter()

GasName = Literal["co2", "methane", "nitrous_oxide"]
Scope = Literal["featured", "expanded", "sovereign"]


def _scoped_pool(scope: Scope) -> pd.DataFrame:
    if scope == "sovereign":
        return load_raw_sovereign()
    df = load_raw()
    return df[df["country"].isin(FEATURED_COUNTRIES)] if scope == "featured" else df


def _optional_floats(s: pd.Series) -> list[float | None]:
    """NaN-safe Series -> list[float | None] conversion (mirrors data_loaders.py's
    load_world_map_series pd.isna() idiom) -- a raw NaN isn't valid JSON, and
    dropna(subset=[gas]) below only guarantees the *primary* gas column is non-null per
    row, not per_capita/growth/per_gdp, which can be independently missing."""
    return [None if pd.isna(v) else float(v) for v in s]


@router.get("/historical/timeseries", response_model=HistoricalTimeseriesResponse)
def get_timeseries(
    countries: list[str] | None = Query(default=None),
    gas: GasName = "co2",
    scope: Scope = "expanded",
):
    try:
        df_raw = _scoped_pool(scope)
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    # No expanded-country validation here (unlike country_profile.py) -- this endpoint
    # already accepts an arbitrary explicit `countries` list and silently omits any that
    # don't match, a pre-existing lenient convention this Release doesn't change.
    selected = countries if countries else FEATURED_COUNTRIES
    df_plot = df_raw[df_raw["country"].isin(selected)].dropna(subset=[gas])

    per_capita_col = f"{gas}_per_capita"  # gas is Literal-validated (422 before reaching here);
    # the three GasName values match OWID's three per-capita column names exactly.

    series = []
    for country in selected:
        d = df_plot[df_plot["country"] == country].sort_values("year")
        if d.empty:
            continue
        n = len(d)
        series.append(
            TimeseriesSeries(
                name=country,
                years=d["year"].tolist(),
                values=d[gas].tolist(),
                per_capita=_optional_floats(d[per_capita_col]),
                yoy_pct_change=_optional_floats(d["co2_growth_prct"]) if gas == "co2" else [None] * n,
                per_gdp=_optional_floats(d["co2_per_gdp"]) if gas == "co2" else [None] * n,
            )
        )

    return HistoricalTimeseriesResponse(gas=gas, gas_label=GAS_COLUMNS[gas], series=series)


@router.get("/historical/decade-composition", response_model=HistoricalDecadeCompositionResponse)
def get_decade_composition(
    countries: list[str] | None = Query(default=None),
    scope: Scope = "expanded",
):
    try:
        df_raw = _scoped_pool(scope)
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    # No `countries` filter provided preserves this endpoint's original unfiltered-across-
    # all-countries behavior; callers that want a subset (e.g. the Historical Trends page's
    # own country picker) now get one, matching get_timeseries()'s pattern above.
    df_filtered = df_raw[df_raw["country"].isin(countries)] if countries else df_raw

    gas_cols_list = list(GAS_COLUMNS.keys())
    dg = df_filtered.assign(decade=(df_filtered["year"] // 10) * 10)
    agg = dg.groupby("decade")[gas_cols_list].sum()
    agg_pct = agg.div(agg.sum(axis=1), axis=0) * 100

    series = [
        DecadeGasShare(gas=gas, gas_label=GAS_COLUMNS[gas], share=agg_pct[gas].tolist())
        for gas in gas_cols_list
    ]

    return HistoricalDecadeCompositionResponse(decades=agg_pct.index.tolist(), series=series)
