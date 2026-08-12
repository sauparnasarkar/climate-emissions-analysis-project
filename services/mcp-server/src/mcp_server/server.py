"""FastMCP app instantiation and tool registration point.

Transport configuration (Streamable HTTP + stdio fallback, SPEC.md §2/§7) is Step 4 work --
this module only wires up the server object and its tools so it can be imported and tested
independently of how it's eventually run.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .client import get_client
from .resolution import CountryLists

mcp = MCPServer("climate-emissions")


@mcp.tool()
async def list_countries() -> dict:
    """List the three country scopes this server understands: 'featured' (10, curated),
    'expanded' (~40, data-driven by coverage/materiality), and 'sovereign' (~218, every
    real country). Call this first to resolve a country name before any other tool, and
    use len(sovereign) as the denominator whenever another tool's response mentions how
    many countries were shown out of the full sovereign scope."""
    client = get_client()
    return await client.get("/countries")


async def get_country_lists() -> CountryLists:
    """Fetch the current country lists, wrapped for the resolution guard (resolution.py)."""
    client = get_client()
    data = await client.get("/countries")
    return CountryLists(
        featured=data["featured"],
        expanded=data["expanded"],
        sovereign=data["sovereign"],
    )


if __name__ == "__main__":
    mcp.run()
