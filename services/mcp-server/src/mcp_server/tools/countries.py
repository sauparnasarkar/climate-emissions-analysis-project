"""SPEC.md §5 direct wrap: get_country_profile."""

from __future__ import annotations

from ..client import get_client
from ..resolution import fetch_country_lists, resolve_country
from ..server import mcp


@mcp.tool()
async def get_country_profile(country: str) -> dict:
    """Full yearly emissions profile for a single country: CO2, per-capita CO2, YoY %
    change, and GHG intensity. Single-country only -- no trimming/scope_note applies.
    `country` is resolved against the expanded (~40-country) scope; a real country outside
    that scope (e.g. one only in the full sovereign list) raises a clear error explaining
    why, rather than a bare 404.

    Do NOT call this once per country to build a multi-country comparison -- that produces
    an arbitrary, non-reproducible country set with no ranking behind it, and costs one
    round trip per country. Use get_historical_emissions instead (omit its `countries` arg,
    pick a `scope`) for a single call that returns a real, data-ranked comparison set. Only
    reach for this tool when the user is asking about one specific country's own numbers.
    """
    lists = await fetch_country_lists()
    resolved = resolve_country(country, lists, scope="expanded")
    client = get_client()
    return await client.get(f"/countries/{resolved}/profile")
