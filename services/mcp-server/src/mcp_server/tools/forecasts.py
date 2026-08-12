"""SPEC.md §5 direct wraps: get_forecast, get_forecast_summary, get_model_comparison."""

from __future__ import annotations

from ..client import get_client
from ..resolution import fetch_country_lists, resolve_country
from ..server import mcp


@mcp.tool()
async def get_forecast(country: str) -> dict:
    """The ETS(A,Ad,N)-based production emissions forecast for a single country, with
    historical/holdout series and a confidence interval -- always the production model,
    never model-selectable. `country` is resolved against the expanded (~40-country) scope;
    a real country outside that scope raises a clear error rather than a bare 404."""
    lists = await fetch_country_lists()
    resolved = resolve_country(country, lists, scope="expanded")
    client = get_client()
    return await client.get(f"/forecasts/{resolved}")


@mcp.tool()
async def get_forecast_summary(scope: str = "featured") -> dict:
    """2030/2035/2040 forecast snapshot table. `scope` is 'featured' (10, default) or
    'expanded' (~40)."""
    client = get_client()
    return await client.get("/forecasts/summary", params={"scope": scope})


@mcp.tool()
async def get_model_comparison() -> dict:
    """Precomputed backtest comparison (MAE/RMSE) across Naive, Linear Regression, Random
    Forest per-country, Random Forest pooled, and ETS(A,Ad,N) -- a static artifact, not
    computed live."""
    client = get_client()
    return await client.get("/forecasts/model-comparison")
