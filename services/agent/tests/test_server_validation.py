"""Direct unit tests for server.py's own logic -- thread_id validation/bounding, progress
percent, and deploy-prefix normalization -- kept separate from test_server.py's HTTP-level
tests. Uses monkeypatch on the module-level `_live_thread_ids` registry so these tests can't leak
state into each other or into test_server.py's tests (that set is process-global by design,
matching MemorySaver's own process-lifetime scope).
"""

import uuid
from collections import OrderedDict

import pytest
from fastapi import HTTPException

from agent import server


@pytest.fixture(autouse=True)
def _isolated_thread_registry(monkeypatch):
    monkeypatch.setattr(server, "_live_thread_ids", OrderedDict())


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


def test_thread_cap_evicts_the_least_recently_used_thread_instead_of_refusing(monkeypatch):
    monkeypatch.setattr(server, "MAX_LIVE_THREADS", 2)
    evicted = []
    monkeypatch.setattr(server, "_evict_thread", evicted.append)
    first, second, third = (str(uuid.uuid4()) for _ in range(3))
    server._validate_and_register_thread_id(first)
    server._validate_and_register_thread_id(second)
    server._validate_and_register_thread_id(first)  # first is now the most recently used
    server._validate_and_register_thread_id(third)  # full: second is the oldest
    assert evicted == [second]
    assert list(server._live_thread_ids) == [first, third]


def test_a_flood_of_throwaway_ids_never_blocks_a_new_conversation(monkeypatch):
    # Regression test for the 1,000-id lock-out: past the cap every new conversation used to get a 503 until a restart.
    monkeypatch.setattr(server, "MAX_LIVE_THREADS", 5)
    monkeypatch.setattr(server, "_evict_thread", lambda _id: None)
    for _ in range(50):
        server._validate_and_register_thread_id(None)
    assert len(server._live_thread_ids) == 5
    server._validate_and_register_thread_id(None)  # still admitted


def test_eviction_deletes_the_threads_saved_history():
    from agent.graph import _default_checkpointer

    server.app.state.checkpointer = _default_checkpointer()
    seen = []
    server.app.state.checkpointer.delete_thread = seen.append
    server._evict_thread("abc")
    assert seen == ["abc"]


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
    retired = client.get("/health", headers={"Origin": "https://labs.syena.io"})
    assert "access-control-allow-origin" not in retired.headers
