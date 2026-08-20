"""Per-query trace-id plumbing and logging setup.

`trace_id_var` is a per-request `contextvars.ContextVar`, not a field on `AgentState` -- state is
checkpointed per `thread_id` across turns of one conversation, while a trace-id must be minted
fresh on every single `POST /query` call (a slow *second* turn in an old thread needs its own id,
distinct from that thread's `thread_id`). Every node already reaches `logger` via
`logging.getLogger(__name__)`, so routing the value through a contextvar + logging filter gets it
onto every log line (including the handful of pre-existing `logger.warning`/`logger.exception`
calls in graph.py/server.py) without changing any node's signature -- preserving the
`functools.partial`-based `llm`/`mcp_tools` injection seam the test suite relies on.

`server.py`'s `stream_query()` sets `trace_id_var` as its own first statement (not the `/query`
handler, before handing the generator to `EventSourceResponse`) so the value is guaranteed correct
in whatever task actually drives the generator's execution, regardless of how sse_starlette
schedules that relative to the request-handling task.
"""

import contextvars
import logging
import os
import uuid

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


class TraceIdFilter(logging.Filter):
    """Stamps `record.trace_id` from the contextvar. Attached to a *logger* (not a handler) so it
    runs in `Logger.handle()` before any handler sees the record -- including pytest's `caplog`
    handler, which installs itself independent of whatever handlers `configure_logging()` adds to
    root and would otherwise never see a handler-level filter's effect."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


# The exact logger names this package's modules use (`logging.getLogger(__name__)` in graph.py
# and server.py). A `Logger.addFilter()` call only applies to records logged directly through
# that *exact* logger -- NOT to descendant loggers during propagation up to root's handlers, a
# common logging gotcha confirmed empirically here (attaching the filter to a parent "agent"
# logger that no code logs through directly does nothing; "agent.graph"/"agent.server" are
# distinct Logger objects). New modules that add their own `logger.info(...)` calls need adding
# here too.
_INSTRUMENTED_LOGGERS = ("agent.graph", "agent.server")

_configured = False


def configure_logging(level: str | None = None) -> None:
    """Idempotent -- safe to call at module import time even if the module is reloaded within one
    process. Adds one stderr handler to root (matching the existing launchd log redirect) and
    attaches `TraceIdFilter` to each logger in `_INSTRUMENTED_LOGGERS` so every node/tool log line
    picks up the current query's trace-id with no per-call-site changes. The formatter's
    `defaults={"trace_id": "-"}` covers any other (e.g. third-party) logger's records that reach
    root without ever passing through the filter."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level or os.environ.get("AGENT_LOG_LEVEL", "INFO"))
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [trace_id=%(trace_id)s] %(name)s: %(message)s",
            defaults={"trace_id": "-"},
        )
    )
    root.addHandler(handler)
    for name in _INSTRUMENTED_LOGGERS:
        logging.getLogger(name).addFilter(TraceIdFilter())
    _configured = True
