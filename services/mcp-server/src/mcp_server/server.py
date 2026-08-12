"""MCPServer app instantiation and tool registration point.

Transport configuration (Streamable HTTP + stdio fallback, SPEC.md §2/§7) is Step 4 work --
this module only wires up the server object and its tools so it can be imported and tested
independently of how it's eventually run.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .client import get_client

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


# Import tool modules for their @mcp.tool() registration side effects -- must come after
# `mcp` is defined above, since each tools/*.py module does `from ..server import mcp`.
from .tools import composed, countries, forecasts, historical, scenarios  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run()
