"""@lru_cache loaders mirroring app.py's @st.cache_data loaders 1:1."""

import json
import os
import warnings
from functools import lru_cache

import pandas as pd

from .constants import FEATURED_COUNTRIES, WORLD_MAP_YEAR_END, WORLD_MAP_YEAR_START

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
def load_raw_sovereign() -> pd.DataFrame:
    """All sovereign countries (iso_code.notna() filter, SPEC.md §6.1), year >= 1990. Backing
    dataframe for the Overview "All Countries" tier and the world map (both need every
    country, not just the ~40 expanded ones) -- Expanded/Selected keep reading
    load_features() (ghg_features.csv), unlike this loader which reads owid-co2-data.csv
    directly since ghg_features.csv is already restricted to the ~40 expanded countries.
    iso_code is included for the choropleth's `locations` and doubles as the sovereignty
    filter itself (see below) -- a real ISO-3 code is what distinguishes a sovereign country
    from an OWID aggregate row (mirrors notebook/constants.py's fix, SPEC.md §6.1)."""
    path = _path("owid-co2-data.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/owid-co2-data.csv not found.")
    cols = ["country", "year", "co2", "iso_code"]
    df_r = pd.read_csv(path, usecols=cols)
    return df_r[df_r["iso_code"].notna() & (df_r["year"] >= 1990)].copy()


@lru_cache(maxsize=1)
def load_world_map_series() -> dict:
    """SPEC.md §5.17.1 -- the animated choropleth's full WORLD_MAP_YEAR_START..END payload,
    pivoted into a columnar shape once and cached (this data is selection-invariant, so it's
    fetched once by the frontend regardless of country-selection changes, unlike
    load_raw_sovereign() which backs the selection-scoped /overview endpoint).

    No app.py mirror -- unlike every other loader in this file (whose docstring-level "mirrors
    app.py's @st.cache_data loaders 1:1" convention this loader deliberately breaks), since
    SPEC.md §5.17 is React-only with no equivalent Streamlit feature planned.

    Country order (iso_codes/countries) is fixed by sorting on iso_code once here, since
    `values[yearIdx][countryIdx]` is a positional index that must stay stable across requests.
    Each iso_code's country name is taken from its first matching row -- spot-checked against
    the real dataset before writing this (not assumed): zero iso_codes have more than one
    distinct country name across 1990-2024.

    Real no-data gaps (verified against the actual data, not just SPEC.md's draft claim of "6
    countries, all resolved by 1995"): 6 countries have a partial early-1990s gap (CXR, ERI,
    FSM, MHL, NAM, TLS -- resolved by 1995, matching the draft), but 3 more have *zero* co2 data
    across the entire range (MCO Monaco, SMR San Marino, VAT Vatican City) -- these simply never
    report emissions data in OWID. Not a bug in this loader; the no-data trace design (SyChart)
    handles any number of always/sometimes-null countries generically, so this doesn't need
    special-casing here."""
    path = _path("owid-co2-data.csv")
    if not os.path.exists(path):
        raise DataNotFoundError("data/owid-co2-data.csv not found.")
    cols = ["country", "year", "co2", "iso_code"]
    df_r = pd.read_csv(path, usecols=cols)
    df_r = df_r[
        df_r["iso_code"].notna()
        & (df_r["year"] >= WORLD_MAP_YEAR_START)
        & (df_r["year"] <= WORLD_MAP_YEAR_END)
    ]

    country_meta = df_r[["iso_code", "country"]].drop_duplicates(subset="iso_code").sort_values("iso_code")
    iso_codes = country_meta["iso_code"].tolist()
    countries = country_meta["country"].tolist()
    years = list(range(WORLD_MAP_YEAR_START, WORLD_MAP_YEAR_END + 1))

    pivot = df_r.pivot(index="year", columns="iso_code", values="co2").reindex(index=years, columns=iso_codes)
    values = [[None if pd.isna(v) else float(v) for v in row] for row in pivot.to_numpy()]

    # The floor excludes exact zero, not just null -- confirmed against the real data:
    # Antarctica (a real ISO-3 code, iso_code.notna() lets it through this filter same as
    # every other entity in it) reports literal 0.0 co2 for 2008-2024, genuinely rather than
    # a missing value. log10(0) is undefined, and this range exists specifically to feed a
    # log-scaled color axis (see the class docstring) -- a 0.0 floor would make `colorRange`'s
    # lower bound produce a null zmin once log-transformed. The smallest genuinely *positive*
    # value (confirmed against real data: 0.004 Mt, vs. 0.0 including the zero rows) is the
    # correct log-scale floor.
    positive_co2 = df_r[df_r["co2"] > 0]["co2"]
    value_range = (float(positive_co2.min()), float(df_r["co2"].max()))

    return {
        "iso_codes": iso_codes,
        "countries": countries,
        "years": years,
        "values": values,
        "value_range": value_range,
    }


@lru_cache(maxsize=1)
def load_filtered() -> pd.DataFrame:
    """Week 1 output: all ~218 sovereign countries (iso_code.notna() filter, SPEC.md §6.1),
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
