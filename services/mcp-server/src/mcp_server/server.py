"""MCPServer app instantiation, tool registration, and transport entry point.

Transport is Streamable HTTP by default, with stdio available as a local-dev fallback
(SPEC.md §2/§7) -- select via the MCP_TRANSPORT env var. The HTTP host stays hardcoded to
127.0.0.1 even once deployed behind the Cloudflare Tunnel (SPEC.md §8.3) -- Cloudflare Access
gates the published route at the edge before a request ever reaches this machine, so a public
bind was never needed; 127.0.0.1 plus the Tunnel's own network isolation is defense in depth,
not a stopgap for missing auth. DNS-rebinding protection (`transport_security`, only active
when DEPLOY_BASE_PATH is set -- see `_streamable_http_settings`) is the actual new hardening
this file adds for the public deploy; app-layer request auth (boundary B4 in SPEC.md §8.1) is
Cloudflare Access's job, not this server's -- see SPEC.md §8.2 for why.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .client import get_client

DEFAULT_STREAMABLE_HTTP_PORT = 8765


def _normalize_deploy_prefix(raw: str | None) -> str:
    """Mirrors api/main.py's own _normalize_deploy_prefix -- hand-mirrored 1:1, not shared
    code, since the two services don't share a dependency graph. Returns "" for an unset or
    root ("/") prefix, otherwise a leading-slash, no-trailing-slash form."""
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")


def _streamable_http_settings(deploy_base_path: str | None) -> tuple[str, TransportSecuritySettings | None]:
    """The streamable_http_path and transport_security to pass to mcp.run(), derived from
    DEPLOY_BASE_PATH -- the same env var api/main.py and vite.config.ts already share
    (ARCHITECTURE.md §5/§6). Its presence is this codebase's existing signal for "deployed
    behind the Cloudflare Tunnel"; reused here rather than inventing a second switch.

    Unset (local/stdio dev): default "/mcp" path, transport_security=None -- passing None (not
    an empty TransportSecuritySettings) is what preserves today's permissive behavior, since
    TransportSecurityMiddleware only disables DNS-rebinding protection entirely when its
    settings argument is None; an empty settings object's allowed_hosts/allowed_origins default
    to [], which would reject every request instead.

    Set (deployed behind the Tunnel): the deploy-prefixed path (e.g.
    /ghg-emissions-analysis/mcp), and transport_security locked to the one hostname/origin the
    Tunnel actually forwards (SPEC.md §8.3) -- left unset here, every request would 401 with no
    obvious cause once real traffic arrives carrying Host: labs.syena.io. allowed_hosts also
    carries the co-located loopback host/port this same deploy is reachable on directly
    (127.0.0.1:8765 and localhost:8765, DEFAULT_STREAMABLE_HTTP_PORT below) --
    services/agent's B3 connection (services/agent/CLAUDE.md) never goes through the Tunnel at
    all, so it always carries a loopback Host header, never labs.syena.io. Confirmed missing
    live: a real deploy dry-run got 421 Misdirected Request on this exact request, only fixed by
    spoofing Host: labs.syena.io -- see SPEC.md §8 for the corrected write-up. allowed_origins
    stays locked to labs.syena.io only -- Origin is a browser-only header this server-to-server
    connection never sends, so widening it would add no coverage.

    The security toggle is keyed off deploy_base_path itself, not the normalized prefix --
    DEPLOY_BASE_PATH="/" is a legitimate "deployed at root, no prefix" value (the same case
    api/main.py's own _normalize_deploy_prefix("/") == "" already treats as deliberate, not
    unset), and normalizes to an empty, falsy prefix. Keying off the prefix instead would
    silently drop DNS-rebinding protection for that real deploy configuration -- path-prefixing
    and security-hardening must not be coupled through the same falsy-empty-string check.
    """
    prefix = _normalize_deploy_prefix(deploy_base_path)
    path = f"{prefix}/mcp"
    is_deployed = bool(deploy_base_path)
    security = (
        TransportSecuritySettings(
            allowed_hosts=[
                "labs.syena.io",
                f"127.0.0.1:{DEFAULT_STREAMABLE_HTTP_PORT}",
                f"localhost:{DEFAULT_STREAMABLE_HTTP_PORT}",
            ],
            allowed_origins=["https://labs.syena.io"],
        )
        if is_deployed
        else None
    )
    return path, security


SERVER_INSTRUCTIONS = """\
Climate emissions data for a curated set of countries (featured/expanded/sovereign tiers --
see list_countries). For any request comparing multiple countries -- growth, trends,
rankings, forecasts -- prefer the one tool built for that (get_historical_emissions,
get_gas_composition_by_decade, get_top_emitters, get_forecast_comparison,
get_scenario_cumulative_impact, compare_scenarios_across_countries,
get_emissions_change_summary) over calling a
single-country tool (get_country_profile, get_forecast, get_scenario_projection) once per
country. The
multi-country tools return a real, data-ranked, reproducible set when you don't name
specific countries, in one call instead of one round trip per country; picking countries
yourself and looping a single-country tool does neither. This includes comparisons that
want per-capita/growth-rate context or full forecast series/confidence intervals, not just
raw totals or 2030/2035/2040 snapshots -- get_historical_emissions carries per-capita
(every gas) and, for CO2, year-over-year % growth and carbon intensity alongside the raw
series, and get_forecast_comparison carries the same full historical/holdout/forecast/CI
detail as get_forecast, just for many countries in one call. "Projection"/"forecast" with no
scenario language means the single ETS statistical trajectory (the get_forecast family); route
to the scenario tools (the get_scenario_projection family) only when the question explicitly
invokes scenarios, policy pathways, or BAU/Moderate/Aggressive. For "how many countries
increased/decreased" or "biggest movers since 1990" questions, use
get_emissions_change_summary -- it returns real counts and a bounded top-N list computed
server-side, not a per-country series you'd have to eyeball or count yourself.\
"""

mcp = MCPServer("climate-emissions", instructions=SERVER_INSTRUCTIONS)


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
        streamable_http_path, transport_security = _streamable_http_settings(os.environ.get("DEPLOY_BASE_PATH"))
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=port,
            streamable_http_path=streamable_http_path,
            transport_security=transport_security,
        )
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
