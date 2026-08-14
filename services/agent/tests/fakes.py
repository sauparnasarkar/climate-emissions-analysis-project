"""Test doubles for graph-routing tests.

`ScriptedChatModel` stands in for `llm` (the injectable seam every LLM-backed node takes) so
routing/caching/guard tests never need a real `ANTHROPIC_API_KEY` -- see `llm.py`'s docstring
for why that matters. Hand-rolled rather than LangChain's `GenericFakeChatModel`: that class
doesn't cleanly support `bind_tools`/`with_structured_output` chaining, which every LLM node
here relies on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel


class ScriptedChatModel:
    """Drains a fixed queue of pre-programmed responses, one per `ainvoke` call, in the exact
    order the graph is expected to call them -- regardless of whether the call came through
    `bind_tools()` or `with_structured_output()`, both share the same underlying queue."""

    def __init__(self, responses: Sequence[Any]):
        self._responses = list(responses)
        self._schema: type[BaseModel] | None = None

    def bind_tools(self, tools):  # noqa: ARG002 -- interface parity with ChatAnthropic
        return self

    def with_structured_output(self, schema: type[BaseModel]):
        clone = ScriptedChatModel.__new__(ScriptedChatModel)
        clone._responses = self._responses  # shared queue -- same script, whichever path drains it
        clone._schema = schema
        return clone

    async def ainvoke(self, messages):
        # Captured (not just consumed) so a test can assert on what a node actually sent --
        # e.g. that agent_node's system message carries a cache_control breakpoint.
        self.last_messages = messages
        if not self._responses:
            raise AssertionError("ScriptedChatModel ran out of scripted responses")
        value = self._responses.pop(0)
        if self._schema is not None and not isinstance(value, self._schema):
            return self._schema(**value)
        return value

    @property
    def exhausted(self) -> bool:
        return not self._responses
