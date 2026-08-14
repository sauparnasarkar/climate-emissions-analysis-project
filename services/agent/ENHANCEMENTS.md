# `services/agent` — Enhancements / Release History

Mirrors `services/mcp-server/ENHANCEMENTS.md`'s convention: one entry per shipped release, most
recent first, narrating what changed and why — not a duplicate of `SPEC.md`, which stays a
current-state design doc.

---

## Release 1 — Backend scaffold + MCP client (Step 1 of 5)

Brought `~/Downloads/agent-spec.md` into the repo as [`SPEC.md`](SPEC.md), with two corrections
found during verification (choropleth's real prop name is `locations`, not `iso_code`; `Tile`
has no built-in kicker/prompt/arrow composition) and one architecture decision (co-located B3
localhost connection to `services/mcp-server`, not the Cloudflare-Access-gated B4 path
`services/mcp-server/SPEC.md` §8.4 originally sketched for "the LangGraph agent" — see `SPEC.md`
"Corrections applied" #4).

Shipped:
- `src/agent/state.py` — `ToolCallRecord`, `WidgetSpec`, `AgentState` (`SPEC.md` §7), as Pydantic
  models. Verified the `Annotated[list, add_messages]` reducer on `messages` actually appends
  (not overwrites) via a real minimal `StateGraph` invocation, not just model construction —
  de-risked before Step 2 builds the full nine-node graph on this shape.
- `src/agent/mcp_client.py` — wraps `langchain_mcp_adapters.client.MultiServerMCPClient`,
  pointed at `MCP_SERVER_URL` (default `http://127.0.0.1:8765/mcp`). Confirmed
  `MultiServerMCPClient` cannot be used as an async context manager (as of
  `langchain-mcp-adapters` 0.1.0) — construct then `await client.get_tools()`.
- `src/agent/llm.py` — `get_llm()`, the single seam every LLM-backed graph node will take as an
  injectable argument in Step 2, so the test suite never needs a real `ANTHROPIC_API_KEY`.
- `src/agent/server.py` — bare FastAPI app + `/health`. No graph or query endpoint yet.
- Tests: state-model validation and reducer proof (`test_state.py`), a real connectivity test
  launching a `services/mcp-server` subprocess and confirming `MultiServerMCPClient.get_tools()`
  lists all 13 real tools (`test_mcp_client.py`), a `/health` check (`test_server.py`), and one
  real-network LLM smoke test that self-skips without `ANTHROPIC_API_KEY`
  (`test_llm_smoke.py`).

Not yet built: the LangGraph node catalog, SSE streaming, the frontend nav item, and the Mac
Mini deploy — Steps 2–5, `SPEC.md`'s own scope for those steps unchanged.
