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


# The columns `get_forecast_summary` can rank (and cap) by -- the API's row fields.
FORECAST_RANK_COLUMNS = ("actual_2020", "forecast_2030", "forecast_2035", "forecast_2040", "pct_change_2020_2040")


@mcp.tool()
async def get_forecast_summary(scope: str = "featured", rank_by: str = "actual_2020") -> dict:
    """2030/2035/2040 forecast snapshot table. `scope` is 'featured' (10, default) or
    'expanded' (~40). This tool has no country-list argument, so trimming (SPEC.md §3.2)
    always applies when there are more than 10 rows: capped to the 10 countries with the
    highest `rank_by` value, with a scope_note explaining the cap. At `scope='featured'`
    there are exactly 10 rows already, so no trimming occurs there in practice.

    `rank_by` is the column the cap (and the order of the rows) follows: 'actual_2020' (default),
    'forecast_2030', 'forecast_2035', 'forecast_2040' or 'pct_change_2020_2040'. **For "top N
    forecasted emitters in 2040" pass scope='expanded' and rank_by='forecast_2040'** -- ranking by
    the 2020 actuals would pick the cap from the wrong column. The response's `ranked_by` says
    which column ordered the rows; `effective_scope` is the scope actually served ('expanded' only when the
    expanded list really is larger than the featured ten)."""
    if rank_by not in FORECAST_RANK_COLUMNS:
        raise ValueError(f"rank_by must be one of {', '.join(FORECAST_RANK_COLUMNS)}, got '{rank_by}'")
    client = get_client()
    body = await client.get("/forecasts/summary", params={"scope": scope})
    # The scope that was ACTUALLY served: the API quietly falls back to the featured ten when its expanded list is missing (api/data_loaders.py), still
    # accepting scope='expanded'. 'expanded' is only real when that list is strictly larger than the featured one.
    lists = await fetch_country_lists()
    body["effective_scope"] = "expanded" if scope == "expanded" and set(lists.expanded) > set(lists.featured) else "featured"
    rows = sorted(
        body["rows"],
        key=lambda row: row[rank_by] if row.get(rank_by) is not None else float("-inf"),
        reverse=True,
    )
    trimmed, note = trim(
        rows,
        scope_label=SCOPE_LABELS[scope],
        sort_key_label=f"{rank_by} descending",
    )
    body["rows"] = trimmed
    body["ranked_by"] = rank_by
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
