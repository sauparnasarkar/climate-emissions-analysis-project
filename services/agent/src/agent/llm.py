"""LLM provider seam.

`get_llm()` is the single place that constructs `ChatAnthropic`. Every graph-building function
in `graph.py` takes `llm` as an injectable argument defaulting to `get_llm()` -- this keeps the
node-routing/wiring tests (Step 2) free of a real `ANTHROPIC_API_KEY` requirement, matching
`services/mcp-server`'s own test suite, which needs no external credentials. A stub/fake LLM is
injected in those tests instead. Exactly one test (`tests/test_llm_smoke.py`) makes a real call,
and skips itself when `ANTHROPIC_API_KEY` is unset.
"""

import os

from langchain_anthropic import ChatAnthropic

DEFAULT_MODEL = "claude-sonnet-5"


def get_llm(model: str | None = None) -> ChatAnthropic:
    return ChatAnthropic(model=model or os.environ.get("AGENT_LLM_MODEL", DEFAULT_MODEL))
