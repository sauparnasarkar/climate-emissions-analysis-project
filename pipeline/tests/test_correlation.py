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
    assert len([d for d in rep.deviations if "regression unavailable" in d]) == 3  # two headline variants + all-gas and all(v == {"available": False} for v in out["inputs"].values())
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
    assert "required column(s) missing: year" in out["headline_unavailable_reason"] and len([d for d in rep.deviations if "regression unavailable" in d]) == 3  # two headline variants + all-gas
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
    assert out["headline"] is None and "pairing refused" in out["headline_unavailable_reason"] and len(rep.deviations) == 3  # the two headline variants and the all-gas view


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
    assert out["headline"] is None and out["secondary_fossil_only"] is None and len(rep.deviations) == 3  # the two headline variants and the all-gas view
    assert_full_metadata(out)


def test_an_unexpected_exception_in_a_variant_still_rewrites_the_output_with_nulls(tmp_path, monkeypatch, caplog):
    _, good = stage(tmp_path)
    monkeypatch.setattr(C, "fit_line", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level("ERROR"):
        rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise
    out = json.loads((tmp_path / "correlation_headline.json").read_text())
    assert out["headline"] is None and "unexpected error: RuntimeError: boom" in out["headline_unavailable_reason"] and len(rep.deviations) == 3  # the two headline variants and the all-gas view
    assert any("unexpected error computing" in r.message for r in caplog.records)  # the traceback is logged, not swallowed silently
    assert_full_metadata(out)


@pytest.mark.parametrize(
    "metadata_file,contents,reason,attribution_available",
    [
        ("provenance.json", "{", "attribution metadata", False),
        ("notices.json", "{", "temperature vintage metadata", True),
    ],
)
def test_malformed_metadata_rewrites_stale_output_with_nulls_and_a_deviation(
    tmp_path, metadata_file, contents, reason, attribution_available
):
    _, good = stage(tmp_path)
    assert good["headline"] is not None and good["secondary_fossil_only"] is not None
    (tmp_path / metadata_file).write_text(contents)

    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))
    out = json.loads((tmp_path / "correlation_headline.json").read_text())

    assert out["headline"] is None and out["secondary_fossil_only"] is None
    assert reason in out["headline_unavailable_reason"]
    assert any("correlation metadata unavailable" in d for d in rep.deviations)
    assert out["temperature_source_vintage"]["caveat"] in out["caveats"]
    assert bool(out["attribution"]) is attribution_available
    assert METADATA_KEYS <= set(out)


# ---------------------------------------------------------------- stability: seeded residual block bootstrap and decade holdouts (Phase 1.3b)


def test_bootstrap_of_noise_free_data_has_no_spread():
    x_mt = np.linspace(1e4, 2.5e6, 100)
    s = C.bootstrap_slopes(x_mt, 0.2 + 0.5 * x_mt / 1e6, 10, 300, np.random.default_rng(1))
    assert np.allclose(s, 0.5, atol=1e-12) and len(s) == 300  # zero residuals: every resample has the fitted slope


@pytest.mark.parametrize("block", [1, 5, 10, 30])
def test_vectorized_bootstrap_equals_a_slow_reference_built_from_the_same_draws(block):
    x_mt, y = ar1_data(n=80, seed=3)
    B = 50
    fast = C.bootstrap_slopes(x_mt, y, block, B, np.random.default_rng(99))
    x = x_mt / 1e6
    slope, intercept = np.polyfit(x, y, 1)
    fitted, resid = intercept + slope * x, y - (intercept + slope * x)
    n, nb = len(x), -(-len(x) // block)
    starts = np.random.default_rng(99).integers(0, n - block + 1, size=(B, nb))  # the same draws, then built the slow way
    slow = []
    for row in starts:
        e = np.concatenate([resid[s:s + block] for s in row])[:n]
        slow.append(np.polyfit(x, fitted + e, 1)[0])
    assert np.allclose(fast, slow, rtol=1e-9, atol=1e-12)


def test_bootstrap_block_length_must_fit_the_series():
    x_mt, y = ar1_data(n=40)
    for bad in (0, 41, -3):
        with pytest.raises(ValueError, match="block length"):
            C.bootstrap_slopes(x_mt, y, bad, 10, np.random.default_rng(0))


def test_bootstrap_is_reproducible_and_the_seed_matters():
    x_mt, y = ar1_data()
    a, b = C._bootstrap_block(x_mt, y, 10), C._bootstrap_block(x_mt, y, 10)
    assert a == b  # fixed seed: identical to the last digit, every run
    assert C._bootstrap_block(x_mt, y, 10, seed=1) != a and C._bootstrap_block(x_mt, y, 10, seed=1) == C._bootstrap_block(x_mt, y, 10, seed=1)
    assert C._bootstrap_block(x_mt, y, 5) != a  # a different block length is a different (and itself reproducible) result
    assert C._bootstrap_block(x_mt, y, 5) == C._bootstrap_block(x_mt, y, 5) and C._bootstrap_block(x_mt, y, 10) == a  # computing one length never disturbs another


def test_bootstrap_interval_covers_a_known_slope_at_close_to_the_nominal_rate():
    """60 simulated datasets with AR(1) residuals and a true slope of 0.5; deterministic (fixed seeds). Measured 0.92 against the nominal 0.95."""
    hit = 0
    for r in range(60):
        x_mt, y = ar1_data(rho=0.55, seed=1000 + r)
        lo, hi = C._bootstrap_block(x_mt, y, 10, seed=r, resamples=1000)["ci95"]
        hit += lo <= 0.5 <= hi
    assert hit / 60 >= 0.85


def test_bootstrap_is_wider_than_plain_ols_when_residuals_are_autocorrelated():
    x_mt, y = ar1_data(rho=0.7)
    f = C.fit_line(x_mt, y, 8)
    lo, hi = C._bootstrap_block(x_mt, y, 10)["ci95"]
    assert (hi - lo) > 2 * 1.96 * f["se_ols"] and lo < f["slope"] < hi


def holdout_frame():
    years = np.arange(1850, 2025)
    x = np.cumsum(np.linspace(1e3, 4e4, len(years)))
    rng = np.random.default_rng(5)
    y = 0.1 + 0.6 * x / 1e6 + rng.normal(0, 0.1, len(years))
    return pd.DataFrame({"year": years, "x": x, C.TEMPERATURE: y})


def test_holdout_matches_an_independent_calculation():
    f = holdout_frame()
    h = C.holdout(f, "x", 2000)
    tr, te = f[f.year < 2000], f[f.year >= 2000]
    slope, intercept = np.polyfit(tr.x / 1e6, tr[C.TEMPERATURE], 1)
    err = te[C.TEMPERATURE].to_numpy() - (intercept + slope * te.x.to_numpy() / 1e6)
    assert h["train_slope"] == pytest.approx(slope, rel=1e-10) and h["rmse_c"] == pytest.approx(np.sqrt(np.mean(err**2)), rel=1e-10)
    assert h["mae_c"] == pytest.approx(np.mean(abs(err)), rel=1e-10) and h["mean_error_c"] == pytest.approx(np.mean(err), rel=1e-10)
    assert h["baseline_rmse_train_mean_c"] == pytest.approx(np.sqrt(np.mean((te[C.TEMPERATURE] - tr[C.TEMPERATURE].mean()) ** 2)), rel=1e-10)
    assert (h["n_train"], h["n_test"], h["train_range"], h["test_range"]) == (150, 25, [1850, 1999], [2000, 2024])


def test_a_holdout_that_is_too_small_is_marked_unavailable_with_the_reason():
    f = holdout_frame()
    assert "unavailable" in C.holdout(f, "x", 1860) and "at least 20 training" in C.holdout(f, "x", 1860)["unavailable"]  # 10 training years
    h = C.holdout(f, "x", 2022)
    assert "unavailable" in h and h["n_test"] == 3 and "rmse_c" not in h
    assert "rmse_c" in C.holdout(f, "x", 1870)  # exactly 20 training years is enough


def test_stability_block_structure_seed_and_decade_splits(tmp_path):
    _, out = stage(tmp_path)
    for key in ("headline", "secondary_fossil_only"):
        s = out[key]["stability"]
        assert s["seed"] == 20261002 and s["resamples"] == 2000 and s["primary_block_years"] == 10
        assert [b["block_years"] for b in s["block_length_sensitivity"]] == [5, 10, 20, 30] and s["bootstrap"] == s["block_length_sensitivity"][1]
        assert [h["split_year"] for h in s["holdouts"]] == [1980, 1990, 2000, 2010] and all("rmse_c" in h for h in s["holdouts"])
        assert s["hac_ci95"] == out[key]["fit"]["ci95_hac"] and s["bootstrap_vs_hac_width_ratio"] > 0
        lo, hi = s["bootstrap"]["ci95"]
        assert lo <= out[key]["fit"]["slope"] <= hi  # the bootstrap is centred on the fitted slope
    assert "distinct from the HAC" in out["headline"]["stability"]["method"]


def test_stability_summary_states_the_numbers_and_makes_no_pass_fail_claim(tmp_path):
    _, out = stage(tmp_path)
    s = out["headline"]["stability"]
    lo, hi = s["bootstrap"]["ci95"]
    text = s["summary"]
    assert f"{lo:.3f} to {hi:.3f}" in text and "seed 20261002" in text and "2,000 resamples" in text and "10-year blocks" in text
    assert f"{s['hac_ci95'][0]:.3f} to {s['hac_ci95'][1]:.3f}" in text and "out-of-sample error (RMSE)" in text and "before 2000" in text
    ho = [h for h in s["holdouts"] if h["split_year"] == 2000][0]
    assert f"{ho['rmse_c']:.3f} °C" in text and f"{ho['train_slope']:.3f}" in text
    low = (text + s["note"]).lower()
    assert not any(w in low for w in ("passes", "passed", "fails", "failed", "robust", "reliable", "validated")) and "no pass/fail judgement" in s["note"]


def test_the_stage_output_including_the_bootstrap_is_identical_run_to_run(tmp_path):
    _, a = stage(tmp_path)
    C.run(str(tmp_path), notices_path=str(tmp_path / "none.json"))
    b = json.loads((tmp_path / "correlation_headline.json").read_text())
    for d in (a, b):
        d.pop("generated_at")
    assert a == b and a["headline"]["stability"] == b["headline"]["stability"]


def test_a_bootstrap_interval_that_misses_the_fitted_slope_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_bootstrap_block", lambda x, y, block, **k: {"block_years": block, "ci95": [9.0, 10.0], "median": 9.5})
    rep, out = stage(tmp_path)
    assert any("the bootstrap interval does not bracket the fitted slope" in d for d in rep.deviations)


# ---------------------------------------------------------------- calendar gaps (Copilot review on #213)


def gappy_years(drop):
    return np.array([y for y in range(1850, 2025) if y not in set(drop)])


@pytest.mark.parametrize("block", [5, 10, 20])
def test_blocks_never_span_a_calendar_gap(block):
    years = gappy_years(range(1900, 1915))  # a 15-year hole
    idx = C.block_indices(years, len(years), block, 2000, np.random.default_rng(3))
    assert idx.shape == (2000, len(years))
    full = (len(years) // block) * block  # the final block is trimmed to n, so check the complete ones
    for row in idx[:, :full].reshape(2000, -1, block):
        assert np.all(np.diff(years[row], axis=1) == 1)  # every block is calendar-consecutive


def test_without_gaps_the_draws_are_identical_to_an_unconstrained_bootstrap():
    n, block = 120, 10
    constrained = C.block_indices(np.arange(1850, 1850 + n), n, block, 500, np.random.default_rng(11))
    unconstrained = C.block_indices(None, n, block, 500, np.random.default_rng(11))
    assert np.array_equal(constrained, unconstrained)  # so seeded results do not change for gap-free data


def test_a_block_length_with_no_consecutive_run_is_refused_with_the_reason():
    years = gappy_years(range(1857, 2025, 8))  # runs of 7 consecutive years
    with pytest.raises(ValueError, match="no run of 10 consecutive calendar years"):
        C.block_indices(years, len(years), 10, 10, np.random.default_rng(0))
    assert C.block_indices(years, len(years), 5, 10, np.random.default_rng(0)).shape == (10, len(years))  # 5-year blocks still fit


def test_gappy_data_gives_a_different_interval_than_ignoring_the_gap():
    years = gappy_years(range(1900, 1915))
    x_mt, y = ar1_data(n=len(years), seed=21)
    aware = C._bootstrap_block(x_mt, y, 10, years=years)
    naive = C._bootstrap_block(x_mt, y, 10)
    assert aware != naive and aware["ci95"][0] <= np.polyfit(x_mt / 1e6, y, 1)[0] <= aware["ci95"][1]


def drop_temperature_years(drop):
    def edit(d):
        p = os.path.join(d, "temperature_anomaly_annual.csv")
        df = pd.read_csv(p)
        df[~df.year.isin(list(drop))].to_csv(p, index=False)
    return edit


def test_a_gap_in_the_paired_years_is_flagged_and_the_stability_block_still_forms(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_temperature_years(range(1900, 1905)))
    h = out["headline"]
    assert h["contiguous"] is False and h["n_years"] == 170 and [o["year"] for o in h["omitted_years"]] == list(range(1900, 1905))
    assert any("5 calendar-year gap(s)" in d and "Newey-West lags count rows" in d for d in rep.deviations)
    s = h["stability"]
    assert s["bootstrap"]["block_years"] == 10 and s["block_length_unavailable"] == [] and s["bootstrap"]["ci95"][0] <= h["fit"]["slope"] <= s["bootstrap"]["ci95"][1]


def test_gap_free_data_is_contiguous_with_no_deviation_and_nothing_unavailable(tmp_path):
    rep, out = stage(tmp_path)
    assert out["headline"]["contiguous"] is True and out["headline"]["stability"]["block_length_unavailable"] == []
    assert not any("calendar-year gap" in d for d in rep.deviations)


def test_long_block_lengths_that_the_data_cannot_support_are_listed_not_hidden(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_temperature_years(range(1874, 2025, 25)))  # runs of 24 consecutive years
    s = out["headline"]["stability"]
    assert [b["block_years"] for b in s["block_length_sensitivity"]] == [5, 10, 20]
    assert [u["block_years"] for u in s["block_length_unavailable"]] == [30] and "no run of 30 consecutive calendar years" in s["block_length_unavailable"][0]["reason"]
    assert "5 to 20 years" in s["summary"]


def test_a_missing_primary_block_length_makes_the_variant_unavailable_with_the_reason(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_temperature_years(range(1857, 2025, 8)))  # runs of 7: the 10-year primary cannot be formed
    assert out["headline"] is None and "no run of 10 consecutive calendar years" in out["headline_unavailable_reason"]
    assert out["secondary_fossil_only"] is None and any("regression unavailable" in d for d in rep.deviations)


# ---------------------------------------------------------------- the land-use trade-off copy and weight scan (decisions 41-42)


def variant(rmse, r2, test_range=(2000, 2024)):
    """The minimum a variant block needs for fit_quality_note."""
    return {"fit": {"r_squared": r2}, "stability": {"holdouts": [
        {"split_year": 1990, "rmse_c": 9.9, "test_range": [1990, 2024]},
        {"split_year": 2000, "rmse_c": rmse, "test_range": list(test_range)}]}}


def test_copy_when_the_headline_error_is_larger_and_in_sample_fits_agree_matches_decision_41_exactly():
    n = C.fit_quality_note(variant(0.1744, 0.9033), variant(0.1262, 0.9094))
    assert n["text"] == ("Including land-use emissions aligns this estimate with the IPCC's own TCRE definition. Land-use CO₂ is estimated with more uncertainty than "
                         "fossil-fuel emissions, and in an out-of-sample test this headline predicted recent temperatures with a larger error than the fossil-only variant "
                         "(0.17 vs 0.13 °C for 2000-2024). The data cannot say whether that reflects land-use measurement uncertainty or something else. In-sample, both "
                         "variants fit the historical record almost identically (R² 0.903 vs 0.909); the difference appears specifically in out-of-sample prediction.")
    assert (n["out_of_sample_error"], n["in_sample_fit_similar"], n["split_year"], n["test_range"]) == ("larger", True, 2000, [2000, 2024])
    assert n["headline_rmse_c"] == 0.1744 and n["fossil_only_rmse_c"] == 0.1262  # full precision kept beside the rounded text


def test_copy_never_asserts_a_cause_or_softens_a_large_gap():
    text = C.fit_quality_note(variant(0.229, 0.903), variant(0.150, 0.909))["text"]
    low = text.lower()
    assert "which results in" not in low and "because" not in low and "modestly" not in low
    assert "cannot say whether" in low and "0.23 vs 0.15" in text


@pytest.mark.parametrize("h,f,relation,phrase,has_cannot_say", [
    (0.200, 0.126, "larger", "a larger error than the fossil-only variant", True),
    (0.100, 0.126, "smaller", "a smaller error than the fossil-only variant", False),
    (0.130, 0.126, "similar", "a similar error to the fossil-only variant", False),
    (0.126 * 1.10, 0.126, "similar", "a similar error to", False),  # exactly on the threshold is still similar
])
def test_copy_follows_what_the_numbers_show(h, f, relation, phrase, has_cannot_say):
    n = C.fit_quality_note(variant(h, 0.903), variant(f, 0.909))
    assert n["out_of_sample_error"] == relation and phrase in n["text"] and ("cannot say whether" in n["text"]) is has_cannot_say
    assert ("the difference appears specifically in out-of-sample prediction" in n["text"]) is (relation != "similar")  # only claimed when there is a difference


def test_in_sample_sentence_is_conditional_on_the_fits_actually_agreeing():
    agree = C.fit_quality_note(variant(0.2, 0.903), variant(0.126, 0.909))["text"]
    differ = C.fit_quality_note(variant(0.2, 0.80), variant(0.126, 0.909))
    assert "almost identically (R² 0.903 vs 0.909)" in agree
    assert differ["in_sample_fit_similar"] is False and "almost identically" not in differ["text"] and "In-sample fit differs as well (R² 0.800 vs 0.909)." in differ["text"]
    assert "specifically in out-of-sample" not in differ["text"]


def test_copy_is_unavailable_when_either_variant_has_no_usable_holdout():
    no_ref = {"fit": {"r_squared": 0.9}, "stability": {"holdouts": [{"split_year": 2000, "unavailable": "needs more years"}]}}
    assert C.fit_quality_note(no_ref, variant(0.1, 0.9)) is None and C.fit_quality_note(variant(0.1, 0.9), no_ref) is None


def test_the_stage_output_carries_the_note_with_the_same_numbers_as_the_holdouts_and_fits(tmp_path):
    _, out = stage(tmp_path)
    n = out["headline"]["fit_quality_note"]
    ho = lambda b: [h for h in out[b]["stability"]["holdouts"] if h["split_year"] == 2000][0]
    assert n["headline_rmse_c"] == ho("headline")["rmse_c"] and n["fossil_only_rmse_c"] == ho("secondary_fossil_only")["rmse_c"]
    assert n["headline_r_squared"] == out["headline"]["fit"]["r_squared"] and n["fossil_only_r_squared"] == out["secondary_fossil_only"]["fit"]["r_squared"]
    assert f"{n['headline_rmse_c']:.2f} vs {n['fossil_only_rmse_c']:.2f} °C for 2000-2024" in n["text"] and "fit_quality_note" not in out["secondary_fossil_only"]


def test_without_the_fossil_variant_the_note_is_null_with_a_reason_and_the_headline_survives(tmp_path):
    rep, out = stage(tmp_path, edit_inputs=drop_columns("cumulative_co2_mt"))
    assert out["headline"] is not None and out["headline"]["fit_quality_note"] is None
    assert out["headline"]["fit_quality_note_unavailable_reason"] == "the fossil-only variant is unavailable"


def test_weight_scan_endpoints_equal_the_two_variants_and_the_middle_matches_an_independent_fit(tmp_path):
    _, out = stage(tmp_path)
    scan = out["headline"]["land_use_weight_scan"]
    assert [w["land_use_weight"] for w in scan["weights"]] == [0.0, 0.25, 0.5, 0.7, 1.0, 1.3] and "not to choose a weight" in scan["note"]
    by = {w["land_use_weight"]: w for w in scan["weights"]}
    ho = lambda b: [h for h in out[b]["stability"]["holdouts"] if h["split_year"] == 2000][0]
    assert by[1.0]["holdout_rmse_c"] == pytest.approx(ho("headline")["rmse_c"], rel=1e-9) and by[1.0]["slope"] == pytest.approx(out["headline"]["fit"]["slope"], rel=1e-9)
    assert by[0.0]["holdout_rmse_c"] == pytest.approx(ho("secondary_fossil_only")["rmse_c"], rel=1e-6)  # weight 0 IS the fossil-only variant (slope is start-invariant)
    assert by[0.0]["slope"] == pytest.approx(out["secondary_fossil_only"]["fit"]["slope"], rel=1e-6)
    # the land-use sensitivity published since 1.3a is the same fit at scales 0.7 / 1.0 / 1.3
    for s in out["headline"]["land_use_sensitivity"]:
        assert by[s["land_use_scale"]]["slope"] == pytest.approx(s["slope"], rel=1e-9)
    # an independent calculation at weight 0.5 from the synthetic series definitions
    yrs = np.arange(1850, 2025)
    fossil = np.cumsum([10.0 * (y - 1749) for y in yrs]); luc = np.cumsum([3.0 * (y - 1849) for y in yrs]); temp = np.linspace(-0.13, 1.6, 175)
    x = (fossil + 0.5 * luc) / 1e6; tr = yrs < 2000
    b, a = np.polyfit(x[tr], temp[tr], 1)
    rmse = np.sqrt(np.mean((temp[~tr] - (a + b * x[~tr])) ** 2))
    assert by[0.5]["holdout_rmse_c"] == pytest.approx(rmse, rel=1e-5) and by[0.5]["holdout_train_slope"] == pytest.approx(b, rel=1e-5)


def test_the_fossil_only_variant_has_no_weight_scan_or_note(tmp_path):
    _, out = stage(tmp_path)
    assert "land_use_weight_scan" not in out["secondary_fossil_only"] and "fit_quality_note" not in out["secondary_fossil_only"]


# ---------------------------------------------------------------- the recent all-gas relationship (Phase 1.3c-i; decision 35)


def read_all_gas(tmp_path):
    return json.loads((tmp_path / "correlation_all_gas.json").read_text())


def drop_primap_total(d):
    p = os.path.join(d, "primap_global_composition_annual.csv")
    pd.read_csv(p).drop(columns=["total_ghg_mtco2e"]).to_csv(p, index=False)


def test_all_gas_is_a_separate_output_and_the_two_files_do_not_mix(tmp_path):
    _, head = stage(tmp_path)
    ag = read_all_gas(tmp_path)
    assert "recent_all_gas" not in head and "recent_all_gas" in ag and "headline" not in ag and "secondary_fossil_only" not in ag
    assert ag["name"] == "Recent all-gas relationship" and ag["definition"] == "cumulative PRIMAP-hist total greenhouse gases (CO2-equivalent) from 1970"


def test_all_gas_slope_equals_an_independent_fit_of_the_synthetic_series_and_ignores_the_cumulative_start(tmp_path):
    stage(tmp_path)
    g = read_all_gas(tmp_path)["recent_all_gas"]
    yrs = np.arange(1970, 2025)
    temp = np.linspace(-0.13, 1.6, 175)[yrs - 1850]
    from_1970 = np.cumsum([100.0 * (y - 1749) for y in yrs])  # cumulative from 1970, as decision 35 describes
    from_1750 = np.cumsum([100.0 * (y - 1749) for y in range(1750, 2025)])[yrs - 1750]  # the harmonized indicator's own start
    s1970, s1750 = np.polyfit(from_1970 / 1e6, temp, 1)[0], np.polyfit(from_1750 / 1e6, temp, 1)[0]
    assert s1970 == pytest.approx(s1750, rel=1e-9)  # the slope does not depend on where the cumulative starts
    assert g["fit"]["slope"] == pytest.approx(s1970, rel=1e-6) and g["range"] == [1970, 2024] and g["n_years"] == 55 and g["fit"]["maxlags"] == 5
    assert g["unit"] == "°C per 1,000 GtCO2e" and g["x_indicator"] == "primap_ghg_total_cumulative_mtco2e"


def test_all_gas_is_never_called_tcre_and_has_no_ipcc_comparison(tmp_path):
    stage(tmp_path)
    ag = read_all_gas(tmp_path)
    assert "tcre" not in json.dumps(ag).lower()  # not in any field name, title, caveat or note (decision 35)
    g = ag["recent_all_gas"]
    assert "vs_ar6" not in g and "slope_per_1000_gtc" not in g["fit"] and "ar6_reference" not in ag and "land_use_sensitivity" not in g and "fit_quality_note" not in g


def test_all_gas_explains_why_it_is_a_different_thing(tmp_path):
    stage(tmp_path)
    ag = read_all_gas(tmp_path)
    c = " ".join(ag["caveats"])
    for phrase in ("CO2, CH4, N2O and F-gases", "AR5 100-year global-warming potentials", "excludes international aviation and shipping and land-use change",
                   "strongly correlated with time", "not comparable with the long-run CO2 relationship", "short-lived gases such as methane do not accumulate",
                   "not a complete climate model"):
        assert phrase in c, phrase
    assert "No trailing years were excluded as incomplete." in c and ag["temperature_source_vintage"]["caveat"] in ag["caveats"]


def test_all_gas_states_the_years_excluded_as_incomplete_from_provenance(tmp_path):
    prov_path = write_inputs(tmp_path)
    prov = json.loads(open(prov_path).read())
    prov["primap_global_composition_annual"].update({"excluded_incomplete_years": [{"year": 2025, "reasons": "ch4 coverage 2.0% < 98%"}], "citations": ["Gütschow & Pflüger (2026)"]})
    open(prov_path, "w").write(json.dumps(prov))
    harmonize.run(str(tmp_path), prov_path)
    C.run(str(tmp_path), notices_path=str(tmp_path / "n.json"))
    ag = read_all_gas(tmp_path)
    assert "Years excluded because PRIMAP-hist's reporting for them is incomplete: 2025." in " ".join(ag["caveats"])
    assert ag["attribution"]["license"] == "CC BY-NC-SA 4.0" and ag["attribution"]["citations"] == ["Gütschow & Pflüger (2026)"] and ag["attribution"]["source"] == "PRIMAP"
    assert "PRIMAP-hist licence: CC BY-NC-SA 4.0" in " ".join(ag["caveats"])  # the non-commercial / share-alike notice travels with the numbers


def test_all_gas_window_holdouts_and_stability_follow_its_short_coverage(tmp_path):
    stage(tmp_path)
    g = read_all_gas(tmp_path)["recent_all_gas"]
    assert [w["start"] for w in g["windows"]] == [1970] and g["windows"][0]["slope"] == pytest.approx(g["fit"]["slope"])  # the grid clipped to 1970+
    ho = {h["split_year"]: h for h in g["stability"]["holdouts"]}
    assert "unavailable" in ho[1980] and ho[1980]["n_train"] == 10  # only 10 training years before 1980
    assert all("rmse_c" in ho[s] for s in (1990, 2000, 2010)) and ho[1990]["n_train"] == 20
    assert g["stability"]["seed"] == 20261002 and [b["block_years"] for b in g["stability"]["block_length_sensitivity"]] == [5, 10, 20, 30]
    lo, hi = g["stability"]["bootstrap"]["ci95"]
    assert lo <= g["fit"]["slope"] <= hi


def test_all_gas_unavailable_leaves_the_headline_untouched_and_is_explicit(tmp_path):
    rep, head = stage(tmp_path, edit_inputs=drop_primap_total)
    ag = read_all_gas(tmp_path)
    assert head["headline"] is not None and head["secondary_fossil_only"] is not None  # independent outputs
    assert ag["recent_all_gas"] is None and "primap_ghg_total_cumulative_mtco2e" in ag["recent_all_gas_unavailable_reason"]
    assert any("recent_all_gas regression unavailable" in d for d in rep.deviations) and rep.records["correlation_all_gas"] == 0
    assert ag["inputs"]["primap_ghg_total_cumulative_mtco2e"] == {"available": False} and ag["caveats"] and ag["temperature_source_vintage"]["caveat"] in ag["caveats"]


def test_all_gas_missing_catalog_overwrites_the_stale_file_with_nulls_and_full_metadata(tmp_path):
    stage(tmp_path)
    assert read_all_gas(tmp_path)["recent_all_gas"] is not None
    os.remove(tmp_path / "indicator_catalog.json")
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "n.json"))
    ag = read_all_gas(tmp_path)
    assert ag["recent_all_gas"] is None and "harmonized layer unavailable" in ag["recent_all_gas_unavailable_reason"] and "FileNotFoundError" in ag["recent_all_gas_unavailable_reason"]
    assert ag["name"] == "Recent all-gas relationship" and any("strongly correlated with time" in c for c in ag["caveats"]) and len(rep.deviations) == 3  # 2 headline variants + all-gas


def test_all_gas_short_overlap_is_a_reason_not_a_crash(tmp_path):
    def keep_ten_years(d):
        p = os.path.join(d, "temperature_anomaly_annual.csv")
        df = pd.read_csv(p)
        df[df.year >= 2015].to_csv(p, index=False)

    rep, _ = stage(tmp_path, edit_inputs=keep_ten_years)
    ag = read_all_gas(tmp_path)
    assert ag["recent_all_gas"] is None and "pairing refused" in ag["recent_all_gas_unavailable_reason"] and "at least 20 are required" in ag["recent_all_gas_unavailable_reason"]


def test_all_gas_non_positive_slope_is_flagged(tmp_path):
    def reverse_temperature(d):
        p = os.path.join(d, "temperature_anomaly_annual.csv")
        df = pd.read_csv(p)
        df.assign(anomaly_1850_1900_c=df["anomaly_1850_1900_c"].to_numpy()[::-1]).to_csv(p, index=False)

    rep, _ = stage(tmp_path, edit_inputs=reverse_temperature)
    assert any(d.startswith("recent_all_gas: slope") and "is not positive" in d for d in rep.deviations)


def test_all_gas_output_is_identical_run_to_run_and_the_stage_reports_it(tmp_path):
    rep, _ = stage(tmp_path)
    a = read_all_gas(tmp_path)
    C.run(str(tmp_path), notices_path=str(tmp_path / "none.json"))
    b = read_all_gas(tmp_path)
    for d in (a, b):
        d.pop("generated_at")
    assert a == b and rep.records["correlation_all_gas"] == 1 and any(n.startswith("recent all-gas relationship") for n in rep.notes)


@pytest.mark.parametrize("metadata_file,contents", [("provenance.json", "{not json"), ("notices.json", "{not json")])
def test_all_gas_malformed_metadata_rewrites_the_stale_output_with_nulls_like_the_headline(tmp_path, metadata_file, contents):
    stage(tmp_path, notices={"berkeley_earth": {}})
    assert read_all_gas(tmp_path)["recent_all_gas"] is not None
    (tmp_path / metadata_file).write_text(contents)
    rep = C.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"))  # must not raise
    ag = read_all_gas(tmp_path)
    assert ag["recent_all_gas"] is None and "correlation metadata unavailable" in ag["recent_all_gas_unavailable_reason"]
    assert any("correlation metadata unavailable" in d for d in rep.deviations)
    assert ag["temperature_source_vintage"]["caveat"] in ag["caveats"] and any("strongly correlated with time" in c for c in ag["caveats"])
    assert {"schema_version", "generated_at", "note", "name", "method", "definition", "temperature_source_vintage", "attribution", "caveats", "inputs"} <= set(ag)
