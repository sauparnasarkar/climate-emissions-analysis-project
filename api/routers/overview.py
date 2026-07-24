import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import FEATURED_COUNTRIES, MAX_SELECTED_COUNTRIES
from ..data_loaders import DataNotFoundError, load_expanded_countries, load_features, load_raw_sovereign
from ..schemas import CountryValue, MoverRow, OverviewResponse, OverviewTierMetrics

router = APIRouter()


def _tier_metrics(df: pd.DataFrame, label: str, countries_count: int) -> OverviewTierMetrics:
    latest_year = int(df["year"].max())
    latest_total = float(df[df["year"] == latest_year]["co2"].sum())
    base_total = float(df[df["year"] == 1990]["co2"].sum())
    # A single user-selected country (now possible via `countries`) may have no 1990 row at
    # all -- guard the same way MoverRow's per-country pct_change already tolerates missing
    # baselines, rather than 500ing on a division by zero.
    pct_change = (latest_total - base_total) / base_total * 100 if base_total else 0.0
    return OverviewTierMetrics(
        label=label,
        countries_count=countries_count,
        latest_year=latest_year,
        latest_co2_total=latest_total,
        co2_1990_total=base_total,
        pct_change_since_1990=pct_change,
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

    return OverviewResponse(
        all_countries=_tier_metrics(df_all, "All Countries", df_all["country"].nunique()),
        expanded_countries=_tier_metrics(df_expanded, "Expanded", len(expanded)),
        selected=_tier_metrics(df_selected, "Selected", len(selected)),
        selected_country_list=selected,
        latest_year_bar=latest_year_bar,
        top_movers=top_movers,
        fastest_growth=fastest_growth,
        largest_reduction=largest_reduction,
    )
