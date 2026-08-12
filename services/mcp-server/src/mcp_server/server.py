"""MCPServer app instantiation, tool registration, and transport entry point.

Transport is Streamable HTTP by default, with stdio available as a local-dev fallback
(SPEC.md §2/§7) -- select via the MCP_TRANSPORT env var. The HTTP host is hardcoded to
127.0.0.1 rather than configurable: api/ has no auth layer yet (see this repo's
project_api_no_auth_yet memory), and this server is a thin, unauthenticated pass-through to
it, so it must not be reachable from outside the machine it runs on. That's a V1 constraint,
not a permanent one -- revisit once real service-account auth exists (SPEC.md §2.1).
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from .client import get_client

DEFAULT_STREAMABLE_HTTP_PORT = 8765

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


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "streamable-http":
        port = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_STREAMABLE_HTTP_PORT))
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port)
    elif transport == "stdio":
        mcp.run(transport="stdio")
    else:
        raise ValueError(f"Unknown MCP_TRANSPORT '{transport}' -- use 'streamable-http' or 'stdio'")


# `python -m mcp_server.server` must fail loudly rather than silently no-op: running this file
# directly via `-m` loads it a second time under the name "__main__", separate from the
# "mcp_server.server" module tools/*.py's `from ..server import mcp` resolves to. That gives
# you two different MCPServer instances: one (as "__main__") with only the list_countries tool
# defined above the `from .tools import ...` line, and a second (as "mcp_server.server")
# holding all 12 tools, registered when that import statement forces a second, correctly-named
# execution of this same file. See services/mcp-server/__main__.py for the actual entry point,
# which only ever imports this module by its real package name.
if __name__ == "__main__":
    raise SystemExit("Use `python -m mcp_server`, not `python -m mcp_server.server`.")
