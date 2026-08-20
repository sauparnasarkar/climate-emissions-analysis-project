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
`agent_node`'s `bind_tools()` path needs. The deployed instance moved on from `llama3.1:8b` to a
custom `qwen2.5:14b-ctx8k` Ollama model tag (12288-context variant also evaluated) after a live
compound query genuinely stalled under `llama3.1:8b`'s default 4096-token context -- see
`ollama create`'s `num_ctx` parameter, not something this module controls.

`timeout=150` on the Ollama branch bounds a single LLM call, not a full multi-call turn --
`agent_node`/`guardrail_router`/`ui_selection_node`/`compose_response_node` each make their own
separate call, so one query can chain several. Sized off a real 30-case timed battery against
`qwen2.5:14b-ctx12k` (2026-08-19): the slowest *full* multi-call query took 247.9s total, meaning
no single call within it could have taken longer than that -- 150s leaves comfortable headroom
above realistic single-call latency while still turning a genuine stall (like the one that
motivated this: a request sat at ~0.2% CPU for 4+ minutes with zero progress before `llama-server`
was manually killed) into a bounded, known failure instead of an indefinite hang. Not applied to
the Anthropic path -- no comparable stall has been observed there, and this is deliberately
scoped to the problem that was actually seen.
"""

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_REQUEST_TIMEOUT_SECONDS = 150


def get_llm(model: str | None = None, *, provider: str | None = None) -> BaseChatModel:
    """`provider` is an additive override for the admin-panel settings path (SPEC.md §14) --
    called with no arguments this is byte-for-byte the same as before that feature existed.
    Deliberately still env-var-only otherwise: the settings-store lookup lives in the admin
    code path, never here, so this stays free of any dependency on machine-local state and the
    existing test/hermeticity contract (module docstring above) is unaffected.
    """
    provider = (provider or os.environ.get("LLM_PROVIDER", "anthropic")).lower()

    if provider == "ollama":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=os.environ.get("LOCAL_LLM_URL", DEFAULT_OLLAMA_URL),
            api_key=os.environ.get("LOCAL_LLM_API_KEY", "ollama"),
            model=model or os.environ.get("LOCAL_LLM_MODEL", DEFAULT_OLLAMA_MODEL),
            temperature=0.0,
            max_retries=1,
            timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS,
        )

    if provider != "anthropic":
        raise ValueError(f"Unknown LLM_PROVIDER {provider!r} -- expected 'anthropic' or 'ollama'")

    return ChatAnthropic(model=model or os.environ.get("AGENT_LLM_MODEL", DEFAULT_MODEL))
