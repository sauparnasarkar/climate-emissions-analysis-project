import math

import pytest

from pipeline import step_check as S


def obs(n=40, v=100.0):
    return {f"C{i:02d}": v for i in range(n)}


def with_steps(steps_pct, n=40):
    o = obs(n)
    p = dict(o)
    for c, s in steps_pct.items():
        p[c] = o[c] * (1 + s / 100)
    return p, o


# ---------------------------------------------------------------- the numbers


def test_aggregate_and_per_country_steps_match_hand_calculation():
    r = S.check_step({"A": 110.0, "B": 190.0, "C": 50.0}, {"A": 100.0, "B": 200.0, "C": 50.0})
    assert r["aggregate_step_pct"] == pytest.approx((110 + 190 + 50) / (100 + 200 + 50) * 100 - 100)
    assert r["country_steps_pct"] == {"A": pytest.approx(10.0), "B": pytest.approx(-5.0), "C": pytest.approx(0.0)}
    assert r["median_step_pct"] == pytest.approx(0.0) and r["n_countries"] == 3 and r["n_within_2pct"] == 1


def test_median_for_even_and_odd_counts():
    assert S.check_step({"A": 101.0, "B": 103.0}, {"A": 100.0, "B": 100.0})["median_step_pct"] == pytest.approx(2.0)
    assert S.check_step({"A": 101.0, "B": 103.0, "C": 109.0}, {"A": 100.0, "B": 100.0, "C": 100.0})["median_step_pct"] == pytest.approx(3.0)


def test_the_aggregate_is_weighted_by_size_not_an_average_of_percentages():
    r = S.check_step({"big": 1010.0, "small": 20.0}, {"big": 1000.0, "small": 10.0})  # small doubles (+100%), the total moves +2.0%
    assert r["aggregate_step_pct"] == pytest.approx((1030 / 1010 - 1) * 100) and r["country_steps_pct"]["small"] == pytest.approx(100.0)


# ---------------------------------------------------------------- thresholds (+/-2% aggregate, +/-5% per country)


@pytest.mark.parametrize("agg,breach", [(0.0, False), (1.99, False), (2.0, False), (2.01, True), (-2.0, False), (-2.01, True), (3.7, True), (0.9, False)])
def test_the_aggregate_threshold_is_two_percent_and_inclusive(agg, breach):
    r = S.check_step({"A": 100.0 * (1 + agg / 100)}, {"A": 100.0})
    assert r["aggregate_breach"] is breach and r["aggregate_tolerance_pct"] == 2.0


@pytest.mark.parametrize("step,flagged", [(4.99, False), (5.0, False), (5.01, True), (-5.0, False), (-5.01, True), (0.0, False), (61.9, True)])
def test_the_per_country_threshold_is_five_percent_and_inclusive(step, flagged):
    p, o = with_steps({"C00": step})
    r = S.check_step(p, o)
    assert (len(r["flagged_countries"]) == 1) is flagged and r["country_tolerance_pct"] == 5.0


def test_flagged_countries_are_listed_with_their_step_sorted_most_negative_first():
    p, o = with_steps({"C01": 12.0, "C02": -20.0, "C03": 6.0, "C04": 3.0})
    f = S.check_step(p, o)["flagged_countries"]
    assert [x["country"] for x in f] == ["C02", "C03", "C01"] and f[0]["step_pct"] == pytest.approx(-20.0)


def test_a_few_outliers_are_reported_but_only_a_systematic_breach_is_a_deviation():
    p, o = with_steps({"C00": -13.8, "C01": -5.8, "C02": -5.4})  # today's current fit: 3 of 40
    r = S.check_step(p, o)
    dev, notes = S.step_messages(r, "baseline")
    assert r["systematic_breach"] is False and r["flagged_share"] == pytest.approx(3 / 40) and dev == [] and len(notes) == 1
    assert "3 of 40 countries start outside ±5% of their last observed value (C00 -13.8%, C01 -5.8%, C02 -5.4%)" in notes[0]


@pytest.mark.parametrize("n_flagged,systematic", [(3, False), (4, False), (5, True), (31, True)])
def test_systematic_means_strictly_more_than_ten_percent_of_countries(n_flagged, systematic):
    p, o = with_steps({f"C{i:02d}": 8.0 for i in range(n_flagged)})  # 4 of 40 is exactly 10%: not systematic; 5 of 40 is
    r = S.check_step(p, o)
    assert r["systematic_breach"] is systematic and r["max_flagged_share"] == 0.10
    dev, notes = S.step_messages(r, "x")
    assert (len([d for d in dev if "countries start outside" in d]) == 1) is systematic


def test_the_stale_fit_pattern_is_a_deviation_and_the_current_fit_pattern_is_not():
    stale, o = with_steps({f"C{i:02d}": 12.0 for i in range(31)})  # 31 of 40 outside +/-5%, as the fit stuck at 2018
    dev, _ = S.step_messages(S.check_step(stale, o), "stale")
    assert any("31 of 40 countries" in d and "more than the systematic threshold" in d for d in dev)
    current, o2 = with_steps({"C00": -13.8, "C01": -5.8, "C02": -5.4})
    assert S.step_messages(S.check_step(current, o2), "current")[0] == []


def test_an_aggregate_breach_is_a_deviation_with_the_number():
    r = S.check_step({"A": 103.7}, {"A": 100.0})
    dev, _ = S.step_messages(r, "scenarios")
    assert dev[0].startswith("scenarios: the aggregate first-year step is +3.7% from the last observed total (tolerance ±2%)")


def test_long_flagged_lists_are_abbreviated():
    p, o = with_steps({f"C{i:02d}": 9.0 for i in range(9)})
    _, _ = S.step_messages(S.check_step(p, o), "x")
    dev, _ = S.step_messages(S.check_step(p, o), "x")
    assert "and 3 more" in dev[-1]


def test_custom_thresholds_are_honoured():
    p, o = with_steps({"C00": 4.0})
    assert S.check_step(p, o, country_tol=3.0)["flagged_countries"][0]["country"] == "C00" and not S.check_step(p, o)["flagged_countries"]
    assert S.check_step({"A": 101.0}, {"A": 100.0}, aggregate_tol=0.5)["aggregate_breach"]


# ---------------------------------------------------------------- invalid input is an error, not a quiet pass


def test_mismatched_country_sets_are_refused_with_both_differences_named():
    with pytest.raises(ValueError, match=r"only projected: \['B'\]; only observed: \['C'\]"):
        S.check_step({"A": 1.0, "B": 2.0}, {"A": 1.0, "C": 2.0})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "x", None])
def test_non_finite_or_non_numeric_values_are_refused(bad):
    with pytest.raises(ValueError, match="non-finite projected value"):
        S.check_step({"A": bad}, {"A": 1.0})
    with pytest.raises(ValueError, match="non-finite observed value"):
        S.check_step({"A": 1.0}, {"A": bad})


@pytest.mark.parametrize("observed", [0.0, -3.0])
def test_a_non_positive_observed_total_makes_a_relative_step_undefined(observed):
    with pytest.raises(ValueError, match="observed total is not positive for: A"):
        S.check_step({"A": 1.0}, {"A": observed})


def test_an_empty_check_is_refused():
    with pytest.raises(ValueError, match="no countries to check"):
        S.check_step({}, {})


def test_the_rule_is_stated_in_the_result_for_the_output_metadata():
    r = S.check_step({"A": 100.0}, {"A": 100.0})
    assert r["rule"] == "aggregate step within +/-2%; per-country steps reported when outside +/-5% and a deviation only when more than 10% of countries are outside"
    assert math.isfinite(r["aggregate_step_pct"])
