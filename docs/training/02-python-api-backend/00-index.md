# Python API Backend Curriculum

> Part of the [training document series](../00-architecture-overview.md). This folder is a
> self-contained curriculum for building a Python web API that serves computed analysis
> results as JSON — the "decoupled" presentation-layer option described in the
> [architecture overview](../00-architecture-overview.md#8-options-for-the-presentation-layer).

## Reading order

1. [**HTTP, REST & FastAPI Fundamentals**](01-http-rest-fastapi-fundamentals.md) — HTTP
   methods and status codes, REST conventions, and the FastAPI framework's routing,
   validation, and dependency-injection model.
2. [**API Design & Best Practices**](02-api-design-best-practices.md) — data loading and
   caching, error-handling patterns (failing closed on pipeline output), resource/URL design,
   versioning, pagination, response envelopes, reporting the scope actually served, security
   fundamentals.
3. [**Testing**](03-testing.md) — `pytest`, FastAPI's `TestClient`, fixture-based test data,
   mocking, fixtures built by running the real upstream pipeline, and how to verify a test
   actually catches the regression it claims to.
4. [**Deployment**](04-deployment.md) — running the API in production: ASGI servers,
   containers, cloud platforms, reverse proxies and edge policies, refresh-driven restarts,
   CI/CD, and health checks.

## Prerequisites

Comfort with Python functions, classes, and type hints is assumed. No prior web-framework
experience is assumed.

## See also

- [Architecture Overview](../00-architecture-overview.md) for how this layer fits between the
  data-processing layer and a frontend
- [Data Science / ML](../01-data-science-ml/00-index.md) for what typically produces the data
  this API serves
- [React Front End](../04-react-frontend/00-index.md) for a typical human-facing consumer of
  an API built this way
- [MCP Server](../05-mcp-server/00-index.md) for wrapping this same API as tools an LLM agent
  can call, instead of (or alongside) a frontend
