"""SPEC.md §5 composed tools: get_top_emitters, get_methodology_notes.

Neither is a near-1:1 endpoint wrap -- get_top_emitters ranks a raw time-series payload in
memory (no ranked-by-year endpoint exists), and get_methodology_notes isn't endpoint-backed
at all.
"""

from __future__ import annotations

from ..client import get_client
from ..methodology import methodology_notes
from ..server import mcp


@mcp.tool()
async def get_top_emitters(year: int, n: int = 10) -> dict:
    """The top `n` CO2 emitters for a specific `year`, ranked descending. Composed from
    /overview/world-map-series -- fetched fresh on every call, no server-side cache (SPEC.md
    §6.2), since no ranked-by-year endpoint exists to wrap directly. Countries with no data
    at `year` are excluded from the ranking, not treated as zero."""
    client = get_client()
    data = await client.get("/overview/world-map-series")
    try:
        year_idx = data["years"].index(year)
    except ValueError:
        raise ValueError(
            f"No data for year {year}. Available years: {data['years'][0]}-{data['years'][-1]}."
        ) from None

    year_values = data["values"][year_idx]
    ranked = sorted(
        (
            {"country": country, "iso_code": iso_code, "co2": value}
            for country, iso_code, value in zip(data["countries"], data["iso_codes"], year_values)
            if value is not None
        ),
        key=lambda row: row["co2"],
        reverse=True,
    )
    return {"year": year, "emitters": ranked[:n]}


@mcp.tool()
async def get_methodology_notes() -> dict:
    """Static methodology reference: the ETS(A,Ad,N) forecasting explanation, the five-model
    comparison set, OWID dataset provenance/caveats, and expanded-scope selection criteria.
    Not endpoint-backed -- quote this instead of improvising a methodology explanation."""
    return methodology_notes()
