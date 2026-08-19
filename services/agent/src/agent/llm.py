"""LLM provider seam.

`get_llm()` is the single place that constructs the chat model. Every graph-building function
in `graph.py` takes `llm` as an injectable argument defaulting to `get_llm()` -- this keeps the
node-routing/wiring tests (Step 2) free of a real `ANTHROPIC_API_KEY` requirement, matching
`services/mcp-server`'s own test suite, which needs no external credentials. A stub/fake LLM is
injected in those tests instead. Exactly one test (`tests/test_llm_smoke.py`) makes a real call,
and skips itself when `ANTHROPIC_API_KEY` is unset.

`LLM_PROVIDER=ollama` is a **local experiment seam only**, not a supported deployment mode --
CLAUDE.md's "Model: Claude Sonnet 5 ... for every LLM node" decision still holds for the deployed
Mac Mini instance. `guardrail_router` is this agent's safety boundary for a public unauthenticated
endpoint; a small local model misclassifying off-topic input into `data_query` there is a real
problem. Leave `LLM_PROVIDER` unset in any deployed environment. `langchain_openai` is a regular
(non-optional) dependency in `pyproject.toml`, but still imported lazily inside the `ollama`
branch as defense-in-depth: a venv where `pyproject.toml` changed but `pip install` hasn't been
rerun yet shouldn't break the default anthropic path, or any anthropic-path test, just by this
module being imported.

`DEFAULT_OLLAMA_MODEL` is `llama3.1:8b`, not `qwen2.5-coder:7b` -- verified live against the
Mac Mini's real Ollama endpoint (2026-08-19): `qwen2.5-coder:7b`'s `bind_tools()` output doesn't
land in `AIMessage.tool_calls` at all, it comes back as plain text content, and on an off-topic
query it fabricated a call to a tool that was never in the bound tool list. `llama3.1:8b` produced
correct structured `tool_calls` for a real query, correctly abstained (no hallucinated tool) on an
off-topic one, and structured-output classification worked on both. `qwen2.5-coder:7b` stays
usable via `LOCAL_LLM_MODEL` override for whatever it's still good at, but it is not what
`agent_node`'s `bind_tools()` path needs.
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"


def get_llm(model: str | None = None) -> BaseChatModel:
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "ollama":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=os.environ.get("LOCAL_LLM_URL", DEFAULT_OLLAMA_URL),
            api_key=os.environ.get("LOCAL_LLM_API_KEY", "ollama"),
            model=model or os.environ.get("LOCAL_LLM_MODEL", DEFAULT_OLLAMA_MODEL),
            temperature=0.0,
            max_retries=1,
        )

    if provider != "anthropic":
        raise ValueError(f"Unknown LLM_PROVIDER {provider!r} -- expected 'anthropic' or 'ollama'")

    return ChatAnthropic(model=model or os.environ.get("AGENT_LLM_MODEL", DEFAULT_MODEL))
