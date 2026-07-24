from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..constants import FEATURED_COUNTRIES, GAS_COLUMNS
from ..data_loaders import DataNotFoundError, load_raw
from ..schemas import (
    DecadeGasShare,
    HistoricalDecadeCompositionResponse,
    HistoricalTimeseriesResponse,
    TimeseriesSeries,
)

router = APIRouter()

GasName = Literal["co2", "methane", "nitrous_oxide"]


@router.get("/historical/timeseries", response_model=HistoricalTimeseriesResponse)
def get_timeseries(
    countries: list[str] | None = Query(default=None),
    gas: GasName = "co2",
):
    try:
        df_raw = load_raw()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    # No expanded-country validation here (unlike country_profile.py) -- this endpoint
    # already accepts an arbitrary explicit `countries` list and silently omits any that
    # don't match, a pre-existing lenient convention this Release doesn't change.
    selected = countries if countries else FEATURED_COUNTRIES[:5]
    df_plot = df_raw[df_raw["country"].isin(selected)].dropna(subset=[gas])

    series = []
    for country in selected:
        d = df_plot[df_plot["country"] == country].sort_values("year")
        if d.empty:
            continue
        series.append(TimeseriesSeries(name=country, years=d["year"].tolist(), values=d[gas].tolist()))

    return HistoricalTimeseriesResponse(gas=gas, gas_label=GAS_COLUMNS[gas], series=series)


@router.get("/historical/decade-composition", response_model=HistoricalDecadeCompositionResponse)
def get_decade_composition():
    try:
        df_raw = load_raw()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    gas_cols_list = list(GAS_COLUMNS.keys())
    dg = df_raw.assign(decade=(df_raw["year"] // 10) * 10)
    agg = dg.groupby("decade")[gas_cols_list].sum()
    agg_pct = agg.div(agg.sum(axis=1), axis=0) * 100

    series = [
        DecadeGasShare(gas=gas, gas_label=GAS_COLUMNS[gas], share=agg_pct[gas].tolist())
        for gas in gas_cols_list
    ]

    return HistoricalDecadeCompositionResponse(decades=agg_pct.index.tolist(), series=series)
