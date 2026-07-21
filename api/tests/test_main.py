import importlib

import pytest
from fastapi.testclient import TestClient

from api.main import _normalize_deploy_prefix


def test_normalize_deploy_prefix():
    assert _normalize_deploy_prefix(None) == ""
    assert _normalize_deploy_prefix("/") == ""
    assert _normalize_deploy_prefix("prefix") == "/prefix"
    assert _normalize_deploy_prefix("/prefix/") == "/prefix"
    assert _normalize_deploy_prefix("prefix/") == "/prefix"


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_cors_headers_present(client):
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.fixture
def reloaded_main(monkeypatch):
    """Reloads api.main with DEPLOY_BASE_PATH set to a given value (or unset for None), since
    DEPLOY_PATH_PREFIX is computed once at import time from the environment. Always restores
    the module to its default (no prefix) state afterward so later tests in the session see
    the expected default behavior regardless of execution order."""
    import api.main as main_module

    def _reload_with(prefix_env_value):
        if prefix_env_value is None:
            monkeypatch.delenv("DEPLOY_BASE_PATH", raising=False)
        else:
            monkeypatch.setenv("DEPLOY_BASE_PATH", prefix_env_value)
        importlib.reload(main_module)
        return main_module

    yield _reload_with

    monkeypatch.delenv("DEPLOY_BASE_PATH", raising=False)
    importlib.reload(main_module)


def test_middleware_passthrough_when_no_prefix_configured(reloaded_main):
    main_module = reloaded_main(None)
    resp = TestClient(main_module.app).get("/api/health")
    assert resp.status_code == 200


def test_middleware_strips_configured_prefix(reloaded_main):
    main_module = reloaded_main("ghg-emissions-analysis")
    resp = TestClient(main_module.app).get("/ghg-emissions-analysis/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_middleware_still_serves_bare_path_once_configured(reloaded_main):
    """Per the class docstring, a configured prefix must not break direct/local
    (Tailscale) access — the bare /api/... path stays reachable alongside the
    prefixed one, since Cloudflare Tunnel is only one of two ways in."""
    main_module = reloaded_main("ghg-emissions-analysis")
    resp = TestClient(main_module.app).get("/api/health")
    assert resp.status_code == 200


def test_middleware_respects_path_boundary(reloaded_main):
    """A request for a prefix-plus-suffix path that isn't really under our prefix (e.g.
    another deployment's /ghg-emissions-analysis-v2/...) must not be stripped — a plain
    startswith() would incorrectly match it, but so would a correct boundary check (both
    just 404, since the malformed leftover after naive stripping can never coincidentally
    spell out a real /api/... route either way — this doesn't actually discriminate
    correct-vs-buggy behavior).

    A prefix that is itself a literal substring of a real route path does discriminate: with
    the correct boundary check, "/api/heal" is not a real wrapping prefix of "/api/health"
    (no "/" immediately follows it), so the path is left untouched and resolves normally
    (200). A plain startswith() would incorrectly treat it as a prefix, strip it down to the
    nonsense path "th", and 404 a request that should have succeeded.
    """
    main_module = reloaded_main("api/heal")
    resp = TestClient(main_module.app).get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
