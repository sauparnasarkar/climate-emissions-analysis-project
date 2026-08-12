# Climate Emissions MCP Server

MCP server wrapping the `api/` REST API as hand-curated tools. See [`SPEC.md`](SPEC.md) for
the full design and [`CLAUDE.md`](CLAUDE.md) for agent-facing conventions.

**Status:** implementation complete for Stage 1 (Steps 1–4) — hand-curated tools, trimming,
resolution guard, and both transports are wired and verified against real data. What's left
per `SPEC.md` §7 is the open-ended part of Stage 1: iterating on tool descriptions/argument
schemas as they get exercised for real by Claude Desktop/Code and, eventually, a LangGraph
agent — not a fixed deliverable with a defined "done."

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

Requires the API running separately (`uvicorn api.main:app --port 8081` from the repo root,
using the repo's root `.venv`, not this sub-project's — that's where `api/`'s own deps live).
Point this server at it via `API_BASE_URL` (defaults to `http://127.0.0.1:8081/api`).

**Always run the module as a package (`python -m mcp_server`), never as
`python -m mcp_server.server` directly** — the latter silently misbehaves (or, as of this
version, fails outright) due to how `tools/*.py`'s relative imports interact with `-m`
loading a file as `__main__`; see the note at the bottom of `server.py` for the full
explanation, and `tests/test_entry_point.py` for the regression test that catches it.

Streamable HTTP (default, primary transport per `SPEC.md` §2):

```bash
API_BASE_URL=http://127.0.0.1:8081/api python -m mcp_server
# -> listening on http://127.0.0.1:8765/mcp (host is hardcoded to 127.0.0.1 -- see server.py)
```

stdio (local-dev fallback):

```bash
MCP_TRANSPORT=stdio API_BASE_URL=http://127.0.0.1:8081/api python -m mcp_server
```

Override the Streamable HTTP port with `MCP_SERVER_PORT` (default `8765`).

## Connecting Claude Desktop / Claude Code

**Claude Code** (stdio, simplest — no separate process to manage):

```bash
claude mcp add climate-emissions \
  --env API_BASE_URL=http://127.0.0.1:8081/api \
  -- /path/to/services/mcp-server/.venv/bin/python -m mcp_server
```

(Set `MCP_TRANSPORT=stdio` too if your `claude mcp add` version doesn't default new stdio
entries correctly — check `claude mcp add --help` for the exact flags on your installed
version, since this CLI surface has changed across releases.)

**Claude Desktop**: add an entry to `claude_desktop_config.json`'s `mcpServers` object
pointing `command` at the same venv Python and `args` at `["-m", "mcp_server"]`, with `env`
setting `API_BASE_URL` (and `MCP_TRANSPORT=stdio`, since Desktop's stdio-launcher config
shape is the most broadly supported one). Exact config keys have shifted across Desktop
versions — check Anthropic's current MCP docs for the live schema rather than trusting a
hardcoded example here.

Either way: start `uvicorn api.main:app --port 8081` first, then connect — this server has
no retry/backoff if `api/` isn't up yet when a tool call goes out.

## Local verification (SPEC.md §7)

Both transports have been exercised end-to-end against a real running `api/` and real
`data/` CSVs (not just the fixture-based test suite): all 12 tools list correctly, the
country-resolution guard both auto-resolves typos and produces real fuzzy suggestions
(`"Atlantis"` → `"did you mean: Albania?"`), and the `SPEC.md` §3.2 trimming/`scope_note`
behavior produces correct, real counts (e.g. `"Showing 10 of 215 countries..."` for
`get_historical_emissions(scope="sovereign")`, where 215 — not the raw 218-country sovereign
list — is correct: it's the count of countries with actual CO₂ data once the wrapped API's
own `dropna` runs, which is what an agent doing "top 10 of X" reasoning actually cares about).
