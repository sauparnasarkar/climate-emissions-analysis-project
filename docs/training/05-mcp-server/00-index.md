# MCP Server Curriculum

> Part of the [training document series](../00-architecture-overview.md). This folder is a
> self-contained curriculum for building an MCP server — a standard-protocol layer that
> exposes an existing data source or API as tools an LLM can call, sitting between the
> [API backend](../02-python-api-backend/00-index.md) (or any other data source) and the
> [conversational agent](../06-conversational-agent/00-index.md) that will use it.

## Reading order

1. [**Core Concepts**](01-core-concepts.md) — what MCP is and the problem it solves, the
   host/client/server roles, the three primitives (tools, resources, prompts), transports,
   and a minimal working server.
2. [**Tool Design**](02-tool-design.md) — designing tool schemas for an LLM audience: direct
   wraps vs. composed tools, argument-resolution guards, shaping responses for a model rather
   than a human, error handling, statelessness, interpretive framing, envelope pass-through
   with computed summaries, and rejecting what a tool cannot honor.
3. [**Testing**](03-testing.md) — unit-testing tool functions directly, integration-testing
   through a real client, fixture data patterns, a class of entry-point bug only a real
   subprocess launch can catch, and registry-wide tests for rejection rules.
4. [**Deployment**](04-deployment.md) — transports in production, per-boundary auth
   decisions (a worked four-boundary example with edge service tokens), connecting local,
   desktop-app and programmatic clients, and independent versioning.

## Prerequisites

Comfort with Python functions, classes, and type hints is assumed. Having read the
[Python API Backend curriculum](../02-python-api-backend/00-index.md) first is helpful but not
required — an MCP server commonly wraps a REST API like the one built there, and several
documents in this folder point back to the equivalent backend concept for comparison.

## See also

- [Architecture Overview](../00-architecture-overview.md) for how this layer fits between a
  data-serving API and an LLM agent
- [Python API Backend](../02-python-api-backend/00-index.md) for a typical thing this kind of
  server wraps
- [Conversational Agents](../06-conversational-agent/00-index.md) for the typical consumer of
  an MCP server's tools
