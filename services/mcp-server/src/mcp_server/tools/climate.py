"""SPEC.md §5.1 Area 2 tools: the indicator tools (get_co2_concentration,
get_temperature_anomaly, get_correlation_metadata) and the relationship tools
(get_emissions_temperature_relationship, get_ghg_composition, get_country_cumulative_share,
get_scenario_temperature).

Each returns the API body unchanged (full series + envelope) with a deterministic `summary`
added. Capping what the *model* sees is the agent's job (agent SPEC.md §15.4), not this server's.
"""

from __future__ import annotations

from ..climate import (
    SHARE_SUMMARY_UNITS,
    check_since_year,
    gt_unit,
    fetch_correlation,
    normalize_typography,
    period_rows,
    resolve_share_countries,
    share_ranking_summary,
    share_series_summary,
    since_ranking_summary,
    since_series_block,
    summarize_points,
    world_total_mt,
)
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
# country-share publishes PRIMAP-hist as `primap_hist`; emissions-temperature calls the same source
# `primap_ghg`. Accept both so a caller following either endpoint's vocabulary succeeds.
SHARE_SOURCE_ALIASES = {"primap_ghg": "primap_hist"}
SCENARIO_NAMES = {"bau": "BAU", "moderate": "Moderate", "aggressive": "Aggressive"}


def reconstruction_note(years: list[dict]) -> str | None:
    """A note whenever any returned year predates 1970, however the range was asked for."""
    early = [y["year"] for y in years if y["year"] < COMPOSITION_DEFAULT_START]
    if not early:
        return None
    return (
        f"{len(early)} returned year(s) ({min(early)}-{max(early)}) predate {COMPOSITION_DEFAULT_START}: PRIMAP-hist values "
        "before then are reconstructions from historical datasets, not country-reported data -- say so when quoting them."
    )


def _relationship_label(source: str, variant: str | None, baseline: str, window: list[int]) -> str:
    span = f"{window[0]}-{window[1]}"
    if source == "primap_ghg":
        # The start comes from the returned window: a 1990 baseline is a shorter pair, not 1970+.
        return f"recent all-gas relationship (PRIMAP-hist total GHG, {span}; never called TCRE)"
    # The headline is the pre-industrial (1850-start) total fit only; a 1970 or 1990 window of the
    # same series is a selected-window view (the 1990 one has no published fit) and must not be
    # presented as the headline.
    if baseline != "preindustrial":
        what = "fossil-fuel-and-cement-only" if variant == "fossil" else "total anthropogenic CO₂"
        return f"selected-window relationship, NOT the headline fit (OWID cumulative {what} vs temperature, {span})"
    if variant == "fossil":
        return "secondary fossil-fuel-and-cement-only variant of the headline relationship"
    return "headline long-run relationship (OWID cumulative total anthropogenic CO₂ vs temperature)"


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
    slope with its HAC 95% interval and unit, R², `cumulative` (the first/last cumulative emissions already in GtCO2 -- quote it; the raw `points` are in Mt, never convert them yourself), and, for the pre-industrial OWID fits only (the headline and its fossil-only
    variant), the comparison with the AR6 very-likely range; the all-gas relationship and the
    1970/1990 windows never carry one) -- quote
    that. Always say this is a long-run relationship, not a complete climate model and not proof
    of cause; mention the `caveats` (including that the temperature dataset is a preliminary
    release). It is global: never use it to attribute warming to a country."""
    params = {"source": source, "baseline": baseline, "variant": variant}
    body = await fetch_correlation("emissions-temperature", params)
    points = body["points"]
    summary: dict = {
        "relationship": _relationship_label(body["source"], body.get("variant"), body["baseline"], body["window"]),
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
        # The pairs' cumulative figures are in the API's own unit (Mt CO2 / Mt CO2e); the model kept misreading them as Gt (1000x). State the
        # unit, and give the Gt figures ready to quote -- never to be derived from the pairs.
        x_unit = (body.get("x") or {}).get("unit") or "Mt CO2"
        summary["pair_unit"] = {"cumulative_emissions": x_unit, "temperature": "°C"}
        if x_unit.startswith("Mt"):
            gt_unit = normalize_typography("Gt" + x_unit[2:])
            summary["cumulative"] = {
                "unit": gt_unit,
                "first_year": first["year"],
                "first": round(first["cumulative_emissions"] / 1000),
                "last_year": last["year"],
                "last": round(last["cumulative_emissions"] / 1000),
            }
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
        body["notes"].append(f"Showing {COMPOSITION_DEFAULT_START} onward by default (pass start_year to include earlier years).")
    note = reconstruction_note(body["years"])
    if note:
        body["notes"].append(note)
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
    since_year: int | None = None,
) -> dict:
    """Each country's cumulative share of global emissions -- where emissions have occurred over
    time. Two modes: omit `countries` for a RANKING in `year` (default: latest year; `limit`
    default 15, max 50; each row has cumulative and annual share), or pass `countries` (common
    English names, e.g. 'China', 'United States'; ISO3 codes also accepted; at most 10) for a
    SERIES over `start_year`..`end_year` (`year` and `limit` do not apply to a series and are rejected; likewise `start_year`/`end_year` do not apply to a ranking).
    `source` is 'owid_co2' (fossil + cement CO2, longest history, default; gas_scope 'co2') or
    'primap_hist' (PRIMAP-hist; gas_scope 'co2' or 'total_ghg' -- total GHG in CO2e, excluding
    land use; 'primap_ghg' is accepted as an alias). Omit `gas_scope` to get the source's
    default; an unpublished source/gas_scope pair is rejected with the published ones. An unmatched country name is an explicit error with a suggestion.
    "SINCE YYYY": for how much was emitted since a year ("China since 1990", "the top emitters since
    1970") pass `since_year` (1851 to the latest year), in either mode, NEVER `start_year` (which
    only chooses the years a series is shown from, and a ranking rejects it). `since_year=1990` is
    emissions in 1990 to the latest year: each country's cumulative total then minus its total at
    1989. The `summary.since` block carries each country's emitted amount (`emitted_gt` /
    `emitted_text`), its share of the emissions IN THAT PERIOD (`share_of_period_pct`, not the
    cumulative share; of the World's emissions for OWID, of the source's own total for PRIMAP-hist --
    `summary.since.basis` says which) and its rank by emissions in the period; a ranking with `since_year` is the
    ranking by emissions in the period (`since_rows`) -- quote those, and say the period ("1990-2024").
    The total counted from the first record is still in the summary, as context only. Omit
    `since_year` for the total since records began. `end_year` (series) or `year` (ranking) can end
    the period earlier. There is no per-gas cumulative: CO2 (OWID, PRIMAP) and total greenhouse
    gases in CO2e (PRIMAP) only, so cumulative methane or nitrous oxide is not available.
    UNITS: a field's unit is its suffix (`_gt` = GtCO2, billion tonnes; `_mt` = MtCO2, million tonnes;
    `_pct` = percent; see `summary.units`) -- for `gas_scope='total_ghg'` (PRIMAP-hist total
    greenhouse gases) the amounts are CO2-EQUIVALENT: GtCO2e / MtCO2e. The `*_text` fields are
    already formatted with the right unit (GtCO2 or GtCO2e) -- quote those as written; never put Mt on
    a `_gt` figure (434.9 Gt is not 434.9 Mt).
    QUOTE THE SUMMARY: per country in a series it carries `share_change_pp` and `share_trend`
    ('rising' / 'falling' / 'steady', computed over `trend_window` -- name that window, a trend since
    1850 says little about recent years), the latest cumulative total in Gt, `rank` of `rank_of`
    countries (latest year only), and the latest annual share (a share of the year's emissions, set
    against the cumulative share it shows whether the cumulative share is still rising); for OWID
    `rest_of_world` is what the countries shown leave of the World total.
    IMPORTANT: this is cumulative share of EMISSIONS, not a country's contribution to
    temperature -- never say or imply a country caused a given amount of warming, and never
    regress a country against the global temperature series. The response carries
    `interpretation_note` and the source `caveats` stating this; keep that framing in your
    answer. For `owid_co2` the denominator is the World total including international aviation and
    shipping (the same total as the dashboard and the headline regression), so the countries'
    shares sum to less than 100 and `remainder` (ranking) or `remainder_series` (series) holds
    only the part of the World total that no country holds (international aviation and shipping
    plus a small unassigned residual): countries left out by `limit` are NOT in it, so the rows
    shown plus `remainder` reach 100 only when every country is returned; say 'share of the
    World total'. PRIMAP-hist has no world aggregate, so its shares
    are of its own country sum (they sum to 100, no `remainder`): say 'share of PRIMAP-hist's total'."""
    if countries is not None and not countries:
        raise ValueError("`countries` is an empty list; omit it for a ranking, or name at least one country.")
    if countries and limit is not None:
        raise ValueError("`limit` applies to a ranking only; omit it when passing `countries` (a series).")
    if since_year is not None and countries and year is not None:
        raise ValueError("`year` does not apply to a series; with `since_year` use `end_year` to end the period earlier.")
    if since_year is not None and countries and start_year is not None and start_year != since_year:
        raise ValueError("`since_year` already sets where a series starts; omit `start_year` (or pass the same year).")
    if not countries and (start_year is not None or end_year is not None):
        # The API rejects these for a ranking; a live answer lost its data to that failed call. Say what to pass instead, so a retry succeeds.
        raise ValueError(
            "`start_year`/`end_year` choose the years of a SERIES (pass `countries`). For a ranking of what was emitted since a year pass `since_year` "
            "(for example since_year=1970); for a ranking as of one year pass `year`."
        )
    params = {"source": SHARE_SOURCE_ALIASES.get(source, source), "gas_scope": gas_scope}
    if since_year is not None:
        return await _share_since(params, countries, since_year, year, end_year, limit)
    if countries:
        # The endpoint takes ISO3 codes; resolve names against its own country set first, one
        # extra call (a full ranking carries every country's code and name).
        roster = await fetch_correlation("country-share", {**params, "all_countries": True})
        codes = resolve_share_countries(countries, roster["rows"])
        body = await fetch_correlation(
            "country-share", {**params, "countries": codes, "start_year": start_year, "end_year": end_year, "year": year}
        )
        summary = share_series_summary(body, roster, start_year)
    else:
        # start_year/end_year are forwarded even though they belong to a series: the API rejects
        # them with an explanatory 422, which is better than silently dropping what the caller asked.
        body = await fetch_correlation(
            "country-share", {**params, "year": year, "limit": limit, "start_year": start_year, "end_year": end_year}
        )
        summary = share_ranking_summary(body)
    # NOT the body's `unit` ("Mt CO2"): the summary mixes Mt and Gt fields, so a single unit here mislabelled the Gt ones (a live answer said "434.9 Mt" for the
    # United States, 434.9 Gt). Each field's unit is its suffix; the `*_text` fields are ready to quote.
    summary["units"] = SHARE_SUMMARY_UNITS
    summary["label"] = body["label"]
    body["summary"] = summary
    body["interpretation_note"] = INTERPRETATION_NOTE_SHARE
    return body


async def _share_since(params: dict, countries: list[str] | None, since_year: int, year: int | None, end_year: int | None, limit: int | None) -> dict:
    """`get_country_cumulative_share` with `since_year`: emissions in a period (Release 24.7). The end-year and base-year all-countries rankings give every
    country's amount in the period; a series is the usual series from `since_year` plus the `since` block, a ranking is the period ranking in `since_rows`."""
    if limit is not None and not 1 <= limit <= 50:
        # the ranking is sliced here, not by the API (which validates `limit` to 1-50 for every other ranking): a zero, negative or oversized limit must not slip through
        raise ValueError(f"`limit` must be between 1 and 50; got {limit}.")
    latest = await fetch_correlation("country-share", {**params, "all_countries": True})
    end = year if (not countries and year is not None) else (end_year if countries and end_year is not None else None)
    check_since_year(since_year, latest["year"])
    if end is not None and (end < since_year or end > latest["year"]):
        raise ValueError(f"The period must end between {since_year} and {latest['year']}; got {end}.")
    end_ranking = latest if end in (None, latest["year"]) else await fetch_correlation("country-share", {**params, "all_countries": True, "year": end})
    end_year_used = end_ranking["year"]
    base = await fetch_correlation("country-share", {**params, "all_countries": True, "year": since_year - 1})
    if not base.get("rows"):
        raise ValueError(f"No country shares are published for {since_year - 1}, the year before since_year; see the coverage in the response notes.")
    rows, world_emitted = period_rows(end_ranking, base)
    owid = bool(end_ranking.get("remainder"))
    if countries:
        codes = resolve_share_countries(countries, latest["rows"])
        body = await fetch_correlation("country-share", {**params, "countries": codes, "start_year": since_year, "end_year": end_year, "year": None})
        summary = share_series_summary(body, end_ranking, None)  # not start_year: the window note would say the opposite of what since_year does
        summary["since"] = since_series_block(rows, world_emitted, codes, since_year, end_year_used, owid, world_total_mt(base), gt_unit(end_ranking), latest["year"])
    else:
        shown = rows[: (limit if limit is not None else 15)]
        body = {**end_ranking, "rows": [], "since_rows": shown, "remainder": None, "total_cumulative_mt": None, "annual_total_mt": None}
        summary = since_ranking_summary(rows, shown, world_emitted, since_year, end_year_used, owid, gt_unit(end_ranking))
    body["since_year"] = since_year
    summary["units"] = SHARE_SUMMARY_UNITS
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
    # Gap versus BAU for every line the response carries (the API drops the other line's fields).
    gaps: dict = {}
    for key, label in (("headline_level_c", "headline"), ("fossil_only_level_c", "fossil_only")):
        bau = final.get("BAU", {}).get(key)
        if bau is not None:
            gaps[label] = {n: round(f[key] - bau, 3) for n, f in final.items() if n != "BAU" and f[key] is not None}
    if gaps:
        summary["level_gap_vs_bau_c"] = gaps
    body["summary"] = summary
    return body
