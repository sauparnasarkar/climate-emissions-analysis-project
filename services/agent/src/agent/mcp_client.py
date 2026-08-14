"""MCP client wiring -- connects to `services/mcp-server` over streamable-HTTP.

Co-located deployment (SPEC.md "Corrections applied" #4): this agent and `services/mcp-server`
run on the same Mac Mini, so the connection is plain, unauthenticated localhost -- the same B3
trust boundary `services/mcp-server` already uses for its own calls to `api/`. No Cloudflare
Access headers here; those are only for external clients (Claude Desktop, testers) reaching
`services/mcp-server` from outside the machine.

`MultiServerMCPClient` cannot be used as an async context manager (confirmed against
langchain-mcp-adapters' source, 2026-08-13) -- construct it, then `await client.get_tools()`.
"""

import os

from langchain_mcp_adapters.client import MultiServerMCPClient

DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8765/mcp"


def get_mcp_server_url() -> str:
    return os.environ.get("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)


def build_mcp_client(server_url: str | None = None) -> MultiServerMCPClient:
    url = server_url or get_mcp_server_url()
    return MultiServerMCPClient(
        {
            "climate-emissions-mcp-server": {
                "url": url,
                "transport": "http",
            }
        }
    )


async def get_mcp_tools(server_url: str | None = None):
    """Fetches the current tool list from `services/mcp-server` as LangChain-compatible tools.

    Stateless per call, matching `MultiServerMCPClient`'s own default -- no server-side caching
    of the tool list beyond what LangGraph's own message history naturally avoids re-fetching.
    """
    client = build_mcp_client(server_url)
    return await client.get_tools()
