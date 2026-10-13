import math

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import CUMULATIVE_YEAR_START
from ..cumulative_period import base_cumulative, check_from_year, rebase, share_of_period
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
def get_country_cumulative(country: str, from_year: int | None = Query(default=None, description="Count from this year (1970 to the latest): emissions from then, not the total since records began.")):
    """The country's cumulative-CO2 series from 1970 plus its latest headline figures (SPEC.md §5.28). `rank` is
    among sovereign (iso-coded) countries with a value in the same year, so OWID aggregates such as "Asia" never rank.
    With `from_year` (Release 24.8) the series and `latest` are emissions FROM that year: the years start there, the running total has the total at the year before
    subtracted, `latest.share_of_world_cumulative` is a share of the World's emissions in the period and `rank` is by emissions in the period."""
    if country not in load_expanded_countries():
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")
    try:
        full = load_cumulative()  # from 1969: the extra year is the base of from_year=1970
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)
    df = full[full["year"] >= CUMULATIVE_YEAR_START]

    d = df[df["country"] == country].drop_duplicates("year").sort_values("year")
    if d.empty:
        raise HTTPException(status_code=404, detail=f"No cumulative data for: {country}")
    if from_year is not None:
        check_from_year(from_year, int(df["year"].max()))
        d = d[d["year"] >= from_year]
        emitted = rebase(d["cumulative_co2"], base_cumulative(full, country, from_year))
        world = df[df["country"] == "World"].drop_duplicates("year").set_index("year")["cumulative_co2"]
        world_emitted = rebase(world, base_cumulative(full, "World", from_year))
        # assign, not item assignment on a subset frame: that trips pandas' chained-assignment warning on Python 3.14 (a false positive; see pipeline/country_share.py)
        d = d.assign(cumulative_co2=emitted, share_global_cumulative_co2=share_of_period(emitted, d["year"].map(world_emitted)))

    def opt(s):
        return [None if pd.isna(v) else float(v) for v in s]

    have = d.dropna(subset=["cumulative_co2"])
    latest = None
    if not have.empty:
        row = have.iloc[-1]
        year = int(row["year"])
        peers = df[(df["year"] == year) & df["iso_code"].notna()].dropna(subset=["cumulative_co2"])
        peer_values = peers["cumulative_co2"]
        if from_year is not None:  # rank by emissions in the period: each peer's total minus its own base
            bases = full[full["year"] == from_year - 1].dropna(subset=["cumulative_co2"]).drop_duplicates("country").set_index("country")["cumulative_co2"]
            peer_values = peers["cumulative_co2"] - peers["country"].map(bases).fillna(0.0)
        share = row["share_global_cumulative_co2"]
        latest = CountryCumulativeLatest(
            year=year,
            cumulative_co2=float(row["cumulative_co2"]),
            share_of_world_cumulative=None if pd.isna(share) else float(share),
            rank=int((peer_values.clip(lower=0) > row["cumulative_co2"]).sum()) + 1,
            rank_of=int(len(peers)),
        )
    return CountryCumulativeResponse(
        country=country,
        years=d["year"].astype(int).tolist(),
        cumulative_co2=opt(d["cumulative_co2"]),
        share_of_world_cumulative=opt(d["share_global_cumulative_co2"]),
        share_of_world_annual=opt(d["share_global_co2"]),
        latest=latest,
        from_year=from_year,
    )
