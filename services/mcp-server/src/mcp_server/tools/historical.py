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

    IMPORTANT: each entry in `countries` must be a real country's common English name (e.g.
    "China", "United States", "United Kingdom"), never an ISO code or abbreviation ("CHN",
    "USA") -- the resolution guard fuzzy-matches against full names and will reject or badly
    mismatch a code.

    Each series also carries `per_capita` (for whichever `gas` was requested), plus, for
    `gas="co2"` only, `yoy_pct_change` and `per_gdp` (carbon intensity) -- OWID doesn't
    compute year-over-year growth or per-GDP figures for methane/nitrous_oxide, so both are
    `None` for those gases rather than a fabricated value. `per_gdp` (and, in the most
    recent year or two, `yoy_pct_change`) can also be `None` for gas="co2" simply because
    OWID's GDP figures lag its emissions figures by a year or two -- that's missing source
    data, not a tool error; don't describe it as broken. This tool is the right one for a
    MULTI-country comparison even when you want per-capita/growth/intensity context, not
    just raw totals -- do not call get_country_profile once per country instead; that
    produces the same non-reproducible, arbitrary country selection problem described above,
    just with an extra tool.
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

    IMPORTANT: each entry in `countries` must be a real country's common English name (e.g.
    "China", "United States", "United Kingdom"), never an ISO code or abbreviation ("CHN",
    "USA") -- the resolution guard fuzzy-matches against full names and will reject or badly
    mismatch a code.
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
