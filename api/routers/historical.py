import math
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import FEATURED_COUNTRIES, GAS_COLUMNS, PCT_CHANGE_BASELINE_YEAR
from ..data_loaders import DataNotFoundError, load_raw, load_raw_sovereign
from ..schemas import (
    DecadeGasShare,
    EmissionsChangeSummaryResponse,
    HistoricalDecadeCompositionResponse,
    HistoricalTimeseriesResponse,
    MoverRow,
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


@router.get("/historical/change-summary", response_model=EmissionsChangeSummaryResponse)
def get_change_summary(scope: Scope = "sovereign", top_n: int = Query(default=10, ge=1, le=25)):
    """How many countries increased vs. decreased CO2 emissions between PCT_CHANGE_BASELINE_YEAR
    and the latest year, plus the biggest movers in each direction. Unlike overview.py's
    `top_movers` (capped at MAX_SELECTED_COUNTRIES=10 via its `countries` param), this ranks
    across the full `scope` pool and reduces server-side to counts + a bounded top-N per
    direction -- response size never scales with scope size. Defaults to `sovereign`
    (diverges from every sibling endpoint's `expanded` default) since "how many countries"
    means the real global count, not a curated subset.
    """
    try:
        df = _scoped_pool(scope)
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    baseline_year = PCT_CHANGE_BASELINE_YEAR
    latest_year = int(df["year"].max())
    pool_size = int(df["country"].nunique())

    baseline = df[df["year"] == baseline_year].set_index("country")["co2"]
    latest = df[df["year"] == latest_year].set_index("country")["co2"]
    absolute_change = latest - baseline
    pct_change = absolute_change / baseline * 100

    changes = pd.DataFrame({
        "co2_1990": baseline,
        "co2_latest": latest,
        "absolute_change": absolute_change,
        "pct_change": pct_change,
    }).dropna(subset=["co2_1990", "co2_latest", "absolute_change"])
    # A zero baseline (co2_1990 == 0) makes pct_change +/-inf, which dropna() does NOT catch
    # (it only drops NaN) and which json.dumps can't serialize. No sovereign country has
    # co2==0 at 1990 in today's real data, but 52 rows elsewhere in the same dataset do have
    # co2==0 (e.g. Antarctica -- see WorldMapPoint's own docstring), and this repo runs a
    # weekly automated data refresh, so a future refresh could introduce one. absolute_change
    # stays finite and meaningful even from a zero baseline (0 -> 50 Mt is a real increase),
    # so null out just pct_change for that row rather than dropping the country from the
    # count/ranking entirely -- MoverRow.pct_change is already Optional for exactly this gap.
    changes = changes.assign(pct_change=changes["pct_change"].apply(lambda v: v if math.isfinite(v) else None))

    increased = changes[changes["absolute_change"] > 0]
    decreased = changes[changes["absolute_change"] < 0]
    unchanged = changes[changes["absolute_change"] == 0]

    def _rows(d: pd.DataFrame, ascending: bool) -> list[MoverRow]:
        ranked = d.sort_values("absolute_change", ascending=ascending).head(top_n)
        return [MoverRow(country=country, **row) for country, row in ranked.iterrows()]

    return EmissionsChangeSummaryResponse(
        scope=scope,
        baseline_year=baseline_year,
        latest_year=latest_year,
        country_pool_size=pool_size,
        countries_with_data=len(changes),
        increased_count=len(increased),
        decreased_count=len(decreased),
        unchanged_count=len(unchanged),
        top_increases=_rows(increased, ascending=False),
        top_decreases=_rows(decreased, ascending=True),
    )
