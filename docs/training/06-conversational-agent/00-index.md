# Conversational Agent Curriculum

> Part of the [training document series](../00-architecture-overview.md). This folder is a
> self-contained curriculum for building a graph-based conversational agent — an LLM given
> tools and the autonomy to decide when to use them, typically calling an
> [MCP server](../05-mcp-server/00-index.md) for its tools and surfaced through a
> [frontend](../04-react-frontend/00-index.md) as a chat-like or report-like interface.

## Reading order

1. [**Core Concepts**](01-core-concepts.md) — what "agent" means here, why a graph rather
   than a plain loop, nodes/edges/conditional routing, state schema and reducers, the
   tool-calling loop, and checkpointer-backed memory.
2. [**Tool Calling, Guardrails and Generative UI**](02-tool-calling-and-guardrails.md) — using
   an MCP server as a tool source, classifying requests before acting on them, bounding the
   tool-calling loop, two different kinds of caching, streaming progress, mapping results
   to real UI components instead of freeform generated markup, and structural guardrails
   (required disclosures, capped model views, computed numbers, fixed follow-up lookups).
3. [**Testing**](03-testing.md) — an injectable LLM seam for hermetic tests, stub-based
   graph-routing tests, testing reducers against a real graph invocation, real-subprocess
   integration testing of the tool connection, exactly one gated live-LLM smoke test,
   table-driven tests for the deterministic parts, and answer linting with a golden-prompt
   evaluation.
4. [**Deployment**](04-deployment.md) — trust boundaries between an agent and its tool
   source, session-id validation as a public input boundary, secrets, streaming responses,
   rate limiting, a safe runtime model-switch (admin) capability, and observability.

## Prerequisites

Comfort with Python is assumed. Having read the [MCP Server
curriculum](../05-mcp-server/00-index.md) first is helpful but not required — this curriculum
treats an MCP server as the typical source of an agent's tools, and several documents here
point back to the equivalent MCP-side concept.

## See also

- [Architecture Overview](../00-architecture-overview.md) for how this layer fits alongside a
  more conventional dashboard presentation layer
- [MCP Server](../05-mcp-server/00-index.md) for the typical tool source this kind of agent
  calls
- [React Front End](../04-react-frontend/00-index.md) for a typical UI shell a conversational
  agent is surfaced through
