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


def normalize_typography(value):
    """Proper typography in the text the API hands back: "CO2" -> "CO₂" (also in "GtCO2", "MtCO2e",
    "non-CO2") and "degC" -> "°C", in every string VALUE, recursively.

    Applied once, in `fetch_correlation`, because the API's own labels, units, notes, caveats and
    methodology text carry plain "CO2" (they are written in `pipeline/` and `api/`, not here) and every
    one of them can reach a user through the agent. Dict keys are not text and keep their spelling, and a
    string starting with "http" is left alone, so neither an identifier nor a URL is rewritten.
    Identifiers are lower-case (`owid_co2`, `co2_mt`), so the upper-case "CO2" this replaces never
    appears in one."""
    if isinstance(value, str):
        if value.startswith("http"):
            return value
        return value.replace("CO2", "CO₂").replace("degC", "°C")
    if isinstance(value, dict):
        return {k: normalize_typography(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_typography(v) for v in value]
    return value


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
    return normalize_typography(body)


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


# --- country-share summaries (Release 24.3) ----------------------------------------------------------------

# ENHANCEMENTS.md D6: a country's cumulative share counts as "steady" when it moved by less than this over the window shown.
SHARE_TREND_TOLERANCE_PP = 0.5
_MT_PER_GT = 1000


def share_trend(change_pp: float | None) -> str | None:
    """`rising`, `falling` or `steady`, computed here so the model reports it instead of inferring it. None when there is nothing to compare."""
    if change_pp is None:
        return None
    if change_pp > SHARE_TREND_TOLERANCE_PP:
        return "rising"
    if change_pp < -SHARE_TREND_TOLERANCE_PP:
        return "falling"
    return "steady"


def _gt(mt: float | None) -> float | None:
    return None if mt is None else round(mt / _MT_PER_GT, 1)


def gt_text(mt: float | None) -> str | None:
    """A cumulative amount ready to quote, with its unit ("434.9 GtCO₂"): the model reads this instead of attaching a unit to a bare number. A live answer wrote
    "434.9 Mt" for the United States because the summary said `unit: Mt CO2` beside Gt-valued fields (a 1,000-fold error)."""
    return None if mt is None else f"{mt / _MT_PER_GT:,.1f} GtCO₂"


# What each field's suffix means. The summary used to carry the BODY's `unit` ("Mt CO2") beside `_gt` fields, which is what mislabelled them.
SHARE_SUMMARY_UNITS = {
    "_mt": "MtCO₂ (million tonnes)",
    "_gt": "GtCO₂ (billion tonnes; 1 Gt = 1,000 Mt)",
    "_pct": "percent",
    "_pp": "percentage points",
    "_text": "already formatted with its unit: quote it as written",
}


def share_series_summary(body: dict, roster: dict, start_year: int | None) -> dict:
    """The `summary` of a country-share SERIES: per country the first and last cumulative share, its change in percentage points over the window shown and the
    `share_trend` of that change, the latest cumulative total (Mt and Gt), the latest annual share, and the country's rank among `rank_of` countries.

    `roster` is the all-countries ranking the tool already fetched to resolve names; it is the latest year's, so a rank is given only for a series that ends in
    that year (never a latest-year rank beside an earlier window). For OWID, whose shares are of the World total, `rest_of_world` is what the countries shown
    leave of it in the last year: World minus the countries shown, so it includes international aviation and shipping."""
    ranks = {r["country"]: r["rank"] for r in roster.get("rows", [])}
    rank_of, roster_year = len(ranks), roster.get("year")
    countries = []
    for sr in body["series"]:
        pts = sr["points"]
        first, last = (pts[0], pts[-1]) if pts else (None, None)
        change = round(last["share_pct"] - first["share_pct"], 2) if first and last and last["year"] != first["year"] else None
        ranked = last is not None and last["year"] == roster_year and sr["country"] in ranks
        countries.append(
            {
                "country": sr["country"],
                "name": sr["name"],
                "in_expanded_scope": sr.get("in_expanded_scope"),
                "first_year": first["year"] if first else None,
                "first_share_pct": round(first["share_pct"], 2) if first else None,
                "last_year": last["year"] if last else None,
                "last_share_pct": round(last["share_pct"], 2) if last else None,
                "share_change_pp": change,
                "share_trend": share_trend(change),
                "last_cumulative_mt": round(last["cumulative_mt"], 1) if last else None,
                "last_cumulative_gt": _gt(last["cumulative_mt"]) if last else None,
                "last_cumulative_text": gt_text(last["cumulative_mt"]) if last else None,
                "last_annual_share_pct": round(last["annual_share_pct"], 2) if last and last.get("annual_share_pct") is not None else None,
                "last_annual_mt": round(last["annual_mt"], 1) if last and last.get("annual_mt") is not None else None,
                "rank": ranks[sr["country"]] if ranked else None,
                "rank_of": rank_of if ranked else None,
            }
        )
    firsts = [c["first_year"] for c in countries if c["first_year"] is not None]
    lasts = [c["last_year"] for c in countries if c["last_year"] is not None]
    summary: dict = {
        "mode": "series",
        "countries": countries,
        # The window each `share_trend` is measured over: a trend since 1850 says little about recent movement, so say which window it is.
        "trend_window": [min(firsts), max(lasts)] if firsts else None,
        "rank_year": roster_year,
        "trend_tolerance_pp": SHARE_TREND_TOLERANCE_PP,
        "counted_from": body.get("cumulative_from"),
    }
    cumulative_from = body.get("cumulative_from")
    if start_year is not None and cumulative_from is not None and start_year > cumulative_from:
        summary["window_note"] = (
            f"start_year only chooses the first year shown: every total still counts from each country's first record (the earliest is {cumulative_from}) "
            "and is never restarted at start_year, so a cumulative since a later year is not available."
        )
    # Rest of world, for OWID only (a remainder exists only where the denominator is the World total)
    rem = {r["year"]: r for r in body.get("remainder_series") or []}
    last_year = max(lasts) if lasts else None
    if last_year in rem and countries and all(c["last_year"] == last_year for c in countries):
        w = rem[last_year]
        shown_mt = sum(sr["points"][-1]["cumulative_mt"] for sr in body["series"])
        shown_pct = sum(sr["points"][-1]["share_pct"] for sr in body["series"])
        summary["world_cumulative_gt"] = _gt(w["world_cumulative_mt"])
        summary["world_cumulative_text"] = gt_text(w["world_cumulative_mt"])
        summary["rest_of_world"] = {
            "year": last_year,
            "cumulative_mt": round(max(0.0, w["world_cumulative_mt"] - shown_mt), 1),
            "cumulative_gt": _gt(max(0.0, w["world_cumulative_mt"] - shown_mt)),
            "cumulative_text": gt_text(max(0.0, w["world_cumulative_mt"] - shown_mt)),
            "share_pct": round(max(0.0, 100 - shown_pct), 2),
            "includes": "every country not shown plus international aviation and shipping",
        }
    return summary


def share_ranking_summary(body: dict) -> dict:
    """The `summary` of a country-share RANKING: the top rows (Gt included), the shown rows' share, and for OWID the remainder of the World total. With a limited ranking
    the rows plus the remainder do not make 100: `not_shown_share_pct` is what the countries left out by the limit hold."""
    rows = body["rows"]
    shown_pct = round(sum(r["share_pct"] for r in rows), 2) if rows else None
    summary: dict = {
        "mode": "ranking",
        "year": body["year"],
        "n_rows": len(rows),
        "top": [
            {"rank": r["rank"], "name": r["name"], "share_pct": round(r["share_pct"], 2), "cumulative_gt": _gt(r["cumulative_mt"]), "cumulative_text": gt_text(r["cumulative_mt"]),
             "in_expanded_scope": r.get("in_expanded_scope")}
            for r in rows[:5]
        ],
        # An empty ranking is "no data for that year", not zero emissions: keep it unavailable.
        "shown_share_pct_total": shown_pct,
    }
    rem = body.get("remainder")
    if rem and rows:
        summary["world_cumulative_gt"] = _gt(body.get("total_cumulative_mt"))
        summary["world_cumulative_text"] = gt_text(body.get("total_cumulative_mt"))
        summary["remainder_share_pct"] = round(rem["share_pct"], 2)
        summary["not_shown_share_pct"] = round(max(0.0, 100 - shown_pct - rem["share_pct"]), 2)
    if not rows:
        summary["unavailable"] = "No ranking rows for the requested year; see `notes` for the available coverage."
    return summary
