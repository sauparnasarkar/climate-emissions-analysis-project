"""Abuse limits for the public `/query` endpoint -- cost and capacity, not authentication.

Every query is a paid LLM call on a public, unauthenticated endpoint, and the only other brake is
the Cloudflare edge rule (a per-IP burst limit, nothing per-hour or per-day, nothing on concurrency).
These limits are the app-layer backstop that holds if the edge rule is ever loosened or bypassed:

* a cap on queries running at once (`AGENT_MAX_CONCURRENT_QUERIES`),
* a per-client sliding-hour allowance (`AGENT_QUERIES_PER_IP_PER_HOUR`),
* a global per-UTC-day budget (`AGENT_DAILY_QUERY_BUDGET`).

Each is checked before any LLM work and refused with a curated message. A value of 0 disables that
one limit. The client key is `CF-Connecting-IP` when present, else the socket peer: the service binds
127.0.0.1 and is reached only through the Cloudflare Tunnel, which sets that header.
"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import UTC, datetime

from fastapi import HTTPException, Request

DEFAULT_MAX_CONCURRENT = 6
DEFAULT_PER_IP_PER_HOUR = 60
DEFAULT_DAILY_BUDGET = 1500
HOUR_SECONDS = 3600
MAX_TRACKED_CLIENTS = 10_000  # a bound on the per-client table, not a policy: stale clients are pruned first


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def client_key(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded and forwarded.strip():
        return forwarded.strip()
    return request.client.host if request.client else "unknown"


class QuerySlot:
    """A held concurrency slot; `release` is idempotent so every cleanup path can call it."""

    def __init__(self, limiter: "QueryLimiter") -> None:
        self._limiter: QueryLimiter | None = limiter

    def release(self) -> None:
        if self._limiter is not None:
            self._limiter._in_flight -= 1
            self._limiter = None


class QueryLimiter:
    def __init__(self) -> None:
        self._in_flight = 0
        self._per_client: dict[str, deque[float]] = {}
        self._day = ""
        self._day_count = 0

    @staticmethod
    def max_concurrent() -> int:
        return _env_int("AGENT_MAX_CONCURRENT_QUERIES", DEFAULT_MAX_CONCURRENT)

    @staticmethod
    def per_client_per_hour() -> int:
        return _env_int("AGENT_QUERIES_PER_IP_PER_HOUR", DEFAULT_PER_IP_PER_HOUR)

    @staticmethod
    def daily_budget() -> int:
        return _env_int("AGENT_DAILY_QUERY_BUDGET", DEFAULT_DAILY_BUDGET)

    def acquire(self, client: str, *, now: float | None = None, today: str | None = None) -> QuerySlot:
        """Admits one query or raises a curated `HTTPException`. Counts the query against the
        client's hour and the day only once it is admitted, so a refusal costs nothing."""
        now = time.monotonic() if now is None else now
        today = today or datetime.now(UTC).strftime("%Y-%m-%d")

        if today != self._day:
            self._day, self._day_count = today, 0

        budget = self.daily_budget()
        if budget and self._day_count >= budget:
            raise HTTPException(status_code=503, detail="Today's question allowance has been used up -- please try again tomorrow.")

        cap = self.max_concurrent()
        if cap and self._in_flight >= cap:
            raise HTTPException(status_code=503, detail="Many questions are being answered right now -- please try again in a moment.", headers={"Retry-After": "10"})

        allowance = self.per_client_per_hour()
        window = self._per_client.setdefault(client, deque())
        while window and now - window[0] >= HOUR_SECONDS:
            window.popleft()
        if allowance and len(window) >= allowance:
            retry_after = max(1, int(HOUR_SECONDS - (now - window[0])))
            raise HTTPException(status_code=429, detail="You have asked a lot of questions in the last hour -- please try again later.", headers={"Retry-After": str(retry_after)})

        window.append(now)
        self._day_count += 1
        self._in_flight += 1
        self._prune(now)
        return QuerySlot(self)

    def _prune(self, now: float) -> None:
        if len(self._per_client) <= MAX_TRACKED_CLIENTS:
            return
        for key in [k for k, w in self._per_client.items() if not w or now - w[-1] >= HOUR_SECONDS]:
            del self._per_client[key]
