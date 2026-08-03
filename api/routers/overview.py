import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import (
    FEATURED_COUNTRIES,
    MAX_SELECTED_COUNTRIES,
    PCT_CHANGE_BASELINE_YEAR,
    WORLD_MAP_YEAR_END,
    WORLD_MAP_YEAR_START,
)
from ..data_loaders import (
    DataNotFoundError,
    load_expanded_countries,
    load_features,
    load_raw_sovereign,
    load_world_map_series,
)
from ..schemas import CountryValue, MoverRow, OverviewResponse, OverviewTierMetrics, WorldMapPoint, WorldMapTimeSeries

router = APIRouter()


def _tier_metrics(df: pd.DataFrame, label: str, countries_count: int, include_yearly: bool = False) -> OverviewTierMetrics:
    latest_year = int(df["year"].max())
    latest_total = float(df[df["year"] == latest_year]["co2"].sum())
    base_total = float(df[df["year"] == PCT_CHANGE_BASELINE_YEAR]["co2"].sum())
    # A single user-selected country (now possible via `countries`) may have no 1990 row at
    # all -- guard the same way MoverRow's per-country pct_change already tolerates missing
    # baselines, rather than 500ing on a division by zero.
    pct_change = (latest_total - base_total) / base_total * 100 if base_total else 0.0
    # Only computed for All Countries/Expanded (SPEC.md §5.17.5) -- Selected is summed
    # client-side from the same WorldMapTimeSeries payload the frontend already holds, since
    # re-deriving it here would need to run once per selection change for no benefit.
    co2_by_year: list[float] = []
    if include_yearly:
        by_year = df.groupby("year")["co2"].sum()
        co2_by_year = [
            float(by_year.get(year, 0.0)) for year in range(WORLD_MAP_YEAR_START, WORLD_MAP_YEAR_END + 1)
        ]
    return OverviewTierMetrics(
        label=label,
        countries_count=countries_count,
        latest_year=latest_year,
        latest_co2_total=latest_total,
        co2_1990_total=base_total,
        pct_change_since_1990=pct_change,
        co2_by_year=co2_by_year,
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(countries: list[str] | None = Query(None)):
    expanded = load_expanded_countries()

    # Cap/unknown-country validation only applies to an explicitly-supplied `countries` --
    # not to the FEATURED_COUNTRIES default, which is trusted internal state (and, in
    # production, always a subset of the expanded set by construction; only test fixtures
    # can construct a narrower expanded list that wouldn't contain it).
    if countries:
        if len(countries) > MAX_SELECTED_COUNTRIES:
            raise HTTPException(status_code=422, detail=f"Select at most {MAX_SELECTED_COUNTRIES} countries.")
        unknown = set(countries) - set(expanded)
        if unknown:
            raise HTTPException(status_code=404, detail=f"Unknown countries: {sorted(unknown)}")
        selected = countries
    else:
        selected = FEATURED_COUNTRIES

    try:
        df = load_features()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    try:
        df_all = load_raw_sovereign()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    df_expanded = df[df["country"].isin(expanded)]
    df_selected = df[df["country"].isin(selected)]

    latest_year = int(df_selected["year"].max())
    df_bar = df_selected[df_selected["year"] == latest_year][["country", "co2"]].sort_values("co2", ascending=False)
    latest_year_bar = [CountryValue(country=r["country"], value=r["co2"]) for _, r in df_bar.iterrows()]

    co2_1990_by_country = df_selected[df_selected["year"] == 1990].set_index("country")["co2"]
    co2_latest_by_country = df_selected[df_selected["year"] == latest_year].set_index("country")["co2"]
    absolute_change = co2_latest_by_country - co2_1990_by_country
    pct_change_by_country = absolute_change / co2_1990_by_country * 100

    movers = pd.DataFrame({
        "co2_1990": co2_1990_by_country,
        "co2_latest": co2_latest_by_country,
        "absolute_change": absolute_change,
        "pct_change": pct_change_by_country,
    }).dropna().sort_values("pct_change", ascending=False)

    top_movers = [
        MoverRow(
            country=country,
            co2_1990=row["co2_1990"],
            co2_latest=row["co2_latest"],
            absolute_change=row["absolute_change"],
            pct_change=row["pct_change"],
        )
        for country, row in movers.iterrows()
    ]

    # Every real expanded country currently has both a 1990 and latest-year row (verified
    # against live data), so top_movers is never empty in practice -- but `countries` is
    # arbitrary user input, and a future selected_countries.json regeneration could include
    # a country missing one or the other. Fall back to an "N/A" placeholder rather than
    # crashing on an empty top_movers list.
    na_mover = MoverRow(country="N/A", co2_1990=None, co2_latest=None, absolute_change=None, pct_change=None)
    fastest_growth = top_movers[0] if top_movers else na_mover
    largest_reduction = top_movers[-1] if top_movers else na_mover

    all_latest_year = int(df_all["year"].max())
    df_map = df_all[df_all["year"] == all_latest_year]
    world_map = [
        WorldMapPoint(
            country=r["country"],
            iso_code=r["iso_code"] if pd.notna(r["iso_code"]) else None,
            value=r["co2"] if pd.notna(r["co2"]) else None,
        )
        for _, r in df_map.iterrows()
    ]

    return OverviewResponse(
        all_countries=_tier_metrics(df_all, "All Countries", df_all["country"].nunique(), include_yearly=True),
        expanded_countries=_tier_metrics(df_expanded, "Expanded", len(expanded), include_yearly=True),
        selected=_tier_metrics(df_selected, "Selected", len(selected)),
        selected_country_list=selected,
        latest_year_bar=latest_year_bar,
        top_movers=top_movers,
        fastest_growth=fastest_growth,
        largest_reduction=largest_reduction,
        world_map=world_map,
    )


@router.get("/overview/world-map-series", response_model=WorldMapTimeSeries)
def get_world_map_series():
    """SPEC.md §5.17 -- the animated choropleth's full year-by-year payload. Selection-invariant
    (no `countries` param): served on its own route rather than folded into /overview, which
    re-fetches on every country-selection change and would otherwise ship this ~50KB columnar
    payload on every one of those re-fetches for no reason."""
    try:
        series = load_world_map_series()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)
    return WorldMapTimeSeries(**series)
