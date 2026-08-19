"""The one real-network test in this suite -- confirms `ChatAnthropic(model="claude-sonnet-5")`
actually resolves against whatever `langchain-anthropic` version pip installed, rather than
trusting the class/model name to work from memory. Skips automatically with no API key set, so
the rest of the suite (and CI without a key configured) stays hermetic.

Also skips if `LLM_PROVIDER=ollama` is exported -- `get_llm()` takes no provider argument here,
so without this second condition an `ANTHROPIC_API_KEY`-present + `LLM_PROVIDER=ollama` env
(plausible during the exact local experimentation that env var exists for, see `llm.py`) would
silently make an Ollama call while this test's docstring claims to verify Anthropic resolution.
Never add a second, ungated real-network LLM test for the Ollama path instead -- see `llm.py`'s
module docstring and `services/agent/CLAUDE.md`.
"""

import os

import pytest

from agent.llm import get_llm

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_PROVIDER", "anthropic").lower() != "anthropic",
    reason="ANTHROPIC_API_KEY not set, or LLM_PROVIDER isn't anthropic -- skipping the one real-network LLM smoke test",
)


def test_llm_resolves_and_responds():
    llm = get_llm()
    response = llm.invoke("Reply with exactly one word: OK")
    assert response.content
