"""@lru_cache loaders mirroring app.py's @st.cache_data loaders 1:1."""

import json
import os
import warnings
from functools import lru_cache

import pandas as pd

from .constants import FEATURED_COUNTRIES

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class DataNotFoundError(Exception):
    """Raised when a required CSV hasn't been generated yet — routers turn this into a 503."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


@lru_cache(maxsize=1)
def load_features() -> pd.DataFrame:
    path = _path("ghg_features.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/ghg_features.csv not found. Complete Week 2 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_forecasts() -> pd.DataFrame:
    path = _path("ets_forecasts.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/ets_forecasts.csv not found. Complete Week 4 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_scenarios() -> pd.DataFrame:
    path = _path("scenario_projections.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/scenario_projections.csv not found. Complete Week 5 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_expanded_countries() -> list[str]:
    """Loads data/selected_countries.json (produced by week1_eda.ipynb §1.2's coverage +
    materiality selection). Unlike every other loader here, falls back to
    FEATURED_COUNTRIES with a warning rather than raising DataNotFoundError -- a missing
    expanded-country list should degrade gracefully (routers using it keep working, just
    scoped to the original 10) rather than 503 endpoints that don't otherwise need Week 1
    to have been re-run. Cached like every other loader: a selected_countries.json update
    needs a process restart to take effect."""
    path = _path("selected_countries.json")
    if not os.path.exists(path):
        warnings.warn("data/selected_countries.json not found. Falling back to FEATURED_COUNTRIES only.")
        return FEATURED_COUNTRIES
    with open(path) as f:
        return json.load(f)["expanded"]


@lru_cache(maxsize=1)
def load_raw() -> pd.DataFrame:
    path = _path("owid-co2-data.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/owid-co2-data.csv not found.")
    cols = ["country", "year", "co2", "methane", "nitrous_oxide"]
    df_r = pd.read_csv(path, usecols=cols)
    return df_r[(df_r["country"].isin(load_expanded_countries())) & (df_r["year"] >= 1990)].copy()


@lru_cache(maxsize=1)
def load_filtered() -> pd.DataFrame:
    """Week 1 output: all ~220 sovereign countries (NON_SOVEREIGN aggregates excluded),
    year >= 1990 — the full raw+derived OWID panel, not reduced to the 10 focus countries
    or the 10-column feature set. Backs the Data Explorer endpoints. Deliberately does NOT
    apply load_raw()'s COUNTRIES restriction — exposing the wider country set is the point."""
    path = _path("ghg_filtered.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/ghg_filtered.csv not found. Complete Week 1 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_model_comparison() -> pd.DataFrame:
    path = _path("model_comparison.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/model_comparison.csv not found. Complete Week 4 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_ets_parameters() -> pd.DataFrame:
    path = _path("ets_parameters.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/ets_parameters.csv not found. Complete Week 4 of the notebook.")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_feature_importance() -> pd.DataFrame:
    path = _path("feature_importance.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/feature_importance.csv not found. Complete Week 3 of the notebook.")
    return pd.read_csv(path)
