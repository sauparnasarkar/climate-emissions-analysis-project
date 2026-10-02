"""Readers for the Area 2 climate-context outputs `pipeline/` writes to `data/climate/` (ENHANCEMENTS.md Release 21, decisions 44-45).

The API only reads: nothing here recomputes a pipeline result. `api/` does not import `pipeline/`; the two meet at the files. Every failure to read a usable file is a
`ClimateDataUnavailable`, which the routers turn into a 503 whose `detail` names the cause -- never a 200 with nulls to chart:
- the file does not exist (the pipeline has not run);
- the file exists but is the stage's explicit-null result (`unavailable_reason` set);
- the file's `schema_version` is not one this API understands;
- a numeric value in it is not finite.
"""

import json
import math
import os
from functools import lru_cache

import pandas as pd

from . import data_loaders
from .data_loaders import DataNotFoundError

SUPPORTED_SCHEMA = 1
CLIMATE_DATA_DIR_ENV = "CLIMATE_DATA_DIR"
# Set by tests; when None the directory is `CLIMATE_DATA_DIR` from the environment, else `<DATA_DIR>/climate`.
CLIMATE_DIR: str | None = None


class ClimateDataUnavailable(DataNotFoundError):
    """A climate output is missing, unavailable or unusable: a 503 with the reason (decision 45)."""


def climate_dir() -> str:
    return CLIMATE_DIR or os.environ.get(CLIMATE_DATA_DIR_ENV) or os.path.join(data_loaders.DATA_DIR, "climate")


def _path(name: str) -> str:
    return os.path.join(climate_dir(), name)


def _require_finite(o, where: str) -> None:
    if isinstance(o, float):
        if not math.isfinite(o):
            raise ClimateDataUnavailable(f"{where} holds a non-finite number ({o}); the data is not usable")
    elif isinstance(o, dict):
        for k, v in o.items():
            _require_finite(v, f"{where}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _require_finite(v, f"{where}[{i}]")


@lru_cache(maxsize=None)
def _read_json(name: str, directory: str) -> dict:
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        raise ClimateDataUnavailable(f"{name} has not been generated yet (the Area 2 pipeline has not run)")
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise ClimateDataUnavailable(f"{name} could not be read: {type(e).__name__}: {e}") from e
    if not isinstance(doc, dict):
        raise ClimateDataUnavailable(f"{name} is not a JSON object")
    if doc.get("schema_version", SUPPORTED_SCHEMA) != SUPPORTED_SCHEMA:
        raise ClimateDataUnavailable(f"{name} has schema_version {doc.get('schema_version')!r}; this API understands {SUPPORTED_SCHEMA}")
    if doc.get("unavailable_reason"):
        raise ClimateDataUnavailable(f"{name} is unavailable: {doc['unavailable_reason']}")
    _require_finite(doc, name)
    return doc


def load_json(name: str) -> dict:
    return _read_json(name, climate_dir())


def json_exists(name: str) -> bool:
    return os.path.exists(_path(name))


@lru_cache(maxsize=None)
def _read_csv(name: str, directory: str) -> pd.DataFrame:
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        raise ClimateDataUnavailable(f"{name} has not been generated yet (the Area 2 pipeline has not run)")
    try:
        return pd.read_csv(path)
    except (OSError, ValueError) as e:
        raise ClimateDataUnavailable(f"{name} could not be read: {type(e).__name__}: {e}") from e


def load_csv(name: str) -> pd.DataFrame:
    return _read_csv(name, climate_dir())


def load_catalog() -> dict:
    return load_json("indicator_catalog.json")


def load_provenance() -> dict:
    """provenance.json has no schema_version or unavailable_reason; it is a plain map of series id -> entry."""
    path = _path("provenance.json")
    if not os.path.exists(path):
        raise ClimateDataUnavailable("provenance.json has not been generated yet (the Area 2 pipeline has not run)")
    return _read_provenance(path, os.path.getmtime(path))


@lru_cache(maxsize=None)
def _read_provenance(path: str, _mtime: float) -> dict:
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise ClimateDataUnavailable(f"provenance.json could not be read: {type(e).__name__}: {e}") from e
    if not isinstance(doc, dict):
        raise ClimateDataUnavailable("provenance.json is not a JSON object")
    return doc


def catalog_entry(indicator_id: str) -> dict:
    for e in load_catalog().get("indicators", []):
        if e.get("id") == indicator_id:
            return e
    raise ClimateDataUnavailable(f"indicator {indicator_id} is not in indicator_catalog.json")


def indicator_series(indicator_id: str) -> pd.Series:
    """One harmonized global indicator as a year-indexed series. A missing indicator is a 503 (the layer is incomplete), not an empty answer."""
    df = load_csv("harmonized_global_annual.csv")
    if not {"indicator_id", "year", "value"} <= set(df.columns):
        raise ClimateDataUnavailable("harmonized_global_annual.csv lacks indicator_id/year/value columns")
    sub = df[df["indicator_id"] == indicator_id]
    if sub.empty:
        raise ClimateDataUnavailable(f"indicator {indicator_id} has no rows in harmonized_global_annual.csv")
    s = pd.Series(sub["value"].to_numpy(dtype=float), index=sub["year"].astype(int).to_numpy()).sort_index()
    return s


def clear_caches() -> None:
    _read_json.cache_clear()
    _read_csv.cache_clear()
    _read_provenance.cache_clear()
