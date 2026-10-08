"""SPEC.md §5.1 Area 2 tools: the indicator tools (get_co2_concentration,
get_temperature_anomaly, get_correlation_metadata) and the relationship tools
(get_emissions_temperature_relationship, get_ghg_composition, get_country_cumulative_share,
get_scenario_temperature).

Each returns the API body unchanged (full series + envelope) with a deterministic `summary`
added. Capping what the *model* sees is the agent's job (agent SPEC.md §15.4), not this server's.
"""

from __future__ import annotations

from ..climate import fetch_correlation, resolve_share_countries, summarize_points
from ..server import mcp

# Tool-facing reference label -> the API's `baseline` value.
TEMPERATURE_REFERENCES = {"1850-1900": "1850_1900", "1951-1980": "1951_1980"}


@mcp.tool()
async def get_co2_concentration(start_year: int | None = None, end_year: int | None = None) -> dict:
    """Annual atmospheric CO2 concentration in ppm: NOAA GML Mauna Loa measurements from 1959,
    spliced to the Law Dome ice-core record before 1959. This is a measured quantity (the
    accumulated stock of CO2 in the atmosphere), not an emissions flow and not a model output.
    Optionally restrict to `start_year`..`end_year` (inclusive; clipped to the available
    coverage, which is read from the data). The response carries `summary` (first/last value,
    change, percent change) -- quote that rather than deriving figures from the series -- plus
    `details.splice` (the splice year and the measured overlap gap between the two records;
    mention it when comparing across 1959) and the source `caveats`/`attribution`.
    Annual resolution only. Concentration and emissions move together over the long run, but
    this tool does not establish cause."""
    body = await fetch_correlation(
        "concentration", {"view": "level", "resolution": "annual", "start_year": start_year, "end_year": end_year}
    )
    body["summary"] = summarize_points(body["points"], include_pct=True)
    return body


@mcp.tool()
async def get_temperature_anomaly(
    start_year: int | None = None, end_year: int | None = None, reference: str = "1850-1900"
) -> dict:
    """Global mean surface temperature anomaly in °C (Berkeley Earth Land/Ocean, annual), i.e.
    the deviation from a reference period, not an absolute temperature. `reference` is
    '1850-1900' (pre-industrial, the default and what the dashboard shows) or '1951-1980'
    (Berkeley Earth's native baseline); the 1850-1900 offset is computed from Berkeley Earth's
    own early record and its derivation is in `details.offset`. Optionally restrict to
    `start_year`..`end_year` (inclusive; clipped to coverage, read from the data). The response
    carries `summary` (first/last value and change in °C -- quote it rather than deriving
    figures) and the source `caveats`, which include the note that this dataset is a
    preliminary, not-yet-peer-reviewed release whose values may be revised; mention that
    whenever you quote a temperature figure. The temperature series can run one year past the
    emissions data. This is an observed global quantity: never attribute it to any single
    country, and do not present it as proof that emissions caused a given change."""
    if reference not in TEMPERATURE_REFERENCES:
        raise ValueError(
            f"Unknown reference {reference!r} -- use one of: {', '.join(sorted(TEMPERATURE_REFERENCES))}."
        )
    body = await fetch_correlation(
        "temperature",
        {"view": "level", "baseline": TEMPERATURE_REFERENCES[reference], "start_year": start_year, "end_year": end_year},
    )
    summary = summarize_points(body["points"], include_pct=False)
    summary["reference"] = reference
    body["summary"] = summary
    return body


@mcp.tool()
async def get_correlation_metadata() -> dict:
    """Provenance and methodology for the climate-context data behind the other climate tools:
    every source (OWID, PRIMAP-hist, Berkeley Earth, NOAA GML) with its licence, coverage years,
    release/vintage and caveats; the Berkeley Earth 1850-1900 offset and how it was derived; the
    source/baseline combinations that are valid for the emissions-temperature relationship; the
    statement of why two different global totals are used; and freshness (`summary.stale_outputs`
    lists any pipeline output that is missing or out of date -- tell the user if it is non-empty).
    Use this to answer 'where does this data come from', 'how current is it' and 'what are its
    limits'. It is documentation of the data layer, not a climate model, and says nothing about
    individual countries' contribution to warming."""
    body = await fetch_correlation("meta")
    # The indicator catalog is a data dictionary, not something to answer questions from.
    body["indicator_count"] = len(body.pop("indicators", []))
    outputs = body.get("outputs", {})
    body["summary"] = {
        "sources": [
            {"id": s["id"], "coverage": s.get("coverage"), "retrieved_at": s.get("retrieved_at"), "license": s.get("license")}
            for s in body.get("sources", [])
        ],
        "stale_outputs": sorted(
            name for name, o in outputs.items() if o.get("status") != "available" or o.get("stale")
        ),
        "temperature_offset": body.get("temperature_offset"),
        "pipeline_failures": (body.get("pipeline_last_run") or {}).get("failures", {}),
    }
    return body


# --- relationship tools ---------------------------------------------------------------------

INTERPRETATION_NOTE_SHARE = (
    "Cumulative share of emissions describes where emissions occurred. It is not an estimate of "
    "any country's contribution to global warming, and no country's emissions are regressed "
    "against the global temperature series."
)
COMPOSITION_DEFAULT_START = 1970  # requirements §2.5: the recent all-gas view starts in 1970
SCENARIO_NAMES = {"bau": "BAU", "moderate": "Moderate", "aggressive": "Aggressive"}


def _relationship_label(source: str, variant: str | None) -> str:
    if source == "primap_ghg":
        return "recent all-gas relationship (PRIMAP-hist total GHG, 1970+; never called TCRE)"
    if variant == "fossil":
        return "secondary fossil-fuel-and-cement-only variant of the headline relationship"
    return "headline long-run relationship (OWID cumulative total anthropogenic CO2 vs temperature)"


@mcp.tool()
async def get_emissions_temperature_relationship(
    source: str = "owid_co2", baseline: str | None = None, variant: str | None = None
) -> dict:
    """The paired relationship between cumulative emissions and global temperature anomaly,
    with the fitted regression. Two distinct relationships -- never conflate them:
    (1) `source='owid_co2'` (default): the HEADLINE long-run relationship, OWID cumulative CO2
    since 1850 (fossil fuel, cement and land-use change) vs the Berkeley Earth anomaly, a
    simplified TCRE-style regression. `variant='fossil'` gives the labelled secondary
    fossil-and-cement-only fit. (2) `source='primap_ghg'`: the RECENT ALL-GAS relationship,
    PRIMAP-hist cumulative total GHG in CO2e from 1970 -- this one is NEVER called TCRE and is
    never compared with the AR6 range. `baseline` is 'preindustrial' (1850; owid_co2 default),
    '1970' (primap_ghg default) or '1990' (a short pair with no fit); an unsupported
    source/baseline pair is rejected with the valid combinations -- relay that rather than
    substituting another baseline. The response carries `summary` (relationship label, window,
    slope with its HAC 95% interval and unit, R², AR6 comparison for the headline only) -- quote
    that. Always say this is a long-run relationship, not a complete climate model and not proof
    of cause; mention the `caveats` (including that the temperature dataset is a preliminary
    release). It is global: never use it to attribute warming to a country."""
    params = {"source": source, "baseline": baseline, "variant": variant}
    body = await fetch_correlation("emissions-temperature", params)
    points = body["points"]
    summary: dict = {
        "relationship": _relationship_label(body["source"], body.get("variant")),
        "source": body["source"],
        "variant": body.get("variant"),
        "baseline": body["baseline"],
        "window": body["window"],
        "n_years": body["n_years"],
        "n_omitted_years": len(body.get("omitted_years", [])),
        "fit": body["fit"],
    }
    if points:
        first, last = points[0], points[-1]
        summary["first_pair"] = first
        summary["last_pair"] = last
        summary["temperature_change_c"] = round(last["temperature"] - first["temperature"], 3)
    ctx = body.get("fit_context") or {}
    if body["source"] == "owid_co2" and ctx.get("vs_ar6") is not None:
        summary["vs_ar6"] = ctx["vs_ar6"]
    if body["fit"] is None:
        summary["fit_note"] = "No fit is published for this window; the pair is context only."
    body["summary"] = summary
    return body


@mcp.tool()
async def get_ghg_composition(
    start_year: int | None = None, end_year: int | None = None, year: int | None = None
) -> dict:
    """How the global greenhouse-gas mix has changed: CO2, CH4 (methane), N2O (nitrous oxide)
    and fluorinated gases, in CO2-equivalent (IPCC AR5 GWP-100) from PRIMAP-hist, national
    totals excluding land-use change and international aviation/shipping. Give `year` for one
    year, or `start_year`/`end_year` for a range (not both kinds); omit all for 1970 to the latest
    complete year -- PRIMAP-hist values before 1970 are reconstructions from historical
    datasets, so the default start is 1970 (requirements §2.5); pass an earlier `start_year`
    explicitly to include them and say they are reconstructions. Years where a gas is not reported return it as null and omit it from
    `gases_included`; incomplete trailing years are excluded and listed in
    `excluded_incomplete_years`. `summary` gives the first and last year's shares and the
    change in percentage points per gas -- quote it. Global aggregate only; this tool has no
    country breakdown."""
    defaulted = year is None and start_year is None
    if defaulted:
        start_year = COMPOSITION_DEFAULT_START
    body = await fetch_correlation("ghg-composition", {"start_year": start_year, "end_year": end_year, "year": year})
    if defaulted:
        body["notes"].append(
            f"Showing {COMPOSITION_DEFAULT_START} onward: PRIMAP-hist values before {COMPOSITION_DEFAULT_START} are "
            "reconstructions from historical datasets (pass start_year to include them)."
        )
    years = body["years"]
    summary: dict = {"n_years": len(years), "excluded_incomplete_years": body.get("excluded_incomplete_years", [])}
    if years:
        def shares(row: dict) -> dict:
            return {v["gas"]: v["share_pct"] for v in row["values"]}

        first, last = years[0], years[-1]
        first_s, last_s = shares(first), shares(last)
        summary.update(
            first_year=first["year"],
            last_year=last["year"],
            first_shares_pct=first_s,
            last_shares_pct=last_s,
            last_total_mtco2e=last.get("components_total_mtco2e"),
            share_change_pp={
                g: round(last_s[g] - first_s[g], 2)
                for g in last_s
                if last_s.get(g) is not None and first_s.get(g) is not None
            },
        )
    body["summary"] = summary
    return body


@mcp.tool()
async def get_country_cumulative_share(
    countries: list[str] | None = None,
    year: int | None = None,
    limit: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    source: str = "owid_co2",
    gas_scope: str | None = None,
) -> dict:
    """Each country's cumulative share of global emissions -- where emissions have occurred over
    time. Two modes: omit `countries` for a RANKING in `year` (default: latest year; `limit`
    default 15, max 50; each row has cumulative and annual share), or pass `countries` (common
    English names, e.g. 'China', 'United States'; ISO3 codes also accepted; at most 10) for a
    SERIES over `start_year`..`end_year` (`year` and `limit` do not apply to a series).
    `source` is 'owid_co2' (fossil + cement CO2, longest history, default) or 'primap_ghg'
    (total GHG in CO2e, excluding land use); `gas_scope` is 'co2' or 'total_ghg' and normally
    follows from `source`. An unmatched country name is an explicit error with a suggestion.
    IMPORTANT: this is cumulative share of EMISSIONS, not a country's contribution to
    temperature -- never say or imply a country caused a given amount of warming, and never
    regress a country against the global temperature series. The response carries
    `interpretation_note` and the source `caveats` stating this; keep that framing in your
    answer. The denominator is the national sum excluding international aviation and shipping
    (it differs by design from the World series in the headline regression)."""
    params = {"source": source, "gas_scope": gas_scope}
    if countries:
        # The endpoint takes ISO3 codes; resolve names against its own country set first, one
        # extra call (a full ranking carries every country's code and name).
        roster = await fetch_correlation("country-share", {**params, "all_countries": True})
        codes = resolve_share_countries(countries, roster["rows"])
        body = await fetch_correlation(
            "country-share", {**params, "countries": codes, "start_year": start_year, "end_year": end_year, "year": year}
        )
        summary = {
            "mode": "series",
            "countries": [
                {
                    "country": sr["country"],
                    "name": sr["name"],
                    "first_year": sr["points"][0]["year"] if sr["points"] else None,
                    "first_share_pct": round(sr["points"][0]["share_pct"], 2) if sr["points"] else None,
                    "last_year": sr["points"][-1]["year"] if sr["points"] else None,
                    "last_share_pct": round(sr["points"][-1]["share_pct"], 2) if sr["points"] else None,
                    "last_cumulative_mt": round(sr["points"][-1]["cumulative_mt"], 1) if sr["points"] else None,
                }
                for sr in body["series"]
            ],
        }
    else:
        body = await fetch_correlation("country-share", {**params, "year": year, "limit": limit})
        rows = body["rows"]
        summary = {
            "mode": "ranking",
            "year": body["year"],
            "n_rows": len(rows),
            "top": [{"rank": r["rank"], "name": r["name"], "share_pct": round(r["share_pct"], 2)} for r in rows[:5]],
            "shown_share_pct_total": round(sum(r["share_pct"] for r in rows), 2),
        }
    summary["unit"] = body["unit"]
    summary["label"] = body["label"]
    body["summary"] = summary
    body["interpretation_note"] = INTERPRETATION_NOTE_SHARE
    return body


@mcp.tool()
async def get_scenario_temperature(scenarios: list[str] | None = None, line: str = "both") -> dict:
    """Indicative temperature outcomes implied by the BAU / Moderate / Aggressive emissions
    pathways to 2040: the existing scenario pathways are applied to the covered countries, the
    rest of the world is held at its last-observed share, and the headline regression slope
    converts the added cumulative emissions to implied warming. `scenarios` picks a subset
    (default all three); `line` is 'both', 'headline' (total anthropogenic CO2 slope) or
    'fossil_only'. `summary` gives each scenario's 2040 implied temperature level and added
    warming and the gap versus BAU -- quote it. The response also carries the pre-written
    `reading_note` and `spread`. ALWAYS label the result an 'illustrative, partial-coverage
    translation', not a climate-model projection; say it depends on the regression period, the
    emissions source and the stated assumptions (`assumptions`: rest-of-world share held, land
    use held flat). Warming is global and is not attributable to any one country."""
    names = None
    if scenarios:
        try:
            names = [SCENARIO_NAMES[s.strip().lower()] for s in scenarios]
        except KeyError as exc:
            raise ValueError(f"Unknown scenario {exc.args[0]!r} -- use any of: BAU, Moderate, Aggressive.") from None
    body = await fetch_correlation("scenario-temperature", {"scenario": names, "line": line})
    # step_check is the pipeline's internal per-country QA record (~16 KB), not answer material.
    body.get("base", {}).pop("step_check", None)
    final: dict = {}
    for name, rows in body["scenarios"].items():
        if not rows:
            continue
        last = rows[-1]
        final[name] = {
            "year": last["year"],
            "headline_level_c": (last.get("headline") or {}).get("level_c"),
            "headline_added_warming_c": (last.get("headline") or {}).get("delta_t_c"),
            "fossil_only_level_c": (last.get("fossil_only") or {}).get("level_c"),
            "annual_global_fossil_mt": last.get("global_fossil_mt"),
        }
    summary: dict = {"final_year_by_scenario": final, "line": body["line"]}
    bau = final.get("BAU", {}).get("headline_level_c")
    if bau is not None:
        summary["headline_level_gap_vs_bau_c"] = {
            n: round(f["headline_level_c"] - bau, 3) for n, f in final.items() if n != "BAU" and f["headline_level_c"] is not None
        }
    body["summary"] = summary
    return body
