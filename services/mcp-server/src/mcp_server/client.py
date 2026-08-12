"""Thin async HTTP client for the wrapped REST API (api/).

Base URL comes from the API_BASE_URL env var, never a hardcoded constant -- production may
sit behind api/main.py's StripDeployPrefixMiddleware, so the prefix (and whether one exists
at all) has to be a deploy-time choice, not a build-time one. The URL must include the /api
prefix that api/main.py mounts every router under.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8081/api"


def _default_base_url() -> str:
    return os.environ.get("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class ApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url or _default_base_url(),
            timeout=timeout,
            transport=transport,
        )

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        # httpx repeats a query key per list item for list-valued params, matching how
        # FastAPI's Query(default=None) list params expect to be sent -- no special-casing
        # needed here for e.g. `countries`. None values are dropped rather than sent as the
        # literal string "None".
        filtered = {k: v for k, v in (params or {}).items() if v is not None}
        response = await self._client.get(path, params=filtered)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            # Every endpoint this server wraps (SPEC.md §5) returns a JSON object -- a
            # non-JSON response (e.g. /explorer/download's CSV stream, deliberately out of
            # scope per SPEC.md's tool catalog) means a tool was pointed at the wrong path.
            raise ValueError(f"Expected JSON from {path}, got non-JSON response") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


_client: ApiClient | None = None


def get_client() -> ApiClient:
    global _client
    if _client is None:
        _client = ApiClient()
    return _client


def set_client(client: ApiClient | None) -> None:
    """Injection hook for tests (and, later, server startup) to swap in a specific ApiClient
    instance -- e.g. one wired to an in-process ASGI transport instead of a real connection."""
    global _client
    _client = client
