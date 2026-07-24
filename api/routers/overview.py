from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException

from ..constants import FEATURED_COUNTRIES
from ..data_loaders import DataNotFoundError, load_expanded_countries, load_features
from ..schemas import CountryValue, MoverRow, OverviewResponse

router = APIRouter()

Scope = Literal["featured", "expanded"]


@router.get("/overview", response_model=OverviewResponse)
def get_overview(scope: Scope = "featured"):
    try:
        df = load_features()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    expanded = load_expanded_countries()
    countries_in_scope = FEATURED_COUNTRIES if scope == "featured" else expanded

    latest_year = int(df["year"].max())

    latest_co2 = float(df[(df["year"] == latest_year) & (df["country"].isin(countries_in_scope))]["co2"].sum())
    co2_1990 = float(df[(df["year"] == 1990) & (df["country"].isin(countries_in_scope))]["co2"].sum())
    pct_change = (latest_co2 - co2_1990) / co2_1990 * 100

    df_bar = (
        df[(df["year"] == latest_year) & (df["country"].isin(countries_in_scope))][["country", "co2"]]
        .sort_values("co2", ascending=False)
    )
    latest_year_bar = [CountryValue(country=r["country"], value=r["co2"]) for _, r in df_bar.iterrows()]

    co2_1990_by_country = df[(df["year"] == 1990) & (df["country"].isin(countries_in_scope))].set_index("country")["co2"]
    co2_latest_by_country = df[(df["year"] == latest_year) & (df["country"].isin(countries_in_scope))].set_index("country")["co2"]
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

    return OverviewResponse(
        latest_year=latest_year,
        latest_co2_total=latest_co2,
        co2_1990_total=co2_1990,
        pct_change_since_1990=pct_change,
        countries_count=len(countries_in_scope),
        focus_countries=countries_in_scope,
        total_countries_analyzed=len(expanded),
        latest_year_bar=latest_year_bar,
        top_movers=top_movers,
        fastest_growth=top_movers[0],
        largest_reduction=top_movers[-1],
    )
