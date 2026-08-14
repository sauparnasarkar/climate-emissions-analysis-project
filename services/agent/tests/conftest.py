"""Shared fixtures for the services/agent test suite.

`running_mcp_server` launches a real `services/mcp-server` subprocess on streamable-HTTP --
lifted here from `test_mcp_client.py` (Step 1) since `test_graph.py` (Step 2) needs the same
real-server discipline for its data_query-path tests, matching this project's real-data-over-
mocks testing philosophy throughout.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER_SRC = REPO_ROOT / "services" / "mcp-server" / "src"
MCP_SERVER_VENV_PYTHON = REPO_ROOT / "services" / "mcp-server" / ".venv" / "bin" / "python"


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
