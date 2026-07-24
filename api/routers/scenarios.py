from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException

from ..constants import FEATURED_COUNTRIES, SCENARIO_COLORS
from ..data_loaders import DataNotFoundError, load_expanded_countries, load_features, load_forecasts, load_scenarios
from ..schemas import (
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

    rows = [
        ScenarioCumulativeRow(country=country, values=row.to_dict())
        for country, row in table.iterrows()
    ]

    return ScenarioCumulativeResponse(
        sort_by=sort_by,
        order=order,
        scenarios=list(SCENARIO_COLORS.keys()),
        rows=rows,
    )
