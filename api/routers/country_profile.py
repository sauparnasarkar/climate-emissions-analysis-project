import math

from fastapi import APIRouter, HTTPException

from ..constants import COUNTRIES
from ..data_loaders import DataNotFoundError, load_features
from ..schemas import CountryProfileResponse, CountryProfileTableRow

router = APIRouter()

DISPLAY_COLS = ["year", "co2", "co2_per_capita", "co2_yoy_pct_change", "ghg_intensity"]


def _nan_to_none(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


@router.get("/countries/{country}/profile", response_model=CountryProfileResponse)
def get_country_profile(country: str):
    if country not in COUNTRIES:
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
