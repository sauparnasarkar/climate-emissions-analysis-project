"""Regression test for the module-duplication pitfall documented at the bottom of
server.py: running the server as `python -m mcp_server.server` (rather than
`python -m mcp_server`) loads it a second time under the name "mcp_server.server", separate
from its own "__main__" instance, so `tools/*.py`'s `from ..server import mcp` binds to a
different MCPServer object than the one `main()` actually runs -- silently registering only
`list_countries` (the one tool defined above the `from .tools import ...` line) instead of
all 14. No in-process import test can catch this; it only reproduces via a real subprocess
launched the way an MCP client actually launches this server, which is what this test does.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")

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


async def test_entry_point_registers_every_tool():
    # API_BASE_URL points nowhere reachable -- list_tools() only enumerates registrations,
    # it never calls a tool, so no real (or fixture) api/ backend is needed for this check.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        env={"MCP_TRANSPORT": "stdio", "API_BASE_URL": "http://127.0.0.1:1/api", "PYTHONPATH": SRC_DIR},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
    assert names == EXPECTED_TOOLS


def test_legacy_module_entry_point_fails_loudly():
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=Path(__file__).resolve().parents[1],
        env={"PYTHONPATH": SRC_DIR},
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "Use `python -m mcp_server`, not `python -m mcp_server.server`." in proc.stderr
