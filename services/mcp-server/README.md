# Climate Emissions MCP Server

MCP server wrapping the `api/` REST API as hand-curated tools. See [`SPEC.md`](SPEC.md) for
the full design and [`CLAUDE.md`](CLAUDE.md) for agent-facing conventions.

**Status:** implementation in progress (Stage 1 of a separate conversational-agent project —
not internship scope, see the root `CLAUDE.md`). Transport wiring and Claude Desktop/Code
connection instructions land in a later step; for now this covers local dev setup and tests.

## Dev setup

From this directory (`services/mcp-server/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

From the **repo root** (tests import `api/` directly, mirroring `api/tests`' own convention
of running against fixture CSVs rather than real data):

```bash
pytest services/mcp-server/tests
```

## Running the server locally

Requires the API running separately (`uvicorn api.main:app --port 8081` from the repo root).
Point this server at it via `API_BASE_URL` (defaults to `http://127.0.0.1:8081/api`):

```bash
API_BASE_URL=http://127.0.0.1:8081/api python -m mcp_server.server
```
