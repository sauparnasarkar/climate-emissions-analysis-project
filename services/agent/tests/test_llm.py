"""Unit tests for get_llm()'s construction logic -- no network calls, always runs (unlike
test_llm_smoke.py's one real-network, ANTHROPIC_API_KEY-gated test). ChatOpenAI/ChatAnthropic's
constructors don't validate connectivity, so these just check the resulting object's own
attributes.
"""

import pytest

from agent.llm import DEFAULT_OLLAMA_MODEL, OLLAMA_REQUEST_TIMEOUT_SECONDS, get_llm


def test_ollama_provider_sets_request_timeout(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    llm = get_llm()
    assert llm.request_timeout == OLLAMA_REQUEST_TIMEOUT_SECONDS


def test_ollama_provider_disables_retries(monkeypatch):
    # max_retries=1 (or the ChatOpenAI/openai-SDK default of 2) silently doubles/triples the
    # timeout paragraph's own documented bound on a genuine stall, since a retry just queues
    # behind the still-stuck original request in Ollama's single inference slot rather than
    # actually helping -- reproduced live 2026-08-20 (see llm.py's own docstring): a real query
    # took elapsed=300.546s (2x OLLAMA_REQUEST_TIMEOUT_SECONDS) instead of the intended ~150s.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    llm = get_llm()
    assert llm.max_retries == 0


def test_ollama_provider_defaults_to_llama3(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)
    llm = get_llm()
    assert llm.model_name == DEFAULT_OLLAMA_MODEL


def test_ollama_provider_respects_local_llm_model_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5:14b-ctx8k")
    llm = get_llm()
    assert llm.model_name == "qwen2.5:14b-ctx8k"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm()


def test_explicit_provider_kwarg_works_with_no_env_at_all(monkeypatch):
    # The admin-panel settings path (SPEC.md §14) calls get_llm() this way -- proves the
    # explicit kwarg is sufficient on its own, independent of LLM_PROVIDER being set.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    llm = get_llm("qwen2.5:14b-ctx8k", provider="ollama")
    assert llm.model_name == "qwen2.5:14b-ctx8k"
    assert llm.request_timeout == OLLAMA_REQUEST_TIMEOUT_SECONDS
