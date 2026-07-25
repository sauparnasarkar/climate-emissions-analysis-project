from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..constants import FEATURED_COUNTRIES, SCENARIO_COLORS
from ..data_loaders import DataNotFoundError, load_expanded_countries, load_features, load_forecasts, load_scenarios
from ..schemas import (
    ScenarioCompareResponse,
    ScenarioCumulativeResponse,
    ScenarioCumulativeRow,
    ScenarioSeries,
    ScenarioTimeseriesResponse,
)

router = APIRouter()

ViewMode = Literal["single", "global"]
SortScenario = Literal["BAU", "Moderate", "Aggressive"]
Scope = Literal["featured", "expanded"]


def _bau_segment(df_forecasts, country_filter, start, end):
    if df_forecasts is None:
        return pd.Series(dtype=float)
    fc = df_forecasts[df_forecasts["country"].isin(country_filter)]
    fc = fc[(fc["year"] >= start) & (fc["year"] <= end)]
    return fc.groupby("year")["mean"].sum()


@router.get("/scenarios/timeseries", response_model=ScenarioTimeseriesResponse)
def get_scenario_timeseries(view: ViewMode = "single", country: str | None = None, scope: Scope = "featured"):
    try:
        df_scenarios = load_scenarios()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    try:
        df_forecasts = load_forecasts()
    except DataNotFoundError:
        df_forecasts = None

    try:
        df = load_features()
    except DataNotFoundError:
        df = None

    if view == "single":
        if country is None or country not in load_expanded_countries():
            raise HTTPException(status_code=400, detail="A valid country is required for view=single")
        countries_in_view = [country]
        title_suffix = country
    else:
        countries_in_view = FEATURED_COUNTRIES if scope == "featured" else load_expanded_countries()
        title_suffix = f"All {len(countries_in_view)} Countries"

    hist = (
        df[(df["country"].isin(countries_in_view)) & (df["year"] <= 2024)].groupby("year")["co2"].sum()
        if df is not None
        else pd.Series(dtype=float)
    )
    level_1990 = float(hist.loc[1990]) if 1990 in hist.index else None
    bau_2020_2024 = _bau_segment(df_forecasts, countries_in_view, 2020, 2024)

    historical_series = (
        ScenarioSeries(name="Historical (1990–2024)", years=hist.index.tolist(), values=hist.values.tolist())
        if not hist.empty
        else None
    )

    scenario_series = []
    for scenario in SCENARIO_COLORS:
        if scenario == "BAU":
            series = _bau_segment(df_forecasts, countries_in_view, 2020, 2040)
        else:
            future = (
                df_scenarios[
                    (df_scenarios["country"].isin(countries_in_view)) & (df_scenarios["scenario"] == scenario)
                ]
                .groupby("year")["co2_projected"]
                .sum()
            )
            series = pd.concat([bau_2020_2024, future])
        scenario_series.append(ScenarioSeries(name=scenario, years=series.index.tolist(), values=series.values.tolist()))

    return ScenarioTimeseriesResponse(
        title_suffix=title_suffix,
        historical=historical_series,
        scenarios=scenario_series,
        level_1990=level_1990,
    )


@router.get("/scenarios/cumulative", response_model=ScenarioCumulativeResponse)
def get_scenario_cumulative(sort_by: SortScenario = "BAU"):
    try:
        df_scenarios = load_scenarios()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    cumulative = (
        df_scenarios.groupby(["country", "scenario"])["co2_projected"]
        .sum()
        .reset_index()
        .rename(columns={"co2_projected": "cumulative_co2"})
    )

    order = (
        cumulative[cumulative["scenario"] == sort_by]
        .sort_values("cumulative_co2", ascending=False)["country"]
        .tolist()
    )

    table = cumulative.pivot(index="country", columns="scenario", values="cumulative_co2")
    table = table[list(SCENARIO_COLORS.keys())].loc[order].round(0)

    # Per-scenario 2040 value, alongside the cumulative sum above -- lets the frontend color
    # the treemap by "is the selected scenario's 2040 level higher or lower than today," which
    # a 2025-2040 sum alone can't answer.
    year_2040_table = (
        df_scenarios[df_scenarios["year"] == 2040]
        .pivot(index="country", columns="scenario", values="co2_projected")
        .reindex(columns=list(SCENARIO_COLORS.keys()))
    )

    try:
        df_features = load_features()
        current_year = int(df_features["year"].max())
        current_level_by_country = df_features[df_features["year"] == current_year].set_index("country")["co2"]
    except DataNotFoundError:
        current_level_by_country = pd.Series(dtype=float)

    rows = [
        ScenarioCumulativeRow(
            country=country,
            values=row.to_dict(),
            year_2040=year_2040_table.loc[country].to_dict() if country in year_2040_table.index else {},
            current_level=(
                float(current_level_by_country[country]) if country in current_level_by_country.index else None
            ),
        )
        for country, row in table.iterrows()
    ]

    return ScenarioCumulativeResponse(
        sort_by=sort_by,
        order=order,
        scenarios=list(SCENARIO_COLORS.keys()),
        rows=rows,
    )


@router.get("/scenarios/compare", response_model=ScenarioCompareResponse)
def get_scenario_compare(countries: list[str] = Query(...)):
    if not countries:
        raise HTTPException(status_code=400, detail="At least one country is required")
    unknown = sorted(set(countries) - set(load_expanded_countries()))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown countries: {', '.join(unknown)}")

    try:
        df_scenarios = load_scenarios()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    try:
        df_forecasts = load_forecasts()
    except DataNotFoundError:
        df_forecasts = None

    try:
        df = load_features()
    except DataNotFoundError:
        df = None

    scenario_names = list(SCENARIO_COLORS.keys())
    result: dict[str, list[ScenarioSeries]] = {s: [] for s in scenario_names}

    for country in countries:
        # Historical stops before 2020 (where the forecast/scenario segments below begin) so
        # each country's line is one clean, non-overlapping series rather than the two
        # overlapping historical-vs-forecast traces /scenarios/timeseries uses to show
        # holdout accuracy -- with up to 10 countries per panel, that pattern here would
        # double the trace count and clutter the legend for no benefit in this view.
        hist = (
            df[(df["country"] == country) & (df["year"] < 2020)].sort_values("year")
            if df is not None
            else None
        )
        hist_years = hist["year"].tolist() if hist is not None else []
        hist_values = hist["co2"].tolist() if hist is not None else []

        bau_2020_2024 = _bau_segment(df_forecasts, [country], 2020, 2024)

        for scenario in scenario_names:
            if scenario == "BAU":
                future = _bau_segment(df_forecasts, [country], 2020, 2040)
            else:
                future_only = (
                    df_scenarios[(df_scenarios["country"] == country) & (df_scenarios["scenario"] == scenario)]
                    .groupby("year")["co2_projected"]
                    .sum()
                )
                future = pd.concat([bau_2020_2024, future_only])

            years = hist_years + future.index.tolist()
            values = hist_values + future.values.tolist()
            result[scenario].append(ScenarioSeries(name=country, years=years, values=values))

    return ScenarioCompareResponse(countries=countries, scenarios=result)
