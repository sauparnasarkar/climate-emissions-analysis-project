import math

import pandas as pd
from fastapi import APIRouter, HTTPException

from ..data_loaders import DataNotFoundError, load_cumulative, load_expanded_countries, load_features
from ..schemas import CountryCumulativeLatest, CountryCumulativeResponse, CountryProfileResponse, CountryProfileTableRow

router = APIRouter()

DISPLAY_COLS = ["year", "co2", "co2_per_capita", "co2_yoy_pct_change", "ghg_intensity"]


def _nan_to_none(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


@router.get("/countries/{country}/profile", response_model=CountryProfileResponse)
def get_country_profile(country: str):
    if country not in load_expanded_countries():
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")

    try:
        df = load_features()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    df_country = df[df["country"] == country].sort_values("year").copy()

    df_yoy = df_country.dropna(subset=["co2_yoy_pct_change"])

    available = [c for c in DISPLAY_COLS if c in df_country.columns]
    df_table = df_country[available].round(2)
    table = [
        CountryProfileTableRow(
            year=int(row["year"]),
            co2=_nan_to_none(row.get("co2")),
            co2_per_capita=_nan_to_none(row.get("co2_per_capita")),
            co2_yoy_pct_change=_nan_to_none(row.get("co2_yoy_pct_change")),
            ghg_intensity=_nan_to_none(row.get("ghg_intensity")),
        )
        for _, row in df_table.iterrows()
    ]

    return CountryProfileResponse(
        country=country,
        years=df_country["year"].tolist(),
        co2=[_nan_to_none(v) for v in df_country["co2"].tolist()],
        co2_per_capita=[_nan_to_none(v) for v in df_country["co2_per_capita"].tolist()],
        yoy_years=df_yoy["year"].tolist(),
        yoy_values=df_yoy["co2_yoy_pct_change"].tolist(),
        table=table,
    )


@router.get("/countries/{country}/cumulative", response_model=CountryCumulativeResponse)
def get_country_cumulative(country: str):
    """The country's cumulative-CO2 series from 1970 plus its latest headline figures (SPEC.md §5.28). `rank` is
    among sovereign (iso-coded) countries with a value in the same year, so OWID aggregates such as "Asia" never rank."""
    if country not in load_expanded_countries():
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")
    try:
        df = load_cumulative()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    d = df[df["country"] == country].drop_duplicates("year").sort_values("year")
    if d.empty:
        raise HTTPException(status_code=404, detail=f"No cumulative data for: {country}")

    def opt(s):
        return [None if pd.isna(v) else float(v) for v in s]

    have = d.dropna(subset=["cumulative_co2"])
    latest = None
    if not have.empty:
        row = have.iloc[-1]
        year = int(row["year"])
        peers = df[(df["year"] == year) & df["iso_code"].notna()].dropna(subset=["cumulative_co2"])
        share = row["share_global_cumulative_co2"]
        latest = CountryCumulativeLatest(
            year=year,
            cumulative_co2=float(row["cumulative_co2"]),
            share_of_world_cumulative=None if pd.isna(share) else float(share),
            rank=int((peers["cumulative_co2"] > row["cumulative_co2"]).sum()) + 1,
            rank_of=int(len(peers)),
        )
    return CountryCumulativeResponse(
        country=country,
        years=d["year"].astype(int).tolist(),
        cumulative_co2=opt(d["cumulative_co2"]),
        share_of_world_cumulative=opt(d["share_global_cumulative_co2"]),
        share_of_world_annual=opt(d["share_global_co2"]),
        latest=latest,
    )
