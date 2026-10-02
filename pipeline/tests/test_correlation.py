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
    assert rep.deviations == [] and rep.records["correlation_headline"] == 1 and out["schema_version"] == 1
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


def test_missing_inputs_give_explicit_nulls_with_a_reason_not_a_crash_or_a_stale_file(tmp_path):
    def remove_luc_columns(d):
        p = os.path.join(d, "owid_world_co2_annual.csv")
        pd.read_csv(p).drop(columns=["total_co2_incl_luc_mt", "land_use_change_co2_mt"]).to_csv(p, index=False)

    rep, out = stage(tmp_path, edit_inputs=remove_luc_columns)
    assert out["headline"] is None and out["secondary_fossil_only"] is None and "owid_total_co2_world_cumulative_mt" in out["unavailable_reason"]
    assert any("headline regression unavailable" in d for d in rep.deviations) and rep.records["correlation_headline"] == 0
    assert out["ar6_reference"]["best_estimate"] == 0.45  # the reference is still published


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
