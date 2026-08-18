"""Real connectivity test: launches a real `services/mcp-server` subprocess on
streamable-HTTP (via the `running_mcp_server` fixture, `conftest.py`) and confirms
`MultiServerMCPClient.get_tools()` actually lists all 14 tools -- mirrors this project's
direct-client-smoke-test discipline (real subprocess, not a mocked MCP client), and specifically
`services/mcp-server/tests/test_entry_point.py`'s pattern of pointing `API_BASE_URL` at an
unreachable address, since listing tools never calls a tool.
"""

from __future__ import annotations

from agent.mcp_client import build_mcp_client

EXPECTED_TOOLS = {
    "list_countries",
    "get_country_profile",
    "get_historical_emissions",
    "get_gas_composition_by_decade",
    "get_forecast",
    "get_forecast_summary",
    "get_forecast_comparison",
    "get_model_comparison",
    "get_scenario_projection",
    "get_scenario_cumulative_impact",
    "compare_scenarios_across_countries",
    "get_top_emitters",
    "get_methodology_notes",
    "get_emissions_change_summary",
}


async def test_get_tools_lists_all_fourteen(running_mcp_server):
    client = build_mcp_client(running_mcp_server)
    tools = await client.get_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
