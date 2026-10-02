"""Pure derivation functions for the harmonized layer (Release 21, Phase 1.2; decisions 25-28).

Every function takes a `pandas.Series` indexed by integer calendar year and returns a Series on the
same index. Rules shared by all of them:

- **No interpolation, ever.** A missing year stays NaN, and anything that needs it is NaN too.
- Calendar-year arithmetic is done on the *full* year range, so `shift(1)` is genuinely "the previous
  year" -- a gap in the data can never make a 1950 value look like the year before 1952.
- Anything that would be meaningless is NaN with an explicit reason (see `index_to_baseline`), not a
  silently wrong number.

Deliberately dependency-free (pandas/numpy only) and unaware of files, sources or provenance, so each
rule is unit-testable on its own.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Baselines the platform allows (SPEC §2.5). "preindustrial" is the single year 1850: the first year of
# the Berkeley Earth record and of the 1850-1900 reference, and well inside OWID/PRIMAP-hist coverage.
BASELINES: dict[str, int] = {"1990": 1990, "1970": 1970, "preindustrial": 1850}
TRAILING_WINDOW = 5


def _as_year_series(s: pd.Series) -> pd.Series:
    out = s.astype(float).copy()
    out.index = out.index.astype(int)
    if out.index.has_duplicates:
        raise ValueError("series has duplicate years")
    return out.sort_index()


def _full_range(s: pd.Series) -> pd.Series:
    return s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))


def yoy_pct(s: pd.Series) -> pd.Series:
    """Year-on-year change in percent, `100 * (v[y] / v[y-1] - 1)`. NaN where the previous calendar year is
    missing or is not > 0 (a percentage change from zero or a negative value has no meaning)."""
    s = _as_year_series(s)
    full = _full_range(s)
    prev = full.shift(1)
    out = 100.0 * (full / prev - 1.0)
    out[~(prev > 0)] = np.nan
    return out.reindex(s.index)


def trailing_mean(s: pd.Series, window: int = TRAILING_WINDOW) -> pd.Series:
    """Mean of the current and previous `window - 1` calendar years; NaN until `window` consecutive
    observations exist. Trailing, not centred: no value ever uses a later year, so it is safe to use
    inside a lagged analysis (centring would leak the future into the past)."""
    s = _as_year_series(s)
    return _full_range(s).rolling(window, min_periods=window).mean().reindex(s.index)


def baseline_problem(s: pd.Series, baseline_year: int) -> str | None:
    """Why `s` cannot be indexed to `baseline_year`, or None if it can."""
    s = _as_year_series(s)
    first, last = int(s.index.min()), int(s.index.max())
    if baseline_year < first or baseline_year > last:
        return f"baseline year {baseline_year} is outside the coverage {first}-{last}"
    v = s.get(baseline_year, np.nan)
    if pd.isna(v):
        return f"no value in the baseline year {baseline_year}"
    if v <= 0:
        return f"the baseline-year value ({v:g}) is not greater than zero"
    return None


def index_to_baseline(s: pd.Series, baseline_year: int, base: float = 100.0) -> tuple[pd.Series, str | None]:
    """`base * value / value[baseline_year]`. Returns (series, problem): when there is a problem the series
    is all-NaN and `problem` says why -- the caller records it instead of publishing a meaningless index."""
    s = _as_year_series(s)
    problem = baseline_problem(s, baseline_year)
    if problem:
        return pd.Series(np.nan, index=s.index), problem
    return base * s / s.loc[baseline_year], None


def cumulative(s: pd.Series) -> pd.Series:
    """Running total from the first observation. NaN before the series starts, and NaN from the first
    interior gap onward: a total that skipped a year would be silently too small."""
    s = _as_year_series(s)
    out = pd.Series(np.nan, index=s.index)
    first = s.first_valid_index()
    if first is None:
        return out
    tail = _full_range(s).loc[first:]
    out.loc[first:] = tail.cumsum(skipna=False).reindex(out.loc[first:].index).to_numpy()
    return out


def first_last_valid(s: pd.Series) -> tuple[int, int] | None:
    s = _as_year_series(s)
    a, b = s.first_valid_index(), s.last_valid_index()
    return None if a is None else (int(a), int(b))
