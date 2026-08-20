"""Unit tests for settings.py's persisted-choice store and resolution precedence -- no
network calls, always runs. `AGENT_ADMIN_STORE_PATH` is monkeypatched to a tmp_path file in
every test so nothing here ever touches a real machine path.
"""

from __future__ import annotations

import pytest

from agent import settings


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_ADMIN_STORE_PATH", str(tmp_path / "llm_choice.json"))
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AGENT_LLM_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)


def test_read_stored_choice_missing_file_returns_none():
    assert settings.read_stored_choice() is None


def test_read_stored_choice_malformed_json_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "llm_choice.json"
    path.write_text("not json")
    monkeypatch.setenv("AGENT_ADMIN_STORE_PATH", str(path))
    assert settings.read_stored_choice() is None


def test_read_stored_choice_off_allowlist_returns_none(tmp_path, monkeypatch):
    path = tmp_path / "llm_choice.json"
    path.write_text('{"provider": "ollama", "model": "llama3.1:8b", "updated_at": "2026-01-01T00:00:00+00:00"}')
    monkeypatch.setenv("AGENT_ADMIN_STORE_PATH", str(path))
    assert settings.read_stored_choice() is None


def test_write_then_read_round_trips():
    choice = settings.LlmChoice(provider="ollama", model="qwen2.5:14b-ctx8k", updated_at=settings.now_iso())
    settings.write_stored_choice(choice)
    read_back = settings.read_stored_choice()
    assert read_back is not None
    assert read_back.provider == "ollama"
    assert read_back.model == "qwen2.5:14b-ctx8k"


def test_resolve_prefers_stored_choice_over_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    choice = settings.LlmChoice(provider="ollama", model="qwen2.5:14b-ctx8k", updated_at=settings.now_iso())
    settings.write_stored_choice(choice)

    resolved = settings.resolve_active_choice()
    assert resolved.id == "ollama-qwen14b-ctx8k"


def test_resolve_falls_back_to_env_when_store_absent(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5:14b-ctx8k")

    resolved = settings.resolve_active_choice()
    assert resolved.id == "ollama-qwen14b-ctx8k"


def test_resolve_falls_back_to_code_default_when_nothing_set():
    resolved = settings.resolve_active_choice()
    assert resolved is settings.DEFAULT_CHOICE
    assert resolved.id == "anthropic-sonnet"


def test_resolve_ignores_off_allowlist_env_and_falls_back_to_default(monkeypatch):
    # llm.py's own DEFAULT_OLLAMA_MODEL (llama3.1:8b) is intentionally not on the admin
    # allow-list -- SPEC.md §14.2 -- so this must fall through to the code default, not error.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)

    resolved = settings.resolve_active_choice()
    assert resolved is settings.DEFAULT_CHOICE


def test_choice_by_id_known_and_unknown():
    assert settings.choice_by_id("anthropic-sonnet") is not None
    assert settings.choice_by_id("not-a-real-id") is None
