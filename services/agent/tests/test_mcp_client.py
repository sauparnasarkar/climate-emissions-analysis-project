"""Real connectivity test: launches a real `services/mcp-server` subprocess on
streamable-HTTP and confirms `MultiServerMCPClient.get_tools()` actually lists all 13 tools --
mirrors this project's direct-client-smoke-test discipline (real subprocess, not a mocked MCP
client), and specifically `services/mcp-server/tests/test_entry_point.py`'s pattern of pointing
`API_BASE_URL` at an unreachable address, since listing tools never calls a tool.

Uses `services/mcp-server`'s own venv interpreter to launch the subprocess -- this repo's
convention is one isolated venv per `services/*` sub-project (see both `pyproject.toml`s), so
`services/agent`'s own venv deliberately does not carry the MCP SDK as a dependency; it only
needs `langchain-mcp-adapters` to *speak* MCP as a client, not the server SDK itself.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent.mcp_client import build_mcp_client

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER_SRC = REPO_ROOT / "services" / "mcp-server" / "src"
MCP_SERVER_VENV_PYTHON = REPO_ROOT / "services" / "mcp-server" / ".venv" / "bin" / "python"

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
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_mcp_server():
    if not MCP_SERVER_VENV_PYTHON.exists():
        pytest.skip("services/mcp-server/.venv not present -- run its own setup first")

    port = _free_port()
    proc = subprocess.Popen(
        [str(MCP_SERVER_VENV_PYTHON), "-m", "mcp_server"],
        cwd=str(REPO_ROOT / "services" / "mcp-server"),
        env={
            "MCP_TRANSPORT": "streamable-http",
            "MCP_SERVER_PORT": str(port),
            "API_BASE_URL": "http://127.0.0.1:1/api",
            "PYTHONPATH": str(MCP_SERVER_SRC),
            "PATH": "/usr/bin:/bin",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        url = f"http://127.0.0.1:{port}/mcp"
        deadline = time.monotonic() + 10
        last_error = None
        while time.monotonic() < deadline:
            try:
                # A bare GET without a session is expected to 4xx once the server is up --
                # any HTTP response at all means the port is accepting connections.
                httpx.get(url, timeout=0.5)
                break
            except httpx.ConnectError as exc:
                last_error = exc
                time.sleep(0.2)
        else:
            proc.terminate()
            out, _ = proc.communicate(timeout=5)
            raise RuntimeError(f"mcp-server never came up on {url}: {last_error}\n{out}")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def test_get_tools_lists_all_thirteen(running_mcp_server):
    client = build_mcp_client(running_mcp_server)
    tools = await client.get_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
