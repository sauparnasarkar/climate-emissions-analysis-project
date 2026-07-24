from fastapi import APIRouter

from ..constants import FEATURED_COUNTRIES
from ..data_loaders import load_expanded_countries
from ..schemas import CountriesResponse

router = APIRouter()


@router.get("/countries", response_model=CountriesResponse)
def list_countries():
    return CountriesResponse(featured=FEATURED_COUNTRIES, expanded=load_expanded_countries())
