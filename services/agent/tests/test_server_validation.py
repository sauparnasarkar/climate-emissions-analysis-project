"""Direct unit tests for server.py's own logic -- thread_id validation/bounding, progress
percent, and deploy-prefix normalization -- kept separate from test_server.py's HTTP-level
tests. Uses monkeypatch on the module-level `_live_thread_ids` set so these tests can't leak
state into each other or into test_server.py's tests (that set is process-global by design,
matching MemorySaver's own process-lifetime scope).
"""

import uuid

import pytest
from fastapi import HTTPException

from agent import server


@pytest.fixture(autouse=True)
def _isolated_thread_registry(monkeypatch):
    monkeypatch.setattr(server, "_live_thread_ids", set())


def test_thread_id_none_mints_a_valid_uuid():
    minted = server._validate_and_register_thread_id(None)
    uuid.UUID(minted)  # raises if not a valid UUID
    assert minted in server._live_thread_ids


def test_thread_id_valid_uuid_passes_through():
    given = str(uuid.uuid4())
    result = server._validate_and_register_thread_id(given)
    assert result == given
    assert given in server._live_thread_ids


def test_thread_id_malformed_rejected():
    with pytest.raises(HTTPException) as exc_info:
        server._validate_and_register_thread_id("not-a-uuid")
    assert exc_info.value.status_code == 400


def test_thread_id_reuse_does_not_double_count_against_cap(monkeypatch):
    monkeypatch.setattr(server, "MAX_LIVE_THREADS", 1)
    thread_id = str(uuid.uuid4())
    server._validate_and_register_thread_id(thread_id)
    # Same thread_id again -- must not be rejected just because the cap is already at 1.
    result = server._validate_and_register_thread_id(thread_id)
    assert result == thread_id


def test_thread_id_cap_rejects_new_thread_once_full(monkeypatch):
    monkeypatch.setattr(server, "MAX_LIVE_THREADS", 1)
    server._validate_and_register_thread_id(str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        server._validate_and_register_thread_id(str(uuid.uuid4()))
    assert exc_info.value.status_code == 503


def test_freshly_minted_thread_id_is_also_subject_to_the_cap(monkeypatch):
    # Regression test: the None-input branch must register/count the minted id too -- every new
    # conversation's first query takes this branch, so a version that returns early without
    # registering would mean the cap never actually bounds the common case.
    monkeypatch.setattr(server, "MAX_LIVE_THREADS", 1)
    server._validate_and_register_thread_id(None)
    with pytest.raises(HTTPException) as exc_info:
        server._validate_and_register_thread_id(None)
    assert exc_info.value.status_code == 503


def test_progress_percent_caps_at_ninety():
    assert server._progress_percent(1) == 15
    assert server._progress_percent(6) == 90
    assert server._progress_percent(50) == 90


def test_normalize_deploy_prefix():
    assert server._normalize_deploy_prefix(None) == ""
    assert server._normalize_deploy_prefix("/") == ""
    assert server._normalize_deploy_prefix("ghg-emissions-analysis/agent") == "/ghg-emissions-analysis/agent"
    assert server._normalize_deploy_prefix("/ghg-emissions-analysis/agent/") == "/ghg-emissions-analysis/agent"


def test_normalize_deploy_prefix_for_the_release_20_root_deploy():
    # Release 20 (root SPEC.md §5.25): on climate-analytics.syena.io the tunnel forwards /agent/...
    # with no stripping, so the agent's DEPLOY_BASE_PATH becomes "/agent/" (was
    # "/ghg-emissions-analysis/agent/") and must strip exactly that one segment.
    assert server._normalize_deploy_prefix("/agent/") == "/agent"


def test_cors_allows_the_release_20_subdomain_and_rejects_strangers():
    from fastapi.testclient import TestClient

    client = TestClient(server.app)
    ok = client.get("/health", headers={"Origin": "https://climate-analytics.syena.io"})
    assert ok.headers.get("access-control-allow-origin") == "https://climate-analytics.syena.io"
    bad = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in bad.headers
