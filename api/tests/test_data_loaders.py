import pytest

from api.data_loaders import DataNotFoundError, load_raw

from .conftest import FIXTURE_COUNTRIES, write_fixture


@pytest.mark.parametrize(
    ("loader_name", "filename", "expected_snippet"),
    [
        ("load_features", "ghg_features.csv", "Week 2"),
        ("load_forecasts", "ets_forecasts.csv", "Week 4"),
        ("load_scenarios", "scenario_projections.csv", "Week 5"),
        ("load_raw", "owid-co2-data.csv", "owid-co2-data.csv"),
        ("load_model_comparison", "model_comparison.csv", "Week 4"),
        ("load_ets_parameters", "ets_parameters.csv", "Week 4"),
        ("load_feature_importance", "feature_importance.csv", "Week 3"),
    ],
)
def test_loader_raises_when_file_missing(data_dir, loader_name, filename, expected_snippet):
    import api.data_loaders as data_loaders

    loader = getattr(data_loaders, loader_name)
    with pytest.raises(DataNotFoundError) as exc_info:
        loader()
    assert filename in str(exc_info.value)
    assert expected_snippet in str(exc_info.value)


def test_load_raw_filters_by_country_and_year(data_dir):
    write_fixture(data_dir, "owid-co2-data.csv")
    df = load_raw()

    assert set(df["country"].unique()) == set(FIXTURE_COUNTRIES)
    assert "Canada" not in df["country"].unique()  # non-focus country row
    assert df["year"].min() >= 1990  # the fixture's 1985 row must be excluded
    assert not ((df["country"] == "China") & (df["year"] == 1985)).any()


def test_load_expanded_countries_falls_back_with_warning(data_dir):
    import api.data_loaders as data_loaders

    with pytest.warns(UserWarning, match="selected_countries.json"):
        result = data_loaders.load_expanded_countries()
    assert result == data_loaders.FEATURED_COUNTRIES


def test_load_expanded_countries_reads_json_file(data_dir):
    import json

    import api.data_loaders as data_loaders

    with open(data_dir / "selected_countries.json", "w") as f:
        json.dump({"expanded": ["China", "France"]}, f)

    assert data_loaders.load_expanded_countries() == ["China", "France"]
