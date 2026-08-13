"""SPEC.md §5 direct wraps: get_forecast, get_forecast_summary, get_model_comparison."""

from __future__ import annotations

from ..client import get_client
from ..methodology import SCOPE_LABELS
from ..resolution import fetch_country_lists, resolve_country
from ..server import mcp
from ..trimming import trim


@mcp.tool()
async def get_forecast(country: str) -> dict:
    """The ETS(A,Ad,N)-based production emissions forecast for a single country, with
    historical/holdout series and a confidence interval -- always the production model,
    never model-selectable. `country` is resolved against the expanded (~40-country) scope;
    a real country outside that scope raises a clear error rather than a bare 404.

    Do NOT call this once per country to build a multi-country comparison -- use
    get_forecast_comparison instead, which fetches every country's forecast concurrently in
    one call rather than costing one MCP round trip per country.

    Use this family (or get_forecast_comparison/get_forecast_summary) for plain
    forecast/projection questions with no scenario language -- "what will X's emissions be by
    2040", "projected emissions trend". This is the single statistical extrapolation, not a
    policy pathway. If the question explicitly invokes scenarios, policy pathways, or
    BAU/Moderate/Aggressive (or synonyms like "business as usual", "if climate policy
    tightens"), use get_scenario_projection/compare_scenarios_across_countries/
    get_scenario_cumulative_impact instead."""
    lists = await fetch_country_lists()
    resolved = resolve_country(country, lists, scope="expanded")
    client = get_client()
    return await client.get(f"/forecasts/{resolved}")


@mcp.tool()
async def get_forecast_summary(scope: str = "featured") -> dict:
    """2030/2035/2040 forecast snapshot table. `scope` is 'featured' (10, default) or
    'expanded' (~40). This tool has no country-list argument, so trimming (SPEC.md §3.2)
    always applies when there are more than 10 rows: capped to the 10 countries with the
    highest actual_2020 value, with a scope_note explaining the cap. At `scope='featured'`
    there are exactly 10 rows already, so no trimming occurs there in practice."""
    client = get_client()
    body = await client.get("/forecasts/summary", params={"scope": scope})
    trimmed, note = trim(
        body["rows"],
        scope_label=SCOPE_LABELS[scope],
        sort_key_label="actual_2020 descending",
        sort_key=lambda row: row["actual_2020"] if row["actual_2020"] is not None else float("-inf"),
    )
    body["rows"] = trimmed
    if note is not None:
        body["scope_note"] = note
    return body


@mcp.tool()
async def get_model_comparison() -> dict:
    """Precomputed backtest comparison (MAE/RMSE) across Naive, Linear Regression, Random
    Forest per-country, Random Forest pooled, and ETS(A,Ad,N) -- a static artifact, not
    computed live."""
    client = get_client()
    return await client.get("/forecasts/model-comparison")
