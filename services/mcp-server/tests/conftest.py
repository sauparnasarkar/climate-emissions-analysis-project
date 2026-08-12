"""Shared fixtures for the mcp-server test suite.

Reuses api/tests/conftest.py's fixture-CSV pattern directly (same FIXTURE_COUNTRIES,
data_dir, full_data) rather than duplicating it -- these tests exercise the real api/
FastAPI app mounted in-process via an ASGI transport, never a real running server and
never the real (gitignored) data/ CSVs, matching that suite's own convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.main import app as api_app  # noqa: E402
from api.tests.conftest import (  # noqa: E402, F401
    FIXTURE_COUNTRIES,
    OUT_OF_SCOPE_COUNTRY,
    data_dir,
    full_data,
    write_selected_countries_json,
)

import mcp_server.client as mcp_client  # noqa: E402
from mcp_server.client import ApiClient  # noqa: E402


@pytest.fixture
def api_client(full_data) -> ApiClient:
    """An ApiClient wired directly into the api/ FastAPI app in-process (ASGI transport, no
    real server on a real port), and also installed as the module-level singleton so tool
    functions under test (which call client.get_client() internally) see the same fixture
    data as a direct ApiClient.get() call in the same test.
    """
    transport = httpx.ASGITransport(app=api_app)
    client = ApiClient(base_url="http://testserver/api", transport=transport)
    mcp_client.set_client(client)
    yield client
    mcp_client.set_client(None)
