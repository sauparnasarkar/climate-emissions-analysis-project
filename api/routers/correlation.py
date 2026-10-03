"""`/api/correlation/*` -- the Area 2 climate-context endpoints (ENHANCEMENTS.md Release 21, Phase 1.4, decisions 44-55).

Read-only over the files `pipeline/` wrote; nothing is recomputed per request. Phase 1.4a: `/meta`, `/concentration`, `/temperature`.
"""

from datetime import datetime, timezone
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from .. import climate_loaders as cl
from ..schemas_correlation import (
    CompositionYear,
    CorrelationConcentrationResponse,
    CorrelationCountryShareResponse,
    CorrelationEmissionsTemperatureResponse,
    CorrelationGhgCompositionResponse,
    CorrelationMetaResponse,
    CorrelationScenarioTemperatureResponse,
    CorrelationTemperatureResponse,
    GasValue,
    IndicatorInfo,
    OmittedYear,
    PairPoint,
    SeriesPoint,
    SharePoint,
    ShareRow,
    ShareSeries,
)

router = APIRouter(prefix="/correlation")

ConcentrationView = Literal["level", "yoy_pct", "mean5y", "index"]
IndexBaseline = Literal["preindustrial", "1970", "1990"]
Resolution = Literal["annual", "monthly"]
TemperatureView = Literal["level", "mean5y"]
TemperatureBaseline = Literal["1850_1900", "1951_1980"]
PairSource = Literal["owid_co2", "primap_ghg"]
PairBaseline = Literal["preindustrial", "1970", "1990"]
PairVariant = Literal["total", "fossil"]
PAIR_START = {"preindustrial": 1850, "1970": 1970, "1990": 1990}
PAIR_X = {("owid_co2", "total"): "owid_total_co2_world_cumulative_mt", ("owid_co2", "fossil"): "owid_co2_world_cumulative_mt", ("primap_ghg", "total"): "primap_ghg_total_cumulative_mtco2e"}
PAIR_Y = "temperature_anomaly_1850_1900_c"

CONCENTRATION_NOTE = ("Atmospheric CO2 concentration: NOAA GML Mauna Loa measurements from 1959, spliced to the Law Dome ice-core/firn spline before 1959 (different "
                      "stations and hemispheres; the splice and the measured overlap gap are in `details`). A measured quantity, not a model output.")
TEMPERATURE_NOTE = ("Global mean surface temperature anomaly (Berkeley Earth Land/Ocean). A measured-and-analysed quantity; the 95% uncertainty is the publisher's, for the "
                    "native-baseline anomaly, and is not re-derived for the 1850-1900 offset (whose own spread is in `details.offset`).")
META_NOTE = ("Context for the climate-correlation endpoints: sources, licences, baselines and the rules that decide which combinations are valid. Paired series "
             "elsewhere are interpretive context, not proof of causation.")
TWO_GLOBAL_TOTALS = ("Two different global totals are used on purpose. The emissions-temperature regression's X-variable is OWID's full World row, which includes "
                     "international aviation and shipping (they are real atmospheric loading, so excluding them would understate cumulative CO2). The country-share denominator "
                     "is the sum of national emissions, which excludes those bunkers, so country shares sum to 100% of territorial emissions. The two totals therefore differ "
                     "by the international transport line, published as its own indicator.")
MATRIX = [
    {"source": "owid_co2", "baseline": "preindustrial", "valid": True, "fit": "published (1850 window)", "note": "headline view"},
    {"source": "owid_co2", "baseline": "1970", "valid": True, "fit": "published (1970 window)", "note": None},
    {"source": "owid_co2", "baseline": "1990", "valid": True, "fit": None, "note": "pair only: no fit is published for a 1990 window"},
    {"source": "primap_ghg", "baseline": "preindustrial", "valid": False, "fit": None, "note": "422: the all-gas relationship is defined from 1970; no 1850-based fit exists"},
    {"source": "primap_ghg", "baseline": "1970", "valid": True, "fit": "published (recent all-gas relationship)", "note": "never called TCRE, never compared with the AR6 range"},
    {"source": "primap_ghg", "baseline": "1990", "valid": True, "fit": None, "note": "pair only, shorter window, warning in the response"},
]
OUTPUT_FILES = ("indicator_catalog.json", "correlation_headline.json", "correlation_all_gas.json", "correlation_composition.json", "correlation_country_share.json",
                "correlation_scenario_temperature.json")
IMPLEMENTED_ENDPOINTS = ["/api/correlation/meta", "/api/correlation/concentration", "/api/correlation/temperature", "/api/correlation/emissions-temperature", "/api/correlation/ghg-composition",
                         "/api/correlation/country-share", "/api/correlation/scenario-temperature"]
SOURCE_KEYS = ("source", "license", "coverage", "retrieved_at", "source_release", "update_cadence", "units", "geography", "gas_scope", "caveats", "citations",
               "required_citation_format", "land_use_license_note", "methodology", "source_urls")


def _unavailable(e: cl.ClimateDataUnavailable):
    return HTTPException(status_code=503, detail=e.message)


def _strings(xs) -> list[str]:
    return [x for x in (xs or []) if isinstance(x, str)]


def _attribution(series_ids: list[str]) -> list[dict]:
    prov = cl.load_provenance()
    out = []
    for sid in series_ids:
        e = prov.get(sid)
        if not isinstance(e, dict):  # a number must not be served without its source and licence (decision 46)
            raise cl.ClimateDataUnavailable(f"provenance.json has no entry for {sid}: its attribution cannot be attached")
        out.append({"series": sid, **{k: e[k] for k in ("source", "license", "citations", "required_citation_format", "land_use_license_note") if k in e}})
    return out


def _check_years(start_year: int | None, end_year: int | None) -> None:
    if start_year is not None and end_year is not None and start_year > end_year:
        raise HTTPException(status_code=422, detail=f"start_year ({start_year}) is after end_year ({end_year})")


def _info(entry: dict) -> IndicatorInfo:
    return IndicatorInfo(id=entry["id"], name=entry.get("name", entry["id"]), unit=entry.get("unit", ""), kind=entry.get("kind", ""), decimals=entry.get("decimals"),
                         description=entry.get("description"))


def _value(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _annual_points(values: pd.Series, uncertainty: pd.Series | None, start_year: int | None, end_year: int | None) -> tuple[list[SeriesPoint], list[str]]:
    """Every year between the requested bounds and the data's own coverage, a year with no value kept as an explicit null (no interpolation, no gap closing)."""
    first, last = int(values.index.min()), int(values.index.max())
    lo, hi = max(first, start_year if start_year is not None else first), min(last, end_year if end_year is not None else last)
    notes = []
    if lo > hi:
        return [], [f"no data in the requested range: coverage is {first}-{last}"]
    pts = [SeriesPoint(year=y, value=_value(values.get(y)), uncertainty=_value(uncertainty.get(y)) if uncertainty is not None else None) for y in range(lo, hi + 1)]
    missing = [p.year for p in pts if p.value is None]
    if missing:
        notes.append(f"{len(missing)} year(s) have no value and are returned as null, not interpolated: {missing[:10]}{' ...' if len(missing) > 10 else ''}")
    return pts, notes


def _series_response(entry: dict, ids: list[str], view: str, baseline: str | None, resolution: str, start_year, end_year, points, coverage, notes, note, vintage, details,
                     series_ids) -> dict:
    cat = cl.load_catalog()
    prov = cl.load_provenance()
    caveats = list(dict.fromkeys(_strings(entry.get("caveats")) + [c for s in series_ids for c in _strings((prov.get(s) or {}).get("caveats"))]))
    return dict(schema_version=cat.get("schema_version", 1), generated_at=cat.get("generated_at"), note=note, caveats=caveats, attribution=_attribution(series_ids),
                source_vintage=vintage, indicator=_info(entry), view=view, baseline=baseline, resolution=resolution, start_year=start_year, end_year=end_year,
                coverage=coverage, points=points, notes=notes, details=details)


@router.get("/concentration", response_model=CorrelationConcentrationResponse)
def get_concentration(view: ConcentrationView = "level", baseline: IndexBaseline | None = None, resolution: Resolution = "annual", start_year: int | None = Query(None, ge=0),
                      end_year: int | None = Query(None, ge=0)):
    _check_years(start_year, end_year)
    if view == "index" and baseline is None:
        raise HTTPException(status_code=422, detail="view=index requires baseline (preindustrial, 1970 or 1990)")
    if view != "index" and baseline is not None:
        raise HTTPException(status_code=422, detail="baseline applies only to view=index")
    if resolution == "monthly" and view != "level":
        raise HTTPException(status_code=422, detail="resolution=monthly supports view=level only (the derived views are annual)")
    try:
        if resolution == "monthly":
            df = cl.load_csv("co2_concentration_monthly_mlo.csv")
            if not {"year", "month", "co2_ppm"} <= set(df.columns):
                raise cl.ClimateDataUnavailable("co2_concentration_monthly_mlo.csv lacks year/month/co2_ppm columns")
            first, last = int(df["year"].min()), int(df["year"].max())
            sub = df[(df["year"] >= (start_year if start_year is not None else first)) & (df["year"] <= (end_year if end_year is not None else last))].sort_values(["year", "month"])
            pts = [SeriesPoint(year=int(r.year), month=int(r.month), value=_value(r.co2_ppm), deseasonalized=_value(getattr(r, "co2_deseasonalized_ppm", None))) for r in sub.itertuples()]
            notes = ["Monthly values are Mauna Loa only (from March 1958); the ice-core splice is annual and is not offered monthly."]
            if not pts:
                notes.append(f"no data in the requested range: coverage is {first}-{last}")
            entry = cl.catalog_entry("co2_concentration_ppm")
            prov = cl.load_provenance().get("co2_concentration_monthly_mlo") or {}
            return _series_response(entry, [], view, None, "monthly", start_year, end_year, pts, [first, last], notes, CONCENTRATION_NOTE, prov.get("source_release"),
                                    {"station": "Mauna Loa", "units": prov.get("units")}, ["co2_concentration_monthly_mlo"])
        sid = {"level": "co2_concentration_ppm", "yoy_pct": "co2_concentration_ppm__yoy_pct", "mean5y": "co2_concentration_ppm__mean5y",
               "index": f"co2_concentration_ppm__index_{baseline}"}[view]
        entry = cl.catalog_entry(sid)
        values = cl.indicator_series(sid)
        unc, notes_extra = None, []
        if view == "level":
            try:
                unc = cl.indicator_series("co2_concentration_uncertainty_ppm")
            except cl.ClimateDataUnavailable:
                notes_extra.append("the concentration uncertainty series is unavailable; uncertainty is null")
        pts, notes = _annual_points(values, unc, start_year, end_year)
        prov = cl.load_provenance().get("co2_concentration_annual") or {}
        return _series_response(entry, [sid], view, baseline, "annual", start_year, end_year, pts, [int(values.index.min()), int(values.index.max())], notes + notes_extra,
                                CONCENTRATION_NOTE, prov.get("source_release"), {"splice": prov.get("splice"), "units": prov.get("units")}, ["co2_concentration_annual"])
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)


@router.get("/temperature", response_model=CorrelationTemperatureResponse)
def get_temperature(view: TemperatureView = "level", baseline: TemperatureBaseline = "1850_1900", start_year: int | None = Query(None, ge=0), end_year: int | None = Query(None, ge=0)):
    _check_years(start_year, end_year)
    try:
        base_id = f"temperature_anomaly_{baseline}_c"
        sid = base_id if view == "level" else f"{base_id}__mean5y"
        entry = cl.catalog_entry(sid)
        values = cl.indicator_series(sid)
        unc = cl.indicator_series("temperature_uncertainty_95_c") if view == "level" else None
        pts, notes = _annual_points(values, unc, start_year, end_year)
        prov = cl.load_provenance().get("temperature_anomaly_annual") or {}
        details = {"units": prov.get("units"), "reference_period_native": prov.get("reference_period_native"), "methodology": prov.get("methodology"),
                   "offset": prov.get("preindustrial_offset") if baseline == "1850_1900" else None}
        if view == "mean5y":
            notes.append("the trailing 5-year mean carries no uncertainty band (the publisher's 95% interval is for the annual value)")
        return _series_response(entry, [sid], view, baseline, "annual", start_year, end_year, pts, [int(values.index.min()), int(values.index.max())], notes, TEMPERATURE_NOTE,
                                prov.get("source_release"), details, ["temperature_anomaly_annual"])
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)


REFRESH_CADENCE_DAYS = 31  # the pipeline refresh runs monthly
STALE_AFTER_DAYS = 45  # one cadence plus a grace period for a late or retried run


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(generated_at) -> float | None:
    """Days since the output was generated, or None when the timestamp is absent or unparsable (freshness is then unknown, never assumed fresh)."""
    if not isinstance(generated_at, str):
        return None
    try:
        ts = datetime.fromisoformat(generated_at)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max((_now() - ts).total_seconds() / 86400, 0.0)


def _output_status(name: str) -> dict:
    if not cl.json_exists(name):
        return {"status": "missing", "generated_at": None, "age_days": None, "stale": None, "reason": "not generated yet"}
    try:
        gen = cl.load_json(name).get("generated_at")
    except cl.ClimateDataUnavailable as e:
        return {"status": "unavailable", "generated_at": None, "age_days": None, "stale": None, "reason": e.message}
    age = _age_days(gen)
    return {"status": "available", "generated_at": gen, "age_days": None if age is None else round(age, 2), "stale": None if age is None else age > STALE_AFTER_DAYS, "reason": None}


def _last_run() -> dict | None:
    import json
    import os

    path = os.path.join(cl.climate_dir(), "last_run.json")
    if not os.path.exists(path):
        return None
    try:
        doc = json.load(open(path))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    srcs = doc.get("sources") if isinstance(doc.get("sources"), dict) else {}
    return {"started_at": doc.get("started_at"), "finished_at": doc.get("finished_at"),
            "sources": {k: {"records": v.get("records"), "deviations": len(v.get("deviations") or [])} for k, v in srcs.items() if isinstance(v, dict)},
            "failures": doc.get("failures") if isinstance(doc.get("failures"), dict) else {}}


@router.get("/meta", response_model=CorrelationMetaResponse)
def get_meta():
    try:
        cat = cl.load_catalog()
        prov = cl.load_provenance()
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)
    sources = [{"id": sid, **{k: e[k] for k in SOURCE_KEYS if k in e}} for sid, e in sorted(prov.items()) if isinstance(e, dict)]
    temp = prov.get("temperature_anomaly_annual") if isinstance(prov.get("temperature_anomaly_annual"), dict) else {}
    indicators = [{k: i.get(k) for k in ("id", "name", "unit", "kind", "scope", "decimals", "derived_from")} for i in cat.get("indicators", []) if isinstance(i, dict)]
    return CorrelationMetaResponse(
        schema_version=cat.get("schema_version", 1), generated_at=cat.get("generated_at"), note=META_NOTE, caveats=[], attribution=_attribution(sorted(prov)),
        source_vintage=temp.get("source_release"), sources=sources,
        baselines={"index_baselines": cat.get("baselines"), "trailing_window_years": cat.get("trailing_window_years"),
                   "temperature": {"native": "1951-1980", "preindustrial": "1850-1900 (computed from Berkeley Earth's own early record, not taken from the literature)"}},
        temperature_offset=temp.get("preindustrial_offset"), two_global_totals=TWO_GLOBAL_TOTALS, source_baseline_matrix=MATRIX, indicators=indicators,
        outputs={n: _output_status(n) for n in OUTPUT_FILES}, pipeline_last_run=_last_run(), endpoints=IMPLEMENTED_ENDPOINTS,
        freshness={"refresh_cadence_days": REFRESH_CADENCE_DAYS, "stale_after_days": STALE_AFTER_DAYS, "checked_at": _now().isoformat()})


# ------------------------------------------------------------------ /emissions-temperature (decision 48)


def _fit_block(source: str, variant: str):
    """(the pipeline output file, the block inside it that holds the fits) for a source and variant."""
    if source == "primap_ghg":
        return "correlation_all_gas.json", "recent_all_gas"
    return "correlation_headline.json", "headline" if variant == "total" else "secondary_fossil_only"


@router.get("/emissions-temperature", response_model=CorrelationEmissionsTemperatureResponse)
def get_emissions_temperature(source: PairSource = "owid_co2", baseline: PairBaseline | None = None, variant: PairVariant | None = None):
    if source == "primap_ghg" and variant is not None:
        raise HTTPException(status_code=422, detail="variant applies only to source=owid_co2 (the all-gas relationship has a single definition)")
    baseline = baseline or ("1970" if source == "primap_ghg" else "preindustrial")
    if source == "primap_ghg" and baseline == "preindustrial":
        raise HTTPException(status_code=422, detail="source=primap_ghg with baseline=preindustrial is not supported: the all-gas relationship is defined from 1970 and no 1850-based fit exists")
    variant = variant or "total"
    start = PAIR_START[baseline]
    try:
        xid = PAIR_X[("owid_co2" if source == "owid_co2" else "primap_ghg", variant if source == "owid_co2" else "total")]
        x, y = cl.indicator_series(xid), cl.indicator_series(PAIR_Y)
        out_file, block_key = _fit_block(source, variant)
        doc = cl.load_json(out_file)
        block = doc.get(block_key)
        if not isinstance(block, dict):
            raise cl.ClimateDataUnavailable(f"{out_file} has no {block_key} block")
        last = int(min(x.index.max(), y.index.max()))
        points, omitted = [], []
        for yr in range(start, last + 1):
            hx, hy = yr in x.index and pd.notna(x[yr]), yr in y.index and pd.notna(y[yr])
            if hx and hy:
                points.append(PairPoint(year=yr, cumulative_emissions=float(x[yr]), temperature=float(y[yr])))
            else:
                omitted.append(OmittedYear(year=yr, reason="both series missing" if not hx and not hy else ("emissions missing" if not hx else "temperature missing")))
        window = [points[0].year, points[-1].year] if points else [start, last]
        notes, warnings = [], []
        if omitted:
            notes.append(f"{len(omitted)} year(s) in {start}-{last} are omitted because a series has no value; nothing is interpolated")
        fit, ctx = None, {}
        match = next((w for w in block.get("windows", []) if isinstance(w, dict) and w.get("start") == window[0] and w.get("end") == window[1] and w.get("n_years") == len(points)), None)
        if match is not None:
            fit = {k: match.get(k) for k in ("start", "end", "n_years", "slope", "ci95_hac", "r_squared", "maxlags")}
            fit["unit"], fit["label"] = block.get("unit"), block.get("label")
            if block.get("range") and block["range"][0] == window[0]:  # the primary window: the full published context
                ctx = {"definition": doc.get("definition") if isinstance(doc.get("definition"), str) else None, "method": doc.get("method"), "methodology": doc.get("methodology"),
                       "stability": block.get("stability"), "hac_sensitivity": block.get("hac_sensitivity"), "fit": block.get("fit")}
                if source == "owid_co2":
                    ctx["vs_ar6"], ctx["ar6_reference"] = block.get("vs_ar6"), doc.get("ar6_reference")
                    if variant == "total":
                        ctx["fit_quality_note"] = block.get("fit_quality_note")
                        ctx["land_use_sensitivity"], ctx["land_use_weight_scan"] = block.get("land_use_sensitivity"), block.get("land_use_weight_scan")
            else:
                ctx = {"note": "stability, uncertainty-method comparison and the AR6 comparison are published for the primary window only"}
        else:
            notes.append(f"no fit is published for the {window[0]}-{window[1]} window of {len(points)} year(s), so none is shown (the pair is returned without one; nothing is computed on the fly)")
        if baseline == "1990":
            warnings.append(f"a {window[1] - window[0] + 1}-year window is short for this relationship; read the pair as context only")
        entry_x, entry_y = cl.catalog_entry(xid), cl.catalog_entry(PAIR_Y)
        prov = cl.load_provenance()
        sids = list(dict.fromkeys([entry_x.get("source_series"), entry_y.get("source_series")]))
        caveats = list(dict.fromkeys(_strings(doc.get("caveats")) + [c for s in sids for c in _strings((prov.get(s) or {}).get("caveats"))]))
        if source == "primap_ghg":
            caveats.append("The all-gas relationship is a descriptive regression, never called TCRE and never compared with the AR6 range.")
        return CorrelationEmissionsTemperatureResponse(
            schema_version=doc.get("schema_version", 1), generated_at=doc.get("generated_at"), note=doc.get("note") or "", caveats=caveats, attribution=_attribution(sids),
            source_vintage=doc.get("temperature_source_vintage") if isinstance(doc.get("temperature_source_vintage"), dict) else None, source=source,
            variant=variant if source == "owid_co2" else None, baseline=baseline, window=window, x=_info(entry_x), y=_info(entry_y), n_years=len(points), points=points,
            omitted_years=omitted, fit=fit, fit_context=ctx, warnings=warnings, notes=notes)
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)


# ------------------------------------------------------------------ /ghg-composition (decision 49)


@router.get("/ghg-composition", response_model=CorrelationGhgCompositionResponse)
def get_ghg_composition(start_year: int | None = Query(None, ge=0), end_year: int | None = Query(None, ge=0), year: int | None = Query(None, ge=0)):
    if year is not None and (start_year is not None or end_year is not None):
        raise HTTPException(status_code=422, detail="year cannot be combined with start_year/end_year")
    _check_years(start_year, end_year)
    try:
        doc = cl.load_json("correlation_composition.json")
        df = cl.load_csv("correlation_composition_annual.csv")
        if not {"year", "gas", "gas_name", "mtco2e", "share_pct"} <= set(df.columns):
            raise cl.ClimateDataUnavailable("correlation_composition_annual.csv lacks year/gas/gas_name/mtco2e/share_pct columns")
        cov = doc.get("coverage")
        per_year = {int(y["year"]): y for y in doc.get("years", []) if isinstance(y, dict) and "year" in y}
        lo, hi = (year, year) if year is not None else (start_year, end_year)
        years = sorted(per_year)
        sel = [y for y in years if (lo is None or y >= lo) and (hi is None or y <= hi)]
        by_year = {int(y): g for y, g in df.groupby("year")}
        out, notes = [], []
        for y in sel:
            meta = per_year[y]
            g = by_year.get(y)
            if g is None:
                raise cl.ClimateDataUnavailable(f"correlation_composition_annual.csv has no rows for {y}, which correlation_composition.json lists")
            order = {gid: i for i, gid in enumerate(x.get("id") for x in doc.get("gases", []) if isinstance(x, dict))}
            rows = sorted(g.itertuples(), key=lambda r: order.get(r.gas, 99))
            # the CSV must agree with the JSON metadata for this year: every published gas exactly once, a value for each gas listed in gases_included and none for the others
            seen = [r.gas for r in rows]
            if sorted(seen) != sorted(order) or len(set(seen)) != len(seen):
                raise cl.ClimateDataUnavailable(f"correlation_composition_annual.csv has gases {sorted(seen)} for {y}, but correlation_composition.json publishes {sorted(order)}")
            inc_list = meta.get("gases_included")
            if not isinstance(inc_list, list) or not all(isinstance(i, str) for i in inc_list) or not inc_list or len(set(inc_list)) != len(inc_list) or not set(inc_list) <= set(order):
                raise cl.ClimateDataUnavailable(f"gases_included for {y} in correlation_composition.json is not a non-empty, unique list of published gas ids: {inc_list!r}")
            included = set(inc_list)
            bad = sorted(r.gas for r in rows if (_value(r.mtco2e) is not None) != (r.gas in included) or (_value(r.share_pct) is not None) != (r.gas in included))
            if bad:
                raise cl.ClimateDataUnavailable(f"correlation_composition_annual.csv disagrees with gases_included in correlation_composition.json (value or share) for {y}: {', '.join(bad)}")
            out.append(CompositionYear(year=y, gases_included=_strings(meta.get("gases_included")), components_total_mtco2e=meta.get("components_total_mtco2e"),
                                       national_total_mtco2e=meta.get("national_total_mtco2e"), residual_pct=meta.get("residual_pct"),
                                       values=[GasValue(gas=r.gas, name=r.gas_name, mtco2e=_value(r.mtco2e), share_pct=_value(r.share_pct)) for r in rows]))
        if not out:
            notes.append(f"no data in the requested range: coverage is {cov[0]}-{cov[1]}" if isinstance(cov, list) and len(cov) == 2 else "no data in the requested range")
        if any("fgas" not in y.gases_included for y in out):
            notes.append("years where a gas has no value return it as null and omit it from gases_included; shares are over the gases included")
        return CorrelationGhgCompositionResponse(
            schema_version=doc.get("schema_version", 1), generated_at=doc.get("generated_at"), note=doc.get("basis") or "", caveats=_strings(doc.get("caveats")),
            attribution=_attribution(["primap_global_composition_annual"]), name=doc.get("name") or "Global greenhouse-gas composition", basis=doc.get("basis") or "",
            units=doc.get("units") or "", gases=[g for g in doc.get("gases", []) if isinstance(g, dict)], coverage=cov if isinstance(cov, list) else None, start_year=start_year,
            end_year=end_year, year=year, years=out, reconciliation=doc.get("reconciliation"), excluded_incomplete_years=[int(v) for v in doc.get("excluded_incomplete_years", [])],
            notes=notes)
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)


# ------------------------------------------------------------------ /country-share (decision 50)

SHARE_MAX_COUNTRIES = 10
SHARE_MAX_LIMIT = 50
SHARE_DEFAULT_LIMIT = 15


def _attr_from_doc(attr, default_series: str) -> list[dict]:
    """The pipeline's attribution is either {series: entry, ...} or one flat entry; the envelope carries a list of {series, ...}."""
    if isinstance(attr, dict) and attr and all(isinstance(v, dict) for v in attr.values()):
        return [{"series": k, **v} for k, v in attr.items()]
    if isinstance(attr, dict) and attr:
        return [{"series": default_series, **attr}]
    return []


def _share_combinations(doc: dict) -> list[dict]:
    return [c for c in doc.get("combinations", []) if isinstance(c, dict) and c.get("available") is True and "source" in c and "gas_scope" in c]


@router.get("/country-share", response_model=CorrelationCountryShareResponse)
def get_country_share(source: str = "owid_co2", gas_scope: str | None = None, year: int | None = Query(None, ge=0), limit: int = Query(SHARE_DEFAULT_LIMIT, ge=1, le=SHARE_MAX_LIMIT),
                      countries: list[str] | None = Query(None), start_year: int | None = Query(None, ge=0), end_year: int | None = Query(None, ge=0)):
    _check_years(start_year, end_year)
    if countries and year is not None:
        raise HTTPException(status_code=422, detail="year (a ranking) cannot be combined with countries (a series); use start_year/end_year with countries")
    if not countries and (start_year is not None or end_year is not None):
        raise HTTPException(status_code=422, detail="start_year/end_year apply to a countries series; use year for a ranking")
    if countries and len(countries) > SHARE_MAX_COUNTRIES:
        raise HTTPException(status_code=422, detail=f"at most {SHARE_MAX_COUNTRIES} countries per request ({len(countries)} given)")
    try:
        doc = cl.load_json("correlation_country_share.json")
        combos = _share_combinations(doc)
        valid = [f"source={c['source']}&gas_scope={c['gas_scope']}" for c in combos]
        if gas_scope is None:
            gas_scope = next((c["gas_scope"] for c in combos if c["source"] == source), None)
        combo = next((c for c in combos if c["source"] == source and c["gas_scope"] == gas_scope), None)
        if combo is None:
            raise HTTPException(status_code=422, detail=f"unsupported combination source={source}, gas_scope={gas_scope}; the published combinations are: {'; '.join(valid)}")
        df = cl.load_csv("correlation_country_share.csv")
        if not {"country", "year", "source", "gas_scope", "cumulative_mt", "share_pct"} <= set(df.columns):
            raise cl.ClimateDataUnavailable("correlation_country_share.csv lacks country/year/source/gas_scope/cumulative_mt/share_pct columns")
        d = df[(df["source"] == source) & (df["gas_scope"] == gas_scope)]
        if d.empty:
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv has no rows for source={source}, gas_scope={gas_scope}, which correlation_country_share.json publishes")
        years = pd.to_numeric(d["year"], errors="coerce").to_numpy(dtype=float)
        valid_years = np.isfinite(years) & (years >= 0) & (years < np.iinfo(np.int64).max) & (years == np.floor(years))
        if not valid_years.all():
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv has {int((~valid_years).sum())} row(s) with a blank, non-numeric, non-finite or non-integer year for source={source}, gas_scope={gas_scope}")
        d = d.copy()
        d["year"] = years.astype(np.int64)
        vals = d[["cumulative_mt", "share_pct"]].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)  # a non-numeric token becomes NaN and is refused below, not a 500
        if not np.isfinite(vals).all():
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv has {int((~np.isfinite(vals)).any(axis=1).sum())} row(s) with a blank, non-numeric, NaN or infinite value for source={source}, gas_scope={gas_scope}")
        cov_pub = combo.get("coverage")
        if isinstance(cov_pub, list) and len(cov_pub) == 2 and (int(d["year"].min()), int(d["year"].max())) != (cov_pub[0], cov_pub[1]):
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv spans {int(d['year'].min())}-{int(d['year'].max())} for source={source}, gas_scope={gas_scope}, but correlation_country_share.json "
                                            f"publishes coverage {cov_pub[0]}-{cov_pub[1]}: the two files are out of step")
        pub_rows, pub_countries = combo.get("n_rows"), combo.get("n_countries")
        if (isinstance(pub_rows, int) and len(d) != pub_rows) or (isinstance(pub_countries, int) and d["country"].nunique() != pub_countries):
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv has {len(d)} rows for {d['country'].nunique()} countries for source={source}, gas_scope={gas_scope}, but "
                                            f"correlation_country_share.json publishes {pub_rows} rows for {pub_countries} countries: the two files are out of step")
        if d.duplicated(["country", "year"]).any():
            raise cl.ClimateDataUnavailable(f"correlation_country_share.csv has duplicate country/year rows for source={source}, gas_scope={gas_scope}")
        names = {c["iso3"]: c.get("name", c["iso3"]) for c in doc.get("countries", []) if isinstance(c, dict) and "iso3" in c}
        cov = combo.get("coverage") if isinstance(combo.get("coverage"), list) else None
        base = dict(schema_version=doc.get("schema_version", 1), generated_at=doc.get("generated_at"), note=doc.get("note") or "", caveats=_strings(doc.get("caveats")),
                    attribution=_attr_from_doc(doc.get("attribution"), "country_share"), name=doc.get("name") or "Country cumulative share of global emissions", method=doc.get("method") or "",
                    source=source, gas_scope=gas_scope, label=combo.get("label") or "", unit=combo.get("unit") or "", coverage=cov, cumulative_from=combo.get("cumulative_from"),
                    denominator=combo.get("denominator"), reconciliation=combo.get("reconciliation"),
                    details={"gaps": combo.get("gaps"), "ended_before_last_year": combo.get("ended_before_last_year"), "published_from": doc.get("published_from")})
        if countries:
            codes = list(dict.fromkeys(c.strip().upper() for c in countries))
            unknown = [c for c in codes if c not in names]
            if unknown:
                raise HTTPException(status_code=404, detail=f"unknown country code(s): {', '.join(unknown)} (ISO3 codes are listed in correlation_country_share.json)")
            lo = start_year if start_year is not None else (cov[0] if cov else int(d["year"].min()))
            hi = end_year if end_year is not None else (cov[1] if cov else int(d["year"].max()))
            series, notes = [], []
            for c in codes:
                sub = d[(d["country"] == c) & (d["year"] >= lo) & (d["year"] <= hi)].sort_values("year")
                if sub.empty:
                    notes.append(f"{c} has no rows for this source and gas scope in {lo}-{hi}")
                series.append(ShareSeries(country=c, name=names[c], points=[SharePoint(year=int(r.year), cumulative_mt=float(r.cumulative_mt), share_pct=float(r.share_pct)) for r in sub.itertuples()]))
            return CorrelationCountryShareResponse(**base, mode="series", start_year=start_year, end_year=end_year, series=series, notes=notes)
        latest = int(d["year"].max())
        yr = year if year is not None else latest
        sub = d[d["year"] == yr].sort_values(["share_pct", "country"], ascending=[False, True])
        notes = []
        if sub.empty:
            notes.append(f"no data for {yr}: coverage is {cov[0]}-{cov[1]}" if cov else f"no data for {yr}")
        rows = [ShareRow(rank=i + 1, country=r.country, name=names.get(r.country, r.country), cumulative_mt=float(r.cumulative_mt), share_pct=float(r.share_pct))
                for i, r in enumerate(sub.head(limit).itertuples())]
        total = float(sub["cumulative_mt"].sum()) if not sub.empty else None
        return CorrelationCountryShareResponse(**base, mode="ranking", year=yr, limit=limit, total_cumulative_mt=total, rows=rows, notes=notes)
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)


# ------------------------------------------------------------------ /scenario-temperature (decision 51)

ScenarioName = Literal["BAU", "Moderate", "Aggressive"]
ScenarioLine = Literal["both", "headline", "fossil_only"]


@router.get("/scenario-temperature", response_model=CorrelationScenarioTemperatureResponse)
def get_scenario_temperature(scenario: list[ScenarioName] | None = Query(None), line: ScenarioLine = "both"):
    try:
        doc = cl.load_json("correlation_scenario_temperature.json")
        scen = doc.get("scenarios")
        if not isinstance(scen, dict) or not scen:
            raise cl.ClimateDataUnavailable("correlation_scenario_temperature.json has no scenarios")
        for key in ("assumptions", "base"):
            if not isinstance(doc.get(key), dict):
                raise cl.ClimateDataUnavailable(f"correlation_scenario_temperature.json has no {key} block")
        chosen = [s for s in sorted(scen) if not scenario or s in scenario]
        missing = [s for s in (scenario or []) if s not in scen]
        if missing:
            raise cl.ClimateDataUnavailable(f"correlation_scenario_temperature.json has no {', '.join(missing)} scenario")
        drop = {"headline": "fossil_only", "fossil_only": "headline"}.get(line)
        out = {s: [{k: v for k, v in row.items() if k != drop} for row in scen[s]] for s in chosen}
        notes = []
        if scenario and len(chosen) != len(scen):
            notes.append("`spread` and `reading_note` describe all published scenarios, not only the ones selected here")
        if line == "headline":
            notes.append("the fossil-only line is omitted from every row")
        if line == "fossil_only":
            notes.append("the headline line is omitted from every row; `spread` and `reading_note` are defined on the headline line")
        return CorrelationScenarioTemperatureResponse(
            schema_version=doc.get("schema_version", 1), generated_at=doc.get("generated_at"), note=doc.get("note") or "", caveats=_strings(doc.get("caveats")),
            attribution=_attr_from_doc(doc.get("attribution"), "owid_world_co2_annual"),
            source_vintage=doc.get("temperature_source_vintage") if isinstance(doc.get("temperature_source_vintage"), dict) else None, name=doc.get("name") or "Scenario temperature translation",
            method=doc.get("method") or "", labels=_strings(doc.get("labels")), line=line, selected_scenarios=chosen, scenarios=out, assumptions=doc["assumptions"], base=doc["base"],
            covered_countries=[c for c in doc.get("covered_countries", []) if isinstance(c, dict)], scenario_source=doc.get("scenario_source") if isinstance(doc.get("scenario_source"), dict) else None,
            spread=doc.get("spread") if isinstance(doc.get("spread"), dict) else None, reading_note=doc.get("reading_note") if isinstance(doc.get("reading_note"), str) else None, notes=notes)
    except cl.ClimateDataUnavailable as e:
        raise _unavailable(e)
