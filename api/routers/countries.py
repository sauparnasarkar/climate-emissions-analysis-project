from fastapi import APIRouter, HTTPException

from ..constants import FEATURED_COUNTRIES
from ..data_loaders import DataNotFoundError, load_expanded_countries, load_raw_sovereign
from ..schemas import CountriesResponse

router = APIRouter()


@router.get("/countries", response_model=CountriesResponse)
def list_countries():
    # Unlike `expanded` (load_expanded_countries() degrades to FEATURED_COUNTRIES with a
    # warning if selected_countries.json is missing), `sovereign` has no such fallback -- it
    # reads owid-co2-data.csv directly via load_raw_sovereign(), so this endpoint can now 503
    # on a missing raw CSV, which it never could before this field existed.
    try:
        sovereign = sorted(load_raw_sovereign()["country"].unique().tolist())
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)
    return CountriesResponse(featured=FEATURED_COUNTRIES, expanded=load_expanded_countries(), sovereign=sovereign)
