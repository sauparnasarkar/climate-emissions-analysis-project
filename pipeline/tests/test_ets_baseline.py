import inspect
import json
import os
import warnings

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from pipeline import ets_baseline as E

LAST = 2024
YEARS = list(range(1990, LAST + 1))
COUNTRIES = ["Aland", "Bland", "Cland", "Dland", "Eland", "Fland"]


def make_series(i, spike=None, final_dip=None):
    rng = np.random.default_rng(100 + i)
    level, slope = 200.0 + 150 * i, 1.0 + 0.8 * i
    y = np.array([level + slope * k + rng.normal(0, 4 + i) for k in range(len(YEARS))])
    if spike:
        y[YEARS.index(spike[0])] = spike[1]
    if final_dip:
        y[-1] *= final_dip
    return y


def write(tmp_path, edit=None, countries=COUNTRIES, with_owid=True, with_selected=True, with_world=True, provenance="ok"):
    rows = []
    for i, c in enumerate(countries):
        for y, v in zip(YEARS, make_series(i)):
            rows.append((c, y, v))
    df = pd.DataFrame(rows, columns=["country", "year", "co2"])
    if edit:
        df = edit(df)
    if with_owid:
        df.to_csv(tmp_path / "owid-co2-data.csv", index=False)
    if with_world:
        pd.DataFrame({"year": YEARS, "co2_mt": 1.0}).to_csv(tmp_path / "owid_world_co2_annual.csv", index=False)
    if with_selected:
        (tmp_path / "selected_countries.json").write_text(json.dumps({"expanded": countries}))
    (tmp_path / "provenance.json").write_text("{not json" if provenance == "bad" else json.dumps({"owid_world_co2_annual": {"source": "OWID", "license": "CC BY 4.0", "citations": ["OWID", "GCP"]}}))
    return df


def go(tmp_path, **kw):
    write(tmp_path, **kw)
    rep = E.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"), selected_path=str(tmp_path / "selected_countries.json"))
    return rep, json.loads((tmp_path / "ets_baseline_full_data.json").read_text()), pd.read_csv(tmp_path / "ets_baseline_full_data.csv")


def observed(tmp_path, i):
    """The series exactly as the stage reads it: from the written CSV with the default parser (the one the notebook uses), including whatever edit the test applied."""
    d = pd.read_csv(tmp_path / "owid-co2-data.csv")
    return d[d.country == COUNTRIES[i]].sort_values("year")["co2"].to_numpy()


def direct_forecast(values, steps):
    """An independent call to statsmodels with the specification the stage is documented to use."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # a year-indexed series, exactly as the notebook and the stage pass it (a positional index lands the optimiser at marginally different points)
        r = ExponentialSmoothing(pd.Series(np.asarray(values, dtype=float), index=pd.Index(np.arange(1990, 1990 + len(values)), name="year")), trend="add", damped_trend=True, seasonal=None).fit(optimized=True)
        return np.asarray(r.forecast(steps)), r.params


# ---------------------------------------------------------------- the fit and the output


def test_forecast_equals_an_independent_ets_ad_n_fit_on_every_observed_year(tmp_path):
    _, meta, csv = go(tmp_path)
    steps = E.HORIZON_END - LAST
    for i, c in enumerate(COUNTRIES):
        expected, params = direct_forecast(observed(tmp_path, i), steps)
        got = csv[csv.country == c].sort_values("year")
        assert got.year.tolist() == list(range(LAST + 1, E.HORIZON_END + 1))
        assert got["mean"].to_numpy() == pytest.approx(expected, abs=1e-3)  # the file is rounded to 3 decimals (a rounding of 5e-4 at most)
        assert meta["parameters"][c]["alpha"] == pytest.approx(params["smoothing_level"], abs=1e-12) and meta["parameters"][c]["phi"] == pytest.approx(params["damping_trend"], abs=1e-12)  # same bytes in, same fit out


def test_the_training_window_is_the_whole_record_through_the_last_complete_year(tmp_path):
    _, meta, _ = go(tmp_path)
    assert meta["training_window"] == [1990, LAST] and meta["last_observed_year"] == LAST and meta["forecast_years"] == [LAST + 1, 2043]
    # the last year is used: a different final value must change the forecast
    base = pd.read_csv(tmp_path / "ets_baseline_full_data.csv")
    x = tmp_path / "x"
    x.mkdir()
    _, _, csv2 = go(x, edit=lambda d: d.assign(co2=np.where((d.country == "Aland") & (d.year == LAST), d.co2 * 1.5, d.co2)))
    assert csv2[(csv2.country == "Aland") & (csv2.year == LAST + 1)]["mean"].iloc[0] > base[(base.country == "Aland") & (base.year == LAST + 1)]["mean"].iloc[0] + 5.0  # the final year is used


def test_the_csv_holds_point_forecasts_only_with_the_week_4_style_columns(tmp_path):
    _, _, csv = go(tmp_path)
    assert list(csv.columns) == ["country", "year", "mean"] and len(csv) == len(COUNTRIES) * (2043 - LAST) and (csv["mean"] > 0).all()
    assert not hasattr(E, "simulate") and ".simulate(" not in inspect.getsource(E)  # no unseeded Monte Carlo (Backlog B1)


def test_the_2020_dip_is_left_in_the_training_data(tmp_path):
    def covid(d):
        return d.assign(co2=np.where((d.country == "Bland") & (d.year == 2020), d.co2 * 0.8, d.co2))

    _, _, csv = go(tmp_path, edit=covid)
    raw = observed(tmp_path, 1)
    clean = make_series(1)
    assert raw[YEARS.index(2020)] == pytest.approx(clean[YEARS.index(2020)] * 0.8) and len(raw) == len(YEARS)  # the dip is in the data the stage reads
    assert csv[csv.country == "Bland"].sort_values("year")["mean"].to_numpy() == pytest.approx(direct_forecast(raw, 19)[0], abs=1e-3)  # not interpolated, not dropped


# ---------------------------------------------------------------- the step check (+/-2% aggregate, +/-5% per country)


def test_step_check_uses_the_first_forecast_year_against_the_last_observed_value(tmp_path):
    _, meta, csv = go(tmp_path)
    s = meta["step_check"]
    for i, c in enumerate(COUNTRIES):
        first = csv[(csv.country == c) & (csv.year == LAST + 1)]["mean"].iloc[0]
        assert s["country_steps_pct"][c] == pytest.approx((first / make_series(i)[-1] - 1) * 100, abs=0.01)
    assert s["n_countries"] == 6 and meta["thresholds"] == {"aggregate_step_pct": 2.0, "country_step_pct": 5.0, "max_flagged_share": 0.10}
    assert s["rule"].startswith("aggregate step within +/-2%")


def test_an_aggregate_step_beyond_two_percent_is_a_deviation(tmp_path):
    def dips(d):  # every country's last year drops ~25%: the forecast starts far above the last observation
        return d.assign(co2=np.where(d.year == LAST, d.co2 * 0.75, d.co2))

    rep, meta, _ = go(tmp_path, edit=dips)
    assert meta["step_check"]["aggregate_breach"] is True and meta["step_check"]["aggregate_step_pct"] > 2.0
    assert any("the aggregate first-year step is" in d and "tolerance ±2%" in d for d in rep.deviations)
    assert meta["step_check"]["systematic_breach"] is True and any("countries start outside ±5%" in d for d in rep.deviations)


def test_a_single_outlier_country_is_a_note_with_its_step_and_not_a_deviation(tmp_path):
    def one_dip(d):
        return d.assign(co2=np.where((d.country == "Cland") & (d.year == LAST), d.co2 * 0.6, d.co2))

    many = COUNTRIES + [f"Extra{i}" for i in range(14)]  # 1 of 20 = 5% < the 10% systematic share
    rep, meta, _ = go(tmp_path, edit=lambda d: one_dip(d), countries=COUNTRIES)  # 1 of 6 = 16.7%: systematic with a small set
    assert meta["step_check"]["systematic_breach"] is True
    rows = []
    for i, c in enumerate(many):
        rows.append(pd.DataFrame({"country": c, "year": YEARS, "co2": make_series(i % 6)}))
    d = pd.concat(rows, ignore_index=True)
    d = d.assign(co2=np.where((d.country == "Cland") & (d.year == LAST), d.co2 * 0.6, d.co2))
    d.to_csv(tmp_path / "owid-co2-data.csv", index=False)
    (tmp_path / "selected_countries.json").write_text(json.dumps({"expanded": many}))
    rep2 = E.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"), selected_path=str(tmp_path / "selected_countries.json"))
    meta2 = json.loads((tmp_path / "ets_baseline_full_data.json").read_text())
    assert [f["country"] for f in meta2["step_check"]["flagged_countries"]] == ["Cland"] and meta2["step_check"]["systematic_breach"] is False
    assert not any("countries start outside" in x for x in rep2.deviations) and any("1 of 20 countries start outside ±5%" in n and "Cland" in n for n in rep2.notes)


# ---------------------------------------------------------------- anomalies: flagged, not altered


def test_a_single_year_spike_is_flagged_with_its_year_value_and_ratio_and_the_fit_uses_the_data_as_given(tmp_path):
    def spike(d):
        return d.assign(co2=np.where((d.country == "Dland") & (d.year == 1991), 4000.0, d.co2))

    rep, meta, csv = go(tmp_path, edit=spike)
    a = meta["data_anomalies"]
    assert list(a) == ["Dland"] and a["Dland"][0]["year"] == 1991 and a["Dland"][0]["value_mt"] == 4000.0 and a["Dland"][0]["ratio_to_local_median"] > 5
    assert any("data anomaly in Dland: 1991 = 4,000.0 Mt" in n and "its fit is distorted" in n for n in rep.notes) and not any("anomaly" in d for d in rep.deviations)
    raw = observed(tmp_path, 3)
    assert raw[YEARS.index(1991)] == 4000.0
    assert csv[csv.country == "Dland"].sort_values("year")["mean"].to_numpy() == pytest.approx(direct_forecast(raw, 19)[0], abs=1e-3)  # the spike was NOT removed


@pytest.mark.parametrize("factor,flagged", [(1.5, False), (1.9, False), (2.2, True), (0.6, False), (0.4, True)])
def test_the_anomaly_rule_is_two_times_above_or_below_the_local_median(factor, flagged):
    s = pd.Series(np.full(len(YEARS), 100.0), index=YEARS)
    s.loc[2005] = 100.0 * factor
    assert (len(E.anomalies(s)) == 1) is flagged


def test_a_clean_set_has_no_anomaly_flags(tmp_path):
    _, meta, _ = go(tmp_path)
    assert meta["data_anomalies"] == {}


# ---------------------------------------------------------------- the backtest published beside the result


def test_the_backtest_compares_the_refit_with_the_stuck_fit_and_a_naive_baseline(tmp_path):
    _, meta, _ = go(tmp_path)
    bt = {b["cutoff"]: b for b in meta["backtest"]}
    assert sorted(bt) == [2021, 2022] and bt[2021]["horizon"] == 3 and bt[2021]["years"] == [2022, 2023, 2024] and bt[2022]["years"] == [2023, 2024]
    for b in bt.values():
        assert set(b["variants"]) == {"plain_refit", "fit_stuck_at_2018", "naive_last_value"} and "(the COVID years inside the training data)" in b["summary"]
        assert all(len(v["median_abs_country_error_pct"]) == b["horizon"] and len(v["total_error_pct"]) == b["horizon"] for v in b["variants"].values())


def test_the_backtest_numbers_equal_an_independent_calculation(tmp_path):
    _, meta, _ = go(tmp_path)
    b = {x["cutoff"]: x for x in meta["backtest"]}[2021]
    obs = [observed(tmp_path, i) for i in range(6)]
    k = YEARS.index(2021)
    plain = np.array([np.abs(direct_forecast(o[:k + 1], 3)[0] - o[k + 1:]) / o[k + 1:] * 100 for o in obs])
    assert b["variants"]["plain_refit"]["median_abs_country_error_pct"] == pytest.approx(np.median(plain, axis=0), abs=1e-9)
    naive = np.array([np.abs(o[k] - o[k + 1:]) / o[k + 1:] * 100 for o in obs])
    assert b["variants"]["naive_last_value"]["median_abs_country_error_pct"] == pytest.approx(np.median(naive, axis=0), abs=1e-9)
    stuck = np.array([direct_forecast(o[:YEARS.index(2018) + 1], 6)[0][3:] for o in obs])  # fit stuck at 2018: forecasts for 2019..2024, keep 2022-2024
    act = np.array([o[k + 1:] for o in obs])
    assert b["variants"]["fit_stuck_at_2018"]["total_error_pct"] == pytest.approx(((stuck.sum(axis=0) / act.sum(axis=0)) - 1) * 100, abs=1e-9)
    assert b["variants"]["plain_refit"]["total_error_pct"] == pytest.approx(((np.array([direct_forecast(o[:k + 1], 3)[0] for o in obs]).sum(axis=0) / act.sum(axis=0)) - 1) * 100, abs=1e-9)


def test_the_backtest_summary_states_the_numbers_and_makes_no_skill_claim(tmp_path):
    _, meta, _ = go(tmp_path)
    s = meta["backtest"][0]["summary"].lower()
    assert "median per-country error" in s and "6-country total" in s and "stuck at 2018" in s
    assert not any(w in s for w in ("proves", "validated", "reliable", "skill", "guarantee"))


# ---------------------------------------------------------------- scope limits travel with the result


def test_the_scope_limits_are_in_the_json_the_caveats_and_stated_in_the_methodology(tmp_path):
    _, meta, _ = go(tmp_path)
    assert len(meta["scope_limits"]) == 7 and all(x in meta["caveats"] for x in meta["scope_limits"])
    text = " ".join(meta["scope_limits"])
    for phrase in ("ETS(A,Ad,N) only", "No model selection", "the covered countries only", "aggregates mix large and small emitters", "two cutoffs with short, overlapping horizons (2 and 3 years ahead)",
                   "does not establish forecast skill over the 19-year horizon", "no outlier handling", "flagged but not altered", "unseeded Monte Carlo (Backlog B1)", "territorial fossil fuel and cement CO2"):
        assert phrase in text, phrase
    assert "ETS(A,Ad,N)" in meta["methodology"] and "Week 4's fit" in meta["methodology"] and "unchanged" in meta["methodology"]
    assert meta["attribution"]["license"] == "CC BY 4.0"


# ---------------------------------------------------------------- failure behaviour


def test_missing_zero_or_nonfinite_data_makes_the_baseline_unavailable_naming_the_countries(tmp_path):
    rep, meta, csv = go(tmp_path, edit=lambda d: d[~((d.country == "Bland") & (d.year == 2005))])
    assert meta["step_check"] is None and meta["parameters"] is None and len(csv) == 0 and "Bland" in meta["unavailable_reason"] and "missing, non-finite or not positive" in meta["unavailable_reason"]
    assert any("ets_baseline unavailable" in d for d in rep.deviations)
    _, meta2, _ = go(tmp_path / "z" if (tmp_path / "z").mkdir() is None else tmp_path, edit=lambda d: d.assign(co2=np.where((d.country == "Eland") & (d.year == 2010), 0.0, d.co2)))
    assert "Eland" in meta2["unavailable_reason"]
    _, meta3, _ = go(tmp_path / "n" if (tmp_path / "n").mkdir() is None else tmp_path, edit=lambda d: d.assign(co2=np.where((d.country == "Aland") & (d.year == 2000), np.inf, d.co2)))
    assert "Aland" in meta3["unavailable_reason"]


@pytest.mark.parametrize("missing", ["with_owid", "with_selected", "with_world"])
def test_a_missing_input_is_an_explicit_null_with_the_reason_and_never_a_crash(tmp_path, missing):
    rep, meta, csv = go(tmp_path, **{missing: False})
    assert meta["step_check"] is None and len(csv) == 0 and meta["unavailable_reason"] and any("ets_baseline unavailable" in d for d in rep.deviations)


def test_an_unavailable_output_overwrites_the_previous_baseline_and_keeps_the_full_metadata(tmp_path):
    _, good, csv = go(tmp_path)
    assert len(csv) > 0
    os.remove(tmp_path / "selected_countries.json")
    E.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"), selected_path=str(tmp_path / "selected_countries.json"))
    meta = json.loads((tmp_path / "ets_baseline_full_data.json").read_text())
    assert len(pd.read_csv(tmp_path / "ets_baseline_full_data.csv")) == 0 and meta["countries"] is None  # no stale baseline survives
    assert set(meta) - {"unavailable_reason"} == set(good) and len(meta["scope_limits"]) == 7 and meta["methodology"] and meta["thresholds"]["aggregate_step_pct"] == 2.0
    assert meta["inputs"]["owid_world_co2_annual.csv"]["available"] is True and meta["inputs"]["selected_countries.json"] == {"available": False}
    assert meta["inputs"]["owid-co2-data.csv"] == {"available": False}  # not reached: the country list is read first


def test_an_empty_country_list_and_malformed_provenance_are_handled(tmp_path):
    (tmp_path / "x").mkdir()
    write(tmp_path / "x", countries=COUNTRIES)
    (tmp_path / "x" / "selected_countries.json").write_text(json.dumps({"expanded": []}))
    E.run(str(tmp_path / "x"), owid_path=str(tmp_path / "x" / "owid-co2-data.csv"), selected_path=str(tmp_path / "x" / "selected_countries.json"))
    assert "lists no countries" in json.loads((tmp_path / "x" / "ets_baseline_full_data.json").read_text())["unavailable_reason"]
    rep, meta, csv = go(tmp_path, provenance="bad")
    assert "baseline metadata unavailable" in meta["unavailable_reason"] and len(csv) == 0 and meta["attribution"] == {} and any("could not be read" in c for c in meta["caveats"])


def test_the_output_is_deterministic_and_the_stage_is_registered_and_gated(tmp_path):
    from pipeline import run

    _, a, ca = go(tmp_path)
    E.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"), selected_path=str(tmp_path / "selected_countries.json"))
    b = json.loads((tmp_path / "ets_baseline_full_data.json").read_text())
    cb = pd.read_csv(tmp_path / "ets_baseline_full_data.csv")
    for d in (a, b):
        d.pop("generated_at")
    assert a == b and ca.equals(cb)
    assert "ets_baseline" in run.DERIVED_SOURCES and "ets_baseline" not in run.ACTIVE_SOURCES and run.DEPENDS_ON["ets_baseline"] == ("owid",)
