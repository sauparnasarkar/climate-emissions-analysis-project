"""Shared fixtures for the api/ test suite.

None of these tests touch the real (gitignored, notebook-generated) CSVs in data/ — every
test writes its own small fixture CSVs to a tmp_path and points api.data_loaders.DATA_DIR at
it, so the loaders' real filtering/parsing logic is genuinely exercised rather than mocked
away. FIXTURE_COUNTRIES is a subset of the real api.constants.COUNTRIES list, so no constant
needs monkeypatching.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import data_loaders

FIXTURE_COUNTRIES = ["China", "United States", "Germany"]
OUT_OF_SCOPE_COUNTRY = "France"  # not in api.constants.COUNTRIES

# One @lru_cache-decorated function per source CSV — cleared before every test so a fixture
# variation in one test (e.g. omitting a file to exercise the 503 path) never sees a result
# cached by a previous test.
_LOADERS = [
    data_loaders.load_features,
    data_loaders.load_forecasts,
    data_loaders.load_scenarios,
    data_loaders.load_raw,
    data_loaders.load_filtered,
    data_loaders.load_model_comparison,
    data_loaders.load_ets_parameters,
    data_loaders.load_feature_importance,
]


def _clear_caches():
    for fn in _LOADERS:
        fn.cache_clear()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Points DATA_DIR at an empty tmp_path. Tests write only the CSVs they need."""
    monkeypatch.setattr(data_loaders, "DATA_DIR", str(tmp_path))
    _clear_caches()
    yield tmp_path
    _clear_caches()


def ghg_features_df() -> pd.DataFrame:
    nan = np.nan
    rows = [
        # country, year, co2, co2_per_capita, co2_yoy_pct_change, ghg_intensity
        ("China", 1990, 2400, 2.1, nan, 1.5),
        ("China", 2020, 10000, 7.0, 5.2, 0.8),
        ("China", 2023, 11000, 7.6, 3.0, 0.75),
        ("United States", 1990, 5000, 20.0, nan, 0.9),
        ("United States", 2020, 4800, 14.5, -1.1, 0.6),
        ("United States", 2023, 4700, 14.0, -0.5, 0.58),
        ("Germany", 1990, 1000, 12.5, nan, 0.5),
        ("Germany", 2020, 650, 7.8, -3.0, 0.3),
        ("Germany", 2023, 600, 7.2, -2.0, 0.28),
        # out-of-scope country present in the file but must be excluded by COUNTRIES filters
        (OUT_OF_SCOPE_COUNTRY, 2023, 300, 4.5, 1.0, 0.4),
    ]
    return pd.DataFrame(rows, columns=["country", "year", "co2", "co2_per_capita", "co2_yoy_pct_change", "ghg_intensity"])


def ets_forecasts_df() -> pd.DataFrame:
    rows = [
        # country, year, mean, ci_upper, ci_lower
        ("China", 2020, 10500, 11000, 10000),
        ("China", 2030, 13000, 13500, 12500),
        ("China", 2035, 14500, 15200, 13800),
        ("China", 2040, 16000, 17000, 15000),
        ("United States", 2020, 4900, 5100, 4700),
        ("United States", 2030, 4400, 4600, 4200),
        ("United States", 2035, 4100, 4300, 3900),
        ("United States", 2040, 3800, 4000, 3600),
        ("Germany", 2020, 640, 680, 600),
        ("Germany", 2030, 500, 540, 460),
        ("Germany", 2035, 430, 470, 390),
        # Germany deliberately has no 2040 forecast row — exercises the NaN/None path in
        # forecasts/summary's forecast_2040 and the "missing values sort last" behavior.
    ]
    return pd.DataFrame(rows, columns=["country", "year", "mean", "ci_upper", "ci_lower"])


def scenario_projections_df() -> pd.DataFrame:
    rows = [
        # country, year, scenario, co2_projected
        ("China", 2025, "BAU", 10800), ("China", 2040, "BAU", 12500),
        ("China", 2025, "Moderate", 10500), ("China", 2040, "Moderate", 9000),
        ("China", 2025, "Aggressive", 10200), ("China", 2040, "Aggressive", 7000),
        ("United States", 2025, "BAU", 4700), ("United States", 2040, "BAU", 4200),
        ("United States", 2025, "Moderate", 4600), ("United States", 2040, "Moderate", 3500),
        ("United States", 2025, "Aggressive", 4400), ("United States", 2040, "Aggressive", 3000),
        ("Germany", 2025, "BAU", 610), ("Germany", 2040, "BAU", 550),
        ("Germany", 2025, "Moderate", 600), ("Germany", 2040, "Moderate", 400),
        # Germany's Aggressive total is deliberately the highest of the three countries,
        # while its BAU total is the lowest — proves sort_by actually changes the order
        # rather than all three scenarios coincidentally agreeing.
        ("Germany", 2025, "Aggressive", 8000), ("Germany", 2040, "Aggressive", 9000),
    ]
    return pd.DataFrame(rows, columns=["country", "year", "scenario", "co2_projected"])


def owid_raw_df() -> pd.DataFrame:
    years = [1990, 1995, 2000, 2005, 2010]
    rows = []
    for country in FIXTURE_COUNTRIES:
        for i, year in enumerate(years):
            rows.append((country, year, 100.0 + i, 20.0, 5.0))
    # Pre-1990 row (must be excluded by load_raw's year >= 1990 filter) and a non-focus
    # country row (must be excluded by the COUNTRIES filter) — both for "China" so the
    # exclusion is unambiguous.
    rows.append(("China", 1985, 999.0, 999.0, 999.0))
    rows.append(("Canada", 1995, 999.0, 999.0, 999.0))
    return pd.DataFrame(rows, columns=["country", "year", "co2", "methane", "nitrous_oxide"])


def ghg_filtered_df() -> pd.DataFrame:
    # Kenya is outside both FIXTURE_COUNTRIES and the real api.constants.COUNTRIES focus
    # list — load_filtered() deliberately does NOT restrict to COUNTRIES (unlike load_raw),
    # so it must appear in /explorer results, proving that non-restriction.
    rows = [
        ("China", 1990, 2400, 1_150_000_000),
        ("China", 2010, 8500, 1_340_000_000),
        ("China", 2023, 11000, 1_410_000_000),
        ("United States", 1990, 5000, 250_000_000),
        ("United States", 2010, 5300, 309_000_000),
        ("United States", 2023, 4700, 335_000_000),
        ("Germany", 1990, 1000, 79_000_000),
        ("Germany", 2010, 800, 81_000_000),
        ("Germany", 2023, 600, 84_000_000),
        ("Kenya", 1990, 5, 24_000_000),
        ("Kenya", 2010, 12, 41_000_000),
        ("Kenya", 2023, 18, 55_000_000),
    ]
    return pd.DataFrame(rows, columns=["country", "year", "co2", "population"])


def model_comparison_df() -> pd.DataFrame:
    rows = [
        ("China", "Linear Regression", 120.5, 150.2),
        ("China", "RF Pooled", 95.3, 110.7),
        ("United States", "Linear Regression", 80.1, 95.4),
    ]
    return pd.DataFrame(rows, columns=["Country", "Model", "MAE", "RMSE"])


def ets_parameters_df() -> pd.DataFrame:
    rows = [
        ("China", 0.8, 0.05, 0.9),
        ("United States", 0.7, 0.03, 0.85),
        ("Germany", 0.75, 0.04, 0.88),
    ]
    return pd.DataFrame(rows, columns=["country", "alpha", "beta_star", "phi"])


def feature_importance_df() -> pd.DataFrame:
    # Deliberately unsorted — proves the endpoint's own ascending sort, not fixture order.
    rows = [
        ("gdp", 0.32),
        ("population", 0.10),
        ("energy_intensity", 0.45),
        ("coal_share", 0.13),
    ]
    return pd.DataFrame(rows, columns=["feature", "importance"])


FIXTURE_BUILDERS = {
    "ghg_features.csv": ghg_features_df,
    "ets_forecasts.csv": ets_forecasts_df,
    "scenario_projections.csv": scenario_projections_df,
    "owid-co2-data.csv": owid_raw_df,
    "ghg_filtered.csv": ghg_filtered_df,
    "model_comparison.csv": model_comparison_df,
    "ets_parameters.csv": ets_parameters_df,
    "feature_importance.csv": feature_importance_df,
}


def write_fixture(data_dir, filename: str) -> None:
    """Writes a single named fixture CSV (see FIXTURE_BUILDERS) into data_dir."""
    FIXTURE_BUILDERS[filename]().to_csv(data_dir / filename, index=False)


@pytest.fixture
def full_data(data_dir):
    """data_dir with every fixture CSV present — the common case for happy-path tests."""
    for filename in FIXTURE_BUILDERS:
        write_fixture(data_dir, filename)
    return data_dir


@pytest.fixture
def client(full_data):
    from api.main import app

    return TestClient(app)
