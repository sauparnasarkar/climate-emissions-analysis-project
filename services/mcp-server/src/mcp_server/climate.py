"""Shared plumbing for the Area 2 climate-context tools (SPEC.md §5.1).

Two jobs, both cross-cutting rather than per-tool:
- `fetch_correlation` turns the API's HTTP errors into a `ClimateApiError` that carries the
  API's own `detail` text. The correlation endpoints reject on purpose (a 422 naming the valid
  source/baseline combinations, a 503 naming the stale or missing pipeline output) and that text
  is what lets the model self-correct -- a bare `HTTPStatusError` would reach it as an opaque
  failure.
- `summarize_points` builds the deterministic `summary` object (§5.1 convention 2), so the
  model quotes a computed figure instead of deriving one from a raw series.

The API envelope (`note`, `caveats`, `attribution`, `source_vintage`) is never touched here: every
tool returns the API body with `summary` added alongside it (§5.1 convention 1).
"""

from __future__ import annotations

import json

import httpx
from rapidfuzz import fuzz, process

from .client import get_client
from .resolution import AUTO_RESOLVE_THRESHOLD, CountryResolutionError


class ClimateApiError(Exception):
    """The correlation API refused or could not serve a request; the message is the API's own."""


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return response.text[:300]
    if isinstance(detail, str):
        return detail
    # FastAPI's validation errors (e.g. an unknown enum value) are a list of dicts.
    return json.dumps(detail)[:500]


async def fetch_correlation(resource: str, params: dict | None = None) -> dict:
    """GET /correlation/{resource}; 4xx/503 become a ClimateApiError carrying the API's detail."""
    client = get_client()
    try:
        body = await client.get(f"/correlation/{resource}", params=params)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 503:
            raise ClimateApiError(f"Climate data is currently unavailable: {_detail(exc.response)}") from exc
        if 400 <= status < 500:
            raise ClimateApiError(f"The climate API rejected this request ({status}): {_detail(exc.response)}") from exc
        raise
    assert isinstance(body, dict)
    return body


def _round(value: float, places: int = 3) -> float:
    return round(float(value), places)


def summarize_points(points: list[dict], *, include_pct: bool) -> dict:
    """First/last valid value, absolute (and optionally percent) change, null-year count.

    `include_pct` is False for anomaly series: a percent change of a quantity that is defined
    relative to a reference period (and can be near zero or negative) is meaningless.
    """
    valid = [p for p in points if p.get("value") is not None]
    summary: dict = {"n_years": len(points), "n_null_years": len(points) - len(valid)}
    if not valid:
        return summary
    first, last = valid[0], valid[-1]
    summary.update(
        first_year=first["year"],
        first_value=_round(first["value"]),
        last_year=last["year"],
        last_value=_round(last["value"]),
        change=_round(last["value"] - first["value"]),
    )
    if include_pct and first["value"]:
        summary["change_pct"] = _round((last["value"] - first["value"]) / first["value"] * 100, 1)
    if last.get("uncertainty") is not None:
        summary["last_uncertainty"] = _round(last["uncertainty"])
    return summary


def resolve_share_countries(names: list[str], universe: list[dict]) -> list[str]:
    """Resolve country names to the ISO3 codes `/correlation/country-share` takes (§5.1).

    Unlike the emissions tools, this endpoint's identifier set is the pipeline's own ISO3
    crosswalk, not `/countries`' OWID names, so the §3.1 guard is applied against that set
    (`universe`: the endpoint's own `{country, name}` rows): an ISO3 code or exact name matches
    directly, a confident fuzzy name match auto-resolves, anything else is an explicit error with
    a suggestion -- never a silent drop.
    """
    by_code = {u["country"].upper(): u["country"] for u in universe}
    by_name = {u["name"]: u["country"] for u in universe}
    resolved: list[str] = []
    for raw in names:
        if raw.strip().upper() in by_code:
            resolved.append(by_code[raw.strip().upper()])
        elif raw in by_name:
            resolved.append(by_name[raw])
        else:
            match = process.extractOne(raw, list(by_name), scorer=fuzz.WRatio)
            if match is None:
                raise CountryResolutionError(f"No match for '{raw}' in the country-share country list.")
            candidate, score, _ = match
            if score < AUTO_RESOLVE_THRESHOLD:
                raise CountryResolutionError(f"No match for '{raw}' — did you mean: {candidate}?")
            resolved.append(by_name[candidate])
    return list(dict.fromkeys(resolved))
