"""Counting cumulative CO2 FROM a year (`from_year`) -- Release 24.8, ENHANCEMENTS.md D7. Shared by /historical/cumulative and /countries/{country}/cumulative.

Emissions from year X are a country's cumulative total at the end year minus its total at X-1 (equal to the sum of the annual values from X). A country with no
value at X-1 had emitted nothing before it (the pipeline's own rule: an absent row is a cumulative of zero), so its base is 0. Shares are of the World's emissions
in the period. The default (no `from_year`) is unchanged: totals count from each country's first record."""

from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from .constants import CUMULATIVE_BASE_YEAR, CUMULATIVE_YEAR_START


def check_from_year(from_year: int, latest_year: int) -> None:
    if from_year < CUMULATIVE_YEAR_START or from_year > latest_year:
        raise HTTPException(status_code=422, detail=f"from_year must be between {CUMULATIVE_YEAR_START} and {latest_year} (counting from a year needs the total at the year before it, which is held from {CUMULATIVE_BASE_YEAR}).")


def base_cumulative(df: pd.DataFrame, country: str, from_year: int) -> float:
    """A country's cumulative total at the year before `from_year`; 0.0 when it has no value there (it had emitted nothing before)."""
    row = df[(df["country"] == country) & (df["year"] == from_year - 1)]["cumulative_co2"].dropna()
    return float(row.iloc[0]) if len(row) else 0.0


def rebase(values: pd.Series, base: float) -> pd.Series:
    """Emissions from the base year: the running total minus the base, never negative (rounding), and missing stays missing."""
    return (values - base).clip(lower=0)


def share_of_period(emitted: pd.Series, world_emitted: pd.Series) -> pd.Series:
    """A share (%) of the World's emissions in the period; missing where the World emitted nothing yet (the first year of the period can be zero)."""
    return (emitted / world_emitted.where(world_emitted > 0) * 100)
