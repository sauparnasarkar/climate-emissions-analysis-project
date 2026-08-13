"""SPEC.md §5 direct wraps: get_historical_emissions, get_gas_composition_by_decade."""

from __future__ import annotations

from ..client import get_client
from ..methodology import SCOPE_LABELS
from ..resolution import fetch_country_lists, resolve_countries
from ..server import mcp
from ..trimming import trim


@mcp.tool()
async def get_historical_emissions(
    countries: list[str] | None = None,
    gas: str = "co2",
    scope: str = "expanded",
) -> dict:
    """Historical yearly emissions time series for one or more countries. `gas` is one of
    co2, methane, nitrous_oxide. `scope` (featured/expanded/sovereign) picks the country
    pool -- pass it explicitly rather than relying on any default. When `countries` is
    omitted, this resolves and passes the entire `scope` pool explicitly, since the
    wrapped API's own no-countries default silently ignores `scope` and always returns the
    same 5 featured countries regardless (SPEC.md §4) -- relying on that default here would
    silently return the wrong data for a non-featured scope. When `countries` is given
    explicitly, each name is still resolved against `scope` so a real-but-out-of-scope
    country raises a clear error instead of silently vanishing from the response.

    When `countries` is omitted and the resolved scope pool has more than 10 countries, the
    response is capped at the 10 with the highest latest-year value and carries a
    `scope_note` explaining the cap (SPEC.md §3.2). An explicit `countries` list is always
    returned in full, uncapped.

    IMPORTANT: only pass `countries` when the user named specific countries. For an
    open-ended request ("how does X compare to other countries", "how has Y grown over
    time") that doesn't name a country list, omit `countries` entirely and pick `scope`
    instead -- that gives a real, data-ranked comparison set (highest latest-year value
    first, with a scope_note saying how it was chosen), not an arbitrary hand-picked one.
    Inventing a country list yourself produces a different, non-reproducible comparison
    each time this tool is called for a similar question.
    """
    lists = await fetch_country_lists()
    omitted = countries is None
    if omitted:
        resolved = lists.pool(scope)
    else:
        resolved = resolve_countries(countries, lists, scope=scope)
    client = get_client()
    body = await client.get(
        "/historical/timeseries",
        params={"countries": resolved, "gas": gas, "scope": scope},
    )
    if omitted:
        trimmed, note = trim(
            body["series"],
            scope_label=SCOPE_LABELS[scope],
            sort_key_label="latest-year value descending",
            sort_key=lambda series: series["values"][-1] if series["values"] else float("-inf"),
        )
        body["series"] = trimmed
        if note is not None:
            body["scope_note"] = note
    return body


@mcp.tool()
async def get_gas_composition_by_decade(
    countries: list[str] | None = None,
    scope: str = "expanded",
) -> dict:
    """Decade-by-decade share of CO2/methane/nitrous oxide for one or more countries, or
    (when `countries` is omitted) aggregated across the entire `scope` pool -- unlike
    get_historical_emissions, this endpoint's own no-countries default already respects
    `scope` correctly, so no extra resolution is needed for the omitted case (SPEC.md §4).
    When `countries` is given explicitly, each name is still resolved against `scope`.

    IMPORTANT: only pass `countries` when the user named specific countries. For an
    open-ended request that doesn't name a country list, omit `countries` and pick `scope`
    instead, for the same reason as get_historical_emissions -- a hand-picked list is an
    arbitrary, non-reproducible choice; the `scope` pool is a real, defined one.
    """
    client = get_client()
    if countries is None:
        return await client.get("/historical/decade-composition", params={"scope": scope})
    lists = await fetch_country_lists()
    resolved = resolve_countries(countries, lists, scope=scope)
    return await client.get(
        "/historical/decade-composition",
        params={"countries": resolved, "scope": scope},
    )
