"""Tests for the admin LLM-switch endpoints -- SPEC.md §14. Lifespan never runs under a bare
`TestClient(app)` (no `with` context manager, matching the rest of this test file's style), so
`app.state.mcp_tools`/`checkpointer`/`llm_choice` are set up directly by the `admin_state`
fixture rather than relying on the real startup sequence -- same reasoning as `test_server.py`'s
`app.dependency_overrides[get_graph]` pattern, just without a Depends indirection since these
endpoints read `request.app.state` directly.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from agent import server, settings
from agent.graph import _default_checkpointer
from agent.graph import build_graph as real_build_graph
from agent.server import LlmChoiceResponse, app


@pytest.fixture
def admin_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_ADMIN_STORE_PATH", str(tmp_path / "llm_choice.json"))
    initial = settings.choice_by_id("anthropic-sonnet")
    app.state.mcp_tools = []
    app.state.checkpointer = _default_checkpointer()
    app.state.llm_choice = LlmChoiceResponse(
        provider=initial.provider, model=initial.model, label=initial.label, updated_at=settings.now_iso()
    )
    app.state.graph = None
    yield


def test_get_llm_choice_reports_current_state(admin_state):
    client = TestClient(app)
    response = client.get("/admin/llm")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-5"


def test_post_llm_choice_switches_and_persists(admin_state):
    client = TestClient(app)
    response = client.post("/admin/llm", json={"id": "ollama-qwen14b-ctx8k"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:14b-ctx8k"

    # Live in-memory state actually changed...
    assert app.state.llm_choice.provider == "ollama"
    assert app.state.graph is not None

    # ...and so did the persisted store, so the choice survives a restart.
    stored = settings.read_stored_choice()
    assert stored is not None
    assert stored.provider == "ollama"
    assert stored.model == "qwen2.5:14b-ctx8k"


def test_post_llm_choice_rejects_unknown_id(admin_state):
    client = TestClient(app)
    response = client.post("/admin/llm", json={"id": "not-a-real-choice"})
    assert response.status_code == 422
    # Nothing changed -- still the fixture's initial anthropic-sonnet choice.
    assert app.state.llm_choice.provider == "anthropic"
    assert app.state.graph is None


def test_post_llm_choice_build_failure_leaves_previous_graph_running(admin_state, monkeypatch):
    previous_graph = app.state.graph

    async def _failing_build_graph(**kwargs):
        raise RuntimeError("services/mcp-server unreachable")

    monkeypatch.setattr(server, "build_graph", _failing_build_graph)

    client = TestClient(app)
    response = client.post("/admin/llm", json={"id": "ollama-qwen14b-ctx8k"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Claude Sonnet 5" in detail  # curated message names the still-running model...
    assert "services/mcp-server unreachable" not in detail  # ...never the raw exception text

    # Build-before-swap: a failed rebuild must leave the previous state untouched.
    assert app.state.graph is previous_graph
    assert app.state.llm_choice.provider == "anthropic"
    assert settings.read_stored_choice() is None  # never persisted a choice that failed to apply


async def test_apply_llm_choice_lock_serializes_concurrent_calls(admin_state, monkeypatch):
    events: list[str] = []

    async def _slow_build_graph(*, llm, mcp_tools, checkpointer):
        events.append("start")
        await asyncio.sleep(0.05)
        events.append("end")
        return await real_build_graph(llm=llm, mcp_tools=mcp_tools, checkpointer=checkpointer)

    monkeypatch.setattr(server, "build_graph", _slow_build_graph)

    choice_a = settings.choice_by_id("anthropic-sonnet")
    choice_b = settings.choice_by_id("ollama-qwen14b-ctx8k")
    await asyncio.gather(
        server._apply_llm_choice(app, choice_a),
        server._apply_llm_choice(app, choice_b),
    )

    # If the lock serialized the two calls, each call's start/end pair is contiguous -- an
    # interleaved ["start", "start", "end", "end"] would mean both ran concurrently instead.
    assert events == ["start", "end", "start", "end"]
