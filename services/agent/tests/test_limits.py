"""The `/query` abuse limits -- concurrency, per-client hour, per-day budget (limits.py)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agent import limits, server
from agent.limits import QueryLimiter, client_key


@pytest.fixture(autouse=True)
def _limits_env(monkeypatch):
    for name in ("AGENT_MAX_CONCURRENT_QUERIES", "AGENT_QUERIES_PER_IP_PER_HOUR", "AGENT_DAILY_QUERY_BUDGET"):
        monkeypatch.delenv(name, raising=False)


def test_concurrency_cap_refuses_then_frees_when_a_slot_is_released(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_CONCURRENT_QUERIES", "2")
    limiter = QueryLimiter()
    first = limiter.acquire("a")
    limiter.acquire("b")
    with pytest.raises(HTTPException) as exc:
        limiter.acquire("c")
    assert exc.value.status_code == 503 and exc.value.headers["Retry-After"] == "10"
    first.release()
    first.release()  # idempotent: a second release must not free a slot it no longer holds
    limiter.acquire("c")
    with pytest.raises(HTTPException):
        limiter.acquire("d")


def test_per_client_allowance_is_per_client_and_slides(monkeypatch):
    monkeypatch.setenv("AGENT_QUERIES_PER_IP_PER_HOUR", "2")
    limiter = QueryLimiter()
    for _ in range(2):
        limiter.acquire("a", now=0).release()
    with pytest.raises(HTTPException) as exc:
        limiter.acquire("a", now=10)
    assert exc.value.status_code == 429 and int(exc.value.headers["Retry-After"]) == 3590
    limiter.acquire("b", now=10).release()  # another client is unaffected
    limiter.acquire("a", now=3600).release()  # the window has slid past the first query


def test_a_refused_query_does_not_count_against_the_client_or_the_day(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_CONCURRENT_QUERIES", "1")
    monkeypatch.setenv("AGENT_QUERIES_PER_IP_PER_HOUR", "2")
    limiter = QueryLimiter()
    slot = limiter.acquire("a", now=0)
    for _ in range(5):
        with pytest.raises(HTTPException):
            limiter.acquire("a", now=1)  # refused for concurrency
    slot.release()
    limiter.acquire("a", now=2).release()  # only two admitted so far, so this is the second and last
    with pytest.raises(HTTPException) as exc:
        limiter.acquire("a", now=3)
    assert exc.value.status_code == 429


def test_daily_budget_resets_on_a_new_utc_day(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_QUERY_BUDGET", "2")
    limiter = QueryLimiter()
    limiter.acquire("a", today="2026-10-13").release()
    limiter.acquire("b", today="2026-10-13").release()
    with pytest.raises(HTTPException) as exc:
        limiter.acquire("c", today="2026-10-13")
    assert exc.value.status_code == 503 and "tomorrow" in exc.value.detail
    limiter.acquire("c", today="2026-10-14").release()


def test_zero_disables_a_limit_and_a_bad_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("AGENT_QUERIES_PER_IP_PER_HOUR", "0")
    monkeypatch.setenv("AGENT_DAILY_QUERY_BUDGET", "not-a-number")
    limiter = QueryLimiter()
    assert limiter.daily_budget() == limits.DEFAULT_DAILY_BUDGET
    for _ in range(200):
        limiter.acquire("a", now=0).release()


def test_stale_clients_are_pruned_past_the_table_bound(monkeypatch):
    monkeypatch.setattr(limits, "MAX_TRACKED_CLIENTS", 3)
    limiter = QueryLimiter()
    for i in range(3):
        limiter.acquire(f"old{i}", now=0).release()
    limiter.acquire("new", now=5000).release()
    assert set(limiter._per_client) == {"new"}


def test_client_key_prefers_the_cloudflare_header_then_the_socket_peer():
    class Req:
        def __init__(self, headers, host):
            self.headers, self.client = headers, type("C", (), {"host": host})() if host else None

    assert client_key(Req({"cf-connecting-ip": " 203.0.113.9 "}, "127.0.0.1")) == "203.0.113.9"
    assert client_key(Req({}, "127.0.0.1")) == "127.0.0.1"
    assert client_key(Req({}, None)) == "unknown"


def test_the_query_endpoint_refuses_over_budget_before_any_llm_work(monkeypatch):
    monkeypatch.setenv("AGENT_QUERIES_PER_IP_PER_HOUR", "1")
    monkeypatch.setattr(server, "_query_limiter", QueryLimiter())
    started = []

    async def fake_stream(graph, query, thread_id, trace_id, slot=None):
        started.append(query)
        try:
            yield {"event": "result", "data": "{}"}
        finally:
            if slot is not None:
                slot.release()

    monkeypatch.setattr(server, "stream_query", fake_stream)
    server.app.dependency_overrides[server.get_graph] = lambda: None
    try:
        client = TestClient(server.app)
        headers = {"cf-connecting-ip": "198.51.100.7"}
        assert client.post("/query", json={"query": "hi"}, headers=headers).status_code == 200
        second = client.post("/query", json={"query": "again"}, headers=headers)
        assert second.status_code == 429
        assert "try again later" in second.json()["detail"]
        assert started == ["hi"]
        assert server._query_limiter._in_flight == 0  # the first query's slot was given back
    finally:
        server.app.dependency_overrides.clear()


def test_a_malformed_thread_id_is_refused_without_using_up_any_allowance(monkeypatch):
    # Regression (Copilot, PR #301): admission used to run before thread_id validation, so repeated 400s drained the client's
    # hourly allowance and the global daily budget and then denied valid queries.
    monkeypatch.setenv("AGENT_QUERIES_PER_IP_PER_HOUR", "2")
    monkeypatch.setenv("AGENT_DAILY_QUERY_BUDGET", "2")
    limiter = QueryLimiter()
    monkeypatch.setattr(server, "_query_limiter", limiter)
    server.app.dependency_overrides[server.get_graph] = lambda: None
    try:
        client = TestClient(server.app)
        for _ in range(10):
            assert client.post("/query", json={"query": "hi", "thread_id": "not-a-uuid"}).status_code == 400
        assert limiter._day_count == 0 and not limiter._per_client and limiter._in_flight == 0
    finally:
        server.app.dependency_overrides.clear()
