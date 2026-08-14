"""FastAPI app for the conversational agent.

Run via `uvicorn agent.server:app` (matches `api/main.py`'s own run convention -- no custom
`__main__.py` entry point needed here, unlike `services/mcp-server`, since there's no
stdio/streamable-http transport duality or tools-module import-order footgun to guard against).

No graph wiring yet -- Step 2 (`graph.py`) and Step 3 (the SSE query endpoint) build on this.
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Climate Emissions Conversational Agent")


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")
