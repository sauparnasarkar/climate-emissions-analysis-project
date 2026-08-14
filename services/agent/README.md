# Climate Emissions Conversational Agent

LangGraph agent that answers climate-emissions questions by calling `services/mcp-server`'s
tools and rendering results as real design-system components. See [`SPEC.md`](SPEC.md) for the
full design and [`CLAUDE.md`](CLAUDE.md) for agent-facing conventions.

**Status:** Steps 1–5 complete — state schema, MCP client wiring, the full LangGraph node catalog
(guardrails, agent/tools loop, call-count guard, tool-call cache, UI intent selection), the real
`POST /query` SSE endpoint, the `climate-dashboard-react/` frontend (`/ask` nav item), and a
security review (`ENHANCEMENTS.md`'s Step 5 entry). Deployed and running on the Mac Mini
(`com.ghgemissions.agent` launchd agent, port 8766); a genuine end-to-end query — real SSE
progress event, real `services/mcp-server` tool call, real LLM response — verified live
2026-08-14. Cloudflare Tunnel route for the public `/ghg-emissions-analysis/agent` endpoint is
the one remaining step — see `ENHANCEMENTS.md`'s deploy entry.

## Dev setup

From this directory (`services/agent/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest services/agent/tests
```

`test_mcp_client.py` launches a real `services/mcp-server` subprocess (using that sub-project's
own `.venv` — set it up first, see `services/mcp-server/README.md`) and skips itself if that
venv isn't present. `test_llm_smoke.py` makes one real Anthropic API call and skips itself if
`ANTHROPIC_API_KEY` isn't set. Every other test is hermetic.

## Running the server locally

Requires `services/mcp-server` running separately on `127.0.0.1:8765` (its own default) — this
agent connects to it unauthenticated over localhost, matching the co-located deployment (see
`SPEC.md` "Corrections applied" #4). Override with `MCP_SERVER_URL` if needed.

```bash
ANTHROPIC_API_KEY=... uvicorn agent.server:app --port 8766
```

`POST /query` (`{"query": "...", "thread_id": null}`) streams progress events and a final
`result` event over SSE. Omit `thread_id` on the first query of a new conversation — the server
mints and returns one in the `result` event; pass it back on subsequent queries in the same
conversation to keep `tool_cache`/`messages` history (SPEC.md §7/§9).
