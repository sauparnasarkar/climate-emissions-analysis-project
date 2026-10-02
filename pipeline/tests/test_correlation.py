import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import correlation as C
from pipeline import harmonize
from pipeline.tests.test_harmonize import write_inputs

GTC = 44.009 / 12.011


def stage(tmp_path, edit_inputs=None, vintage="2025-01-10T04:48:46+00:00", notices=None, drop=()):
    """Synthetic inputs -> harmonize -> correlate. Returns (report, output dict)."""
    prov_path = write_inputs(tmp_path, drop=drop)
    prov = json.loads(open(prov_path).read())
    if "temperature_anomaly_annual" in prov and vintage:
        prov["temperature_anomaly_annual"]["source_release"] = {"http_last_modified": vintage}
    prov["owid_world_co2_annual"].update({"citations": ["OWID", "GCP"], "attribution_required": True, "required_citation_format": "Global Carbon Project. (<year>) ...",
                                          "land_use_license_note": "No formal license (e.g., CC BY) is stated"})
    open(prov_path, "w").write(json.dumps(prov))
    if edit_inputs:
        edit_inputs(str(tmp_path))
    harmonize.run(str(tmp_path), prov_path)
    npath = str(tmp_path / "notices.json")
    if notices is not None:
        open(npath, "w").write(json.dumps(notices))
    rep = C.run(str(tmp_path), notices_path=npath)
    return rep, json.loads((tmp_path / "correlation_headline.json").read_text())


# ---------------------------------------------------------------- the statistics, checked against independent calculations


def manual_newey_west_se(x, y, L):
    """Bartlett-kernel Newey-West standard error of the slope, from the sandwich formula (independent of statsmodels)."""
    X = np.column_stack([np.ones(len(x)), x]); n = len(y)
    beta = np.linalg.solve(X.T @ X, X.T @ y); e = y - X @ beta
    u = X * e[:, None]
    S = u.T @ u
    for j in range(1, L + 1):
        w = 1 - j / (L + 1)
        G = u[j:].T @ u[:-j]
        S += w * (G + G.T)
    bread = np.linalg.inv(X.T @ X)
    return float(np.sqrt((bread @ S @ bread)[1, 1]))


def ar1_data(n=175, rho=0.6, seed=7, slope=0.5):
    rng = np.random.default_rng(seed)
    x_mt = np.cumsum(rng.uniform(5e3, 4e4, n))  # a growing cumulative series, in Mt
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = rho * e[i - 1] + rng.normal(0, 0.08)
    return x_mt, 0.1 + slope * x_mt / 1e6 + e


def test_ols_recovers_a_known_slope_exactly_and_reports_per_1000_gtco2():
    x_mt = np.linspace(1e4, 2.5e6, 100)
    f = C.fit_line(x_mt, 0.25 + 0.5 * x_mt / 1e6, 4)
    assert f["slope"] == pytest.approx(0.5, abs=1e-12) and f["intercept"] == pytest.approx(0.25, abs=1e-12) and f["r_squared"] == pytest.approx(1.0)
    assert f["n"] == 100 and f["ci95_hac"][0] == pytest.approx(0.5, abs=1e-6) and f["ci95_hac"][1] == pytest.approx(0.5, abs=1e-6)


def test_slope_and_plain_se_match_closed_form_ols():
    x_mt, y = ar1_data()
    f = C.fit_line(x_mt, y, 8)
    x = x_mt / 1e6
    slope, intercept = np.polyfit(x, y, 1)
    assert f["slope"] == pytest.approx(slope, rel=1e-10) and f["intercept"] == pytest.approx(intercept, rel=1e-8)
    resid = y - (intercept + slope * x)
    se = np.sqrt(resid @ resid / (len(y) - 2) / np.sum((x - x.mean()) ** 2))
    assert f["se_ols"] == pytest.approx(se, rel=1e-10)
    assert f["r_squared"] == pytest.approx(1 - resid @ resid / np.sum((y - y.mean()) ** 2), rel=1e-10)


@pytest.mark.parametrize("L", [0, 2, 4, 8, 16])
def test_hac_se_matches_an_independent_newey_west_implementation(L):
    x_mt, y = ar1_data()
    f = C.fit_line(x_mt, y, L)
    assert f["se_hac"] == pytest.approx(manual_newey_west_se(x_mt / 1e6, y, L), rel=1e-9)
    lo, hi = f["ci95_hac"]
    assert (lo + hi) / 2 == pytest.approx(f["slope"], rel=1e-12) and (hi - lo) / 2 == pytest.approx(1.959963984540054 * f["se_hac"], rel=1e-12)


def test_hac_is_wider_than_plain_ols_when_residuals_are_autocorrelated():
    x_mt, y = ar1_data(rho=0.7)
    f = C.fit_line(x_mt, y, 8)
    assert f["se_hac"] > 1.2 * f["se_ols"] and f["residual_lag1_autocorrelation"] > 0.4 and f["durbin_watson"] < 1.2


def test_slope_does_not_depend_on_where_the_cumulative_starts():
    """A constant added to x moves only the intercept (why the 1750-based fossil cumulative and the 1850-based total are comparable)."""
    x_mt, y = ar1_data()
    a, b = C.fit_line(x_mt, y, 8), C.fit_line(x_mt + 3.7e5, y, 8)
    assert a["slope"] == pytest.approx(b["slope"], rel=1e-10) and a["se_hac"] == pytest.approx(b["se_hac"], rel=1e-9) and a["intercept"] != pytest.approx(b["intercept"])


@pytest.mark.parametrize("n,expected", [(175, 8), (55, 5), (20, 4), (125, 7), (75, 6)])
def test_hac_bandwidth_rule(n, expected):
    assert C.hac_lags(n) == expected


# ---------------------------------------------------------------- the stage on synthetic harmonized data


def test_output_structure_conversion_ar6_and_published_sensitivities(tmp_path):
    rep, out = stage(tmp_path)
    assert rep.deviations == [] and rep.records["correlation_headline"] == 2 and out["schema_version"] == 1  # two variants published
    h, s = out["headline"], out["secondary_fossil_only"]
    assert h["x_indicator"] == "owid_total_co2_world_cumulative_mt" and s["x_indicator"] == "owid_co2_world_cumulative_mt" and h["y_indicator"] == "temperature_anomaly_1850_1900_c"
    assert h["range"] == [1850, 2024] and h["n_years"] == 175 and h["fit"]["maxlags"] == 8 and h["unit"] == "°C per 1,000 GtCO2"
    assert h["fit"]["slope_per_1000_gtc"] == pytest.approx(h["fit"]["slope"] * GTC, rel=1e-12)
    assert out["ar6_reference"]["very_likely_range"] == [0.27, 0.63] and out["ar6_reference"]["best_estimate"] == 0.45
    assert [r["maxlags"] for r in h["hac_sensitivity"]] == [4, 8, 16] and h["hac_sensitivity"][1]["se_hac"] == pytest.approx(h["fit"]["se_hac"])
    assert [w["start"] for w in h["windows"]] == [1850, 1900, 1950, 1970] and h["windows"][0]["slope"] == pytest.approx(h["fit"]["slope"])
    assert [w["n_years"] for w in h["windows"]] == [175, 125, 75, 55] and [w["maxlags"] for w in h["windows"]] == [8, 7, 6, 5]
    assert "land_use_sensitivity" in h and "land_use_sensitivity" not in s
    lo, hi = out["ar6_reference"]["very_likely_range"]
    assert h["vs_ar6"]["within_very_likely_range"] == (lo <= h["fit"]["slope"] <= hi)
    assert h["vs_ar6"]["ratio_to_best_estimate"] == pytest.approx(h["fit"]["slope"] / 0.45)


def test_headline_and_variant_equal_independent_polyfits_of_the_synthetic_series(tmp_path):
    _, out = stage(tmp_path)
    tol = dict(rel=1e-6)  # harmonized Mt values are rounded to whole Mt (decimals=0): ~1e-7 relative on a 2.75-million-Mt cumulative
    yrs = np.arange(1850, 2025)
    temp = np.linspace(-0.13, 1.6, 175)
    fossil_flow = lambda y: 10.0 * (y - 1749); luc_flow = lambda y: 3.0 * (y - 1849)
    fossil_1850 = np.cumsum([fossil_flow(y) for y in yrs]); luc = np.cumsum([luc_flow(y) for y in yrs])
    total = fossil_1850 + luc
    assert out["headline"]["fit"]["slope"] == pytest.approx(np.polyfit(total / 1e6, temp, 1)[0], **tol)
    assert out["secondary_fossil_only"]["fit"]["slope"] == pytest.approx(np.polyfit(fossil_1850 / 1e6, temp, 1)[0], **tol)  # 1750-based cumulative: same slope
    for sens in out["headline"]["land_use_sensitivity"]:
        sc = sens["land_use_scale"]
        assert sens["slope"] == pytest.approx(np.polyfit((fossil_1850 + sc * luc) / 1e6, temp, 1)[0], **tol)
    assert [s["land_use_scale"] for s in out["headline"]["land_use_sensitivity"]] == [0.7, 1.0, 1.3]
    assert out["headline"]["land_use_sensitivity"][1]["slope"] == pytest.approx(out["headline"]["fit"]["slope"], **tol)
    w1970 = [w for w in out["headline"]["windows"] if w["start"] == 1970][0]
    assert w1970["slope"] == pytest.approx(np.polyfit(total[yrs >= 1970] / 1e6, temp[yrs >= 1970], 1)[0], **tol)


def test_vintage_caveat_carries_the_file_date_until_the_owner_records_a_reconciliation(tmp_path):
    rep, out = stage(tmp_path)
    v = out["temperature_source_vintage"]
    assert v["file_last_modified"] == "2025-01-10T04:48:46+00:00" and v["reconciled"] is False
    assert v["caveat"] == ("Based on Berkeley Earth file vintage 2025-01-10; a possible ~0.1 °C discrepancy with Berkeley Earth's most recent published report text "
                           "has not yet been reconciled.")
    assert v["caveat"] in out["caveats"] and any("vintage caveat" in n for n in rep.notes)
    _, out2 = stage(tmp_path / "r", notices={"berkeley_earth": {"vintage_reconciled": True}}) if (tmp_path / "r").mkdir() is None else (None, None)
    assert out2["temperature_source_vintage"]["reconciled"] is True and out2["temperature_source_vintage"]["caveat"] is None
    assert not any("vintage" in c for c in out2["caveats"])


def test_unknown_vintage_date_is_stated_not_invented(tmp_path):
    _, out = stage(tmp_path, vintage=None)
    assert "an unknown date" in out["temperature_source_vintage"]["caveat"]


def test_mandatory_caveats_and_attribution_travel_with_the_output(tmp_path):
    _, out = stage(tmp_path)
    c = " ".join(out["caveats"])
    assert "not a complete climate model" in c and "absorbs warming from non-CO2 gases and aerosols" in c and "0.27-0.63" in c
    assert "international aviation and shipping" in c and "sum of national emissions" in c  # the denominator difference (decision 15)
    assert "No formal license (e.g., CC BY) is stated" in c and "+/-0.7 GtC/yr" in c
    a = out["attribution"]
    assert a["attribution_required"] is True and a["required_citation_format"].startswith("Global Carbon Project") and a["citations"] == ["OWID", "GCP"]
    assert "not proof of causation" in out["note"] and out["definition"] == "total anthropogenic CO2 since 1850"
    assert set(out["inputs"]) == {"temperature_anomaly_1850_1900_c", "owid_total_co2_world_cumulative_mt", "owid_co2_world_cumulative_mt", "owid_luc_co2_world_cumulative_mt"}


def drop_columns(*cols):
    def edit(d):
        p = os.path.join(d, "owid_world_co2_annual.csv")
        pd.read_csv(p).drop(columns=list(cols)).to_csv(p, index=False)
    return edit


METADATA_KEYS = {"schema_version", "generated_at", "note", "ar6_reference", "method", "methodology", "definition", "temperature_source_vintage", "attribution", "caveats", "inputs"}


def assert_full_metadata(out):
    """Every output, available or not, carries the contract's metadata (decision 39): the vintage and licence caveats most of all."""
    assert METADATA_KEYS <= set(out)
    c = " ".join(out["caveats"])
    assert "not a complete climate model" in c and "No formal license (e.g., CC BY) is stated" in c and "+/-0.7 GtC/yr" in c and "international aviation and shipping" in c
    assert out["temperature_source_vintage"]["caveat"] in out["caveats"] and out["attribution"]["attribution_required"] is True
    assert out["ar6_reference"]["best_estimate"] == 0.45 and out["definition"] == "total anthropogenic CO2 since 1850"


def test_headline_inputs_missing_leaves_the_independent_fossil_variant_published(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_columns("total_co2_incl_luc_mt", "land_use_change_co2_mt"))
    assert out["headline"] is None and "owid_total_co2_world_cumulative_mt" in out["headline_unavailable_reason"] and "owid_luc_co2_world_cumulative_mt" in out["headline_unavailable_reason"]
    assert out["secondary_fossil_only"]["fit"]["slope"] > 0 and "secondary_fossil_only_unavailable_reason" not in out  # it needs neither land-use input
    assert [d for d in rep.deviations if "regression unavailable" in d] == [f"headline regression unavailable: {out['headline_unavailable_reason']}"]
    assert rep.records["correlation_headline"] == 1 and out["inputs"]["owid_total_co2_world_cumulative_mt"] == {"available": False} and out["inputs"]["owid_co2_world_cumulative_mt"]["available"] is True
    assert_full_metadata(out)


def test_fossil_input_missing_leaves_the_headline_published(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_columns("cumulative_co2_mt"))
    assert out["secondary_fossil_only"] is None and "owid_co2_world_cumulative_mt" in out["secondary_fossil_only_unavailable_reason"]
    assert out["headline"]["fit"]["slope"] > 0 and "headline_unavailable_reason" not in out
    assert_full_metadata(out)


def test_unavailable_results_still_carry_the_full_metadata_contract(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_columns("total_co2_incl_luc_mt", "land_use_change_co2_mt", "cumulative_co2_mt"))
    assert out["headline"] is None and out["secondary_fossil_only"] is None and rep.records["correlation_headline"] == 0
    assert_full_metadata(out)
    assert "Based on Berkeley Earth file vintage 2025-01-10" in out["temperature_source_vintage"]["caveat"]  # the vintage survives: it needs only provenance.json


def test_a_missing_catalog_overwrites_the_previous_output_with_explicit_nulls_and_does_not_raise(tmp_path):
    _, good = stage(tmp_path)
    assert good["headline"] is not None
    os.remove(tmp_path / "indicator_catalog.json")
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and out["secondary_fossil_only"] is None  # the stale regression is not left in place as current
    assert "harmonized layer unavailable" in out["headline_unavailable_reason"] and "FileNotFoundError" in out["headline_unavailable_reason"]
    assert len([d for d in rep.deviations if "regression unavailable" in d]) == 2 and all(v == {"available": False} for v in out["inputs"].values())
    assert_full_metadata(out)


def test_a_pairing_that_is_refused_becomes_a_reason_not_a_crash(tmp_path):
    def keep_ten_temperature_years(d):
        p = os.path.join(d, "temperature_anomaly_annual.csv")
        df = pd.read_csv(p)
        df[df.year >= 2015].to_csv(p, index=False)  # 10 shared years: below the pairing's min_overlap

    rep, out = stage(tmp_path, edit_inputs=keep_ten_temperature_years)
    assert out["headline"] is None and out["secondary_fossil_only"] is None
    assert "pairing refused" in out["headline_unavailable_reason"] and "at least 20 are required" in out["headline_unavailable_reason"]
    assert_full_metadata(out)


def test_a_non_positive_slope_is_flagged_before_publishing(tmp_path):
    def reverse_temperature(d):
        p = os.path.join(d, "temperature_anomaly_annual.csv")
        df = pd.read_csv(p)
        df.assign(anomaly_1850_1900_c=df["anomaly_1850_1900_c"].to_numpy()[::-1]).to_csv(p, index=False)

    rep, out = stage(tmp_path, edit_inputs=reverse_temperature)
    assert any("not positive" in d for d in rep.deviations) and out["headline"]["fit"]["slope"] < 0


def test_the_stage_is_deterministic(tmp_path):
    _, a = stage(tmp_path)
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "none.json"))
    b = json.loads((tmp_path / "correlation_headline.json").read_text())
    for d in (a, b):
        d.pop("generated_at")
    assert a == b  # no random draw anywhere: the bootstrap of Phase 1.3b is seeded, this stage has none


def test_the_stage_is_registered_after_harmonize_in_the_run_order():
    from pipeline import run

    order = list(run.DERIVED_SOURCES)
    assert order.index("correlate") > order.index("harmonize") and "correlate" not in run.ACTIVE_SOURCES


# ---------------------------------------------------------------- malformed harmonized tables (Copilot review on #212)


def test_a_harmonized_table_missing_a_required_column_is_a_clear_load_error(tmp_path):
    from pipeline.pairing import load_harmonized

    stage(tmp_path)
    p = tmp_path / "harmonized_global_annual.csv"
    pd.read_csv(p).drop(columns=["value"]).to_csv(p, index=False)
    with pytest.raises(ValueError, match=r"harmonized_global_annual.csv: required column\(s\) missing: value"):
        load_harmonized(str(tmp_path))
    q = tmp_path / "harmonized_country_annual.csv"
    pd.read_csv(q).drop(columns=["iso3"]).to_csv(q, index=False)
    p.write_text(pd.read_csv(tmp_path / "harmonized_global_annual.csv").assign(value=1.0).to_csv(index=False))
    with pytest.raises(ValueError, match=r"harmonized_country_annual.csv: required column\(s\) missing: iso3"):
        load_harmonized(str(tmp_path))


def test_a_malformed_table_overwrites_the_stale_output_with_nulls_and_does_not_raise(tmp_path):
    _, good = stage(tmp_path)
    assert good["headline"] is not None
    p = tmp_path / "harmonized_global_annual.csv"
    pd.read_csv(p).drop(columns=["year"]).to_csv(p, index=False)
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise a KeyError
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and out["secondary_fossil_only"] is None
    assert "required column(s) missing: year" in out["headline_unavailable_reason"] and len([d for d in rep.deviations if "regression unavailable" in d]) == 2
    assert_full_metadata(out)


def test_a_key_error_inside_a_variant_becomes_a_reason_too(tmp_path, monkeypatch):
    """Belt and braces: a column problem that slips past the load check is still a per-variant reason, not an escaped exception."""
    from pipeline import pairing

    _, _ = stage(tmp_path)

    def boom(*a, **k):
        raise KeyError("value")

    monkeypatch.setattr(C, "align_pair", boom)
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and "pairing refused" in out["headline_unavailable_reason"] and len(rep.deviations) == 2


# ---------------------------------------------------------------- degenerate predictor, malformed catalog entries, last-resort handling (Copilot review #3 on #212)


def test_a_constant_predictor_is_a_clear_error_not_an_index_error():
    with pytest.raises(ValueError, match="no variation over the paired years"):
        C.fit_line(np.full(50, 5.0e5), np.linspace(0, 1, 50), 4)
    with pytest.raises(ValueError, match="non-finite"):
        C.fit_line(np.array([1.0, 2.0, np.nan] * 10), np.linspace(0, 1, 30), 4)


def test_the_intercept_is_always_added(tmp_path):
    x_mt = np.linspace(1e4, 2e6, 60)
    f = C.fit_line(x_mt, 3.0 + 0.4 * x_mt / 1e6, 4)
    assert f["intercept"] == pytest.approx(3.0, abs=1e-9) and f["slope"] == pytest.approx(0.4, abs=1e-12)


def test_a_degenerate_predictor_makes_only_that_variant_unavailable(tmp_path):
    def constant_fossil_cumulative(d):
        p = os.path.join(d, "owid_world_co2_annual.csv")
        df = pd.read_csv(p)
        df.assign(cumulative_co2_mt=5.0).to_csv(p, index=False)

    rep, out = stage(tmp_path, edit_inputs=constant_fossil_cumulative)
    assert out["secondary_fossil_only"] is None and "no variation" in out["secondary_fossil_only_unavailable_reason"]
    assert out["headline"]["fit"]["slope"] > 0 and any("secondary_fossil_only regression unavailable" in d for d in rep.deviations)
    assert_full_metadata(out)


def mangle_catalog(tmp_path, fn):
    p = tmp_path / "indicator_catalog.json"
    doc = json.loads(p.read_text())
    fn(doc)
    p.write_text(json.dumps(doc))


@pytest.mark.parametrize("field", ["name", "unit", "kind", "scope", "id"])
def test_a_catalog_entry_missing_a_required_field_is_a_clear_load_error(tmp_path, field):
    from pipeline.pairing import load_harmonized

    stage(tmp_path)
    mangle_catalog(tmp_path, lambda d: d["indicators"][3].pop(field))
    with pytest.raises(ValueError, match=rf"1 malformed indicator entry; first: .* \(missing {field}\)"):
        load_harmonized(str(tmp_path))


def test_a_malformed_catalog_overwrites_the_stale_output_with_nulls_and_does_not_raise(tmp_path):
    _, good = stage(tmp_path)
    assert good["headline"] is not None
    mangle_catalog(tmp_path, lambda d: [e for e in d["indicators"] if e["id"] == "owid_co2_world_cumulative_mt"][0].pop("name"))
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise a KeyError
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and out["secondary_fossil_only"] is None
    assert "malformed indicator entry" in out["headline_unavailable_reason"] and "owid_co2_world_cumulative_mt" in out["headline_unavailable_reason"]
    assert_full_metadata(out)


@pytest.mark.parametrize("doc", [[1, 2, 3], {"schema_version": 1, "indicators": "nope"}, {"schema_version": 1, "indicators": [7]}])
def test_catalog_json_of_the_wrong_shape_is_handled_not_raised(tmp_path, doc):
    stage(tmp_path)
    (tmp_path / "indicator_catalog.json").write_text(json.dumps(doc))
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and out["secondary_fossil_only"] is None and len(rep.deviations) == 2
    assert_full_metadata(out)


def test_an_unexpected_exception_in_a_variant_still_rewrites_the_output_with_nulls(tmp_path, monkeypatch, caplog):
    _, good = stage(tmp_path)
    monkeypatch.setattr(C, "fit_line", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level("ERROR"):
        rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and "unexpected error: RuntimeError: boom" in out["headline_unavailable_reason"] and len(rep.deviations) == 2
    assert any("unexpected error computing" in r.message for r in caplog.records)  # the traceback is logged, not swallowed silently
    assert_full_metadata(out)
