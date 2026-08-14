"""The one real-network test in this suite -- confirms `ChatAnthropic(model="claude-sonnet-5")`
actually resolves against whatever `langchain-anthropic` version pip installed, rather than
trusting the class/model name to work from memory. Skips automatically with no API key set, so
the rest of the suite (and CI without a key configured) stays hermetic.
"""

import os

import pytest

from agent.llm import get_llm

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping the one real-network LLM smoke test",
)


def test_llm_resolves_and_responds():
    llm = get_llm()
    response = llm.invoke("Reply with exactly one word: OK")
    assert response.content
