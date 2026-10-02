import numpy as np
import pandas as pd
import pytest

from pipeline import derive


def ser(d):
    return pd.Series(d, dtype=float).rename_axis("year")


def test_yoy_pct_uses_the_previous_calendar_year_not_the_previous_row():
    s = ser({2000: 100.0, 2001: 110.0, 2003: 121.0})  # 2002 is absent
    out = derive.yoy_pct(s)
    assert np.isnan(out[2000])
    assert out[2001] == pytest.approx(10.0)
    assert np.isnan(out[2003])  # the previous *calendar* year (2002) is missing: no change is claimed from 2001


def test_yoy_pct_refuses_a_base_that_is_not_positive():
    out = derive.yoy_pct(ser({1: 0.0, 2: 5.0, 3: -2.0, 4: 3.0}))
    assert np.isnan(out[2]) and np.isnan(out[4])  # from zero / from a negative: undefined


def test_trailing_mean_is_trailing_needs_five_consecutive_years_and_never_looks_ahead():
    s = ser({y: float(y - 1999) for y in range(2000, 2008)})  # 1..8
    out = derive.trailing_mean(s)
    assert out.iloc[:4].isna().all() and out[2004] == pytest.approx(3.0)  # mean(1..5)
    assert out[2007] == pytest.approx(6.0)  # mean(4..8): uses 2003-2007 only
    s2 = s.copy()
    s2[2007] = 1000.0  # changing a later year must not change any earlier mean
    assert derive.trailing_mean(s2)[2006] == out[2006]


def test_trailing_mean_does_not_bridge_a_gap():
    s = ser({2000: 1.0, 2001: 2.0, 2002: 3.0, 2003: 4.0, 2004: np.nan, 2005: 6.0, 2006: 7.0, 2007: 8.0, 2008: 9.0, 2009: 10.0})
    out = derive.trailing_mean(s)
    assert np.isnan(out[2003])  # only 4 observations (2000-2003) exist yet: a premature rolling value would be wrong
    assert np.isnan(out[2004]) and np.isnan(out[2008])  # any window containing the gap is null
    assert out[2009] == pytest.approx(8.0)  # 2005..2009 complete again


def test_index_to_baseline_and_its_refusals():
    s = ser({1990: 50.0, 2000: 75.0, 2010: 100.0})
    idx, problem = derive.index_to_baseline(s, 1990)
    assert problem is None and idx[1990] == 100.0 and idx[2010] == pytest.approx(200.0)
    idx, problem = derive.index_to_baseline(s, 1970)
    assert "outside the coverage 1990-2010" in problem and idx.isna().all()
    idx, problem = derive.index_to_baseline(ser({1990: np.nan, 2000: 5.0}), 1990)
    assert "no value in the baseline year 1990" in problem
    idx, problem = derive.index_to_baseline(ser({1990: 0.0, 2000: 5.0}), 1990)
    assert "not greater than zero" in problem and idx.isna().all()
    idx, problem = derive.index_to_baseline(ser({1850: -0.13, 1900: 0.0, 2000: 1.0}), 1850)  # a temperature anomaly: never indexable
    assert "not greater than zero" in problem


def test_cumulative_is_nan_before_the_start_and_from_the_first_interior_gap():
    s = ser({2000: np.nan, 2001: 1.0, 2002: 2.0, 2003: 3.0, 2004: np.nan, 2005: 5.0})
    out = derive.cumulative(s)
    assert np.isnan(out[2000]) and out[2001] == 1.0 and out[2002] == 3.0 and out[2003] == 6.0
    assert np.isnan(out[2004]) and np.isnan(out[2005])  # a total that skipped a year would be silently too small
    assert derive.cumulative(ser({2000: np.nan, 2001: np.nan})).isna().all()
    assert np.isnan(derive.cumulative(ser({2000: 1.0, 2002: 1.0}))[2002])  # a year absent from the index is a gap too


def test_duplicate_years_raise_and_baselines_are_the_spec_2_5_set():
    with pytest.raises(ValueError, match="duplicate years"):
        derive.yoy_pct(pd.Series([1.0, 2.0], index=[2000, 2000]))
    assert derive.BASELINES == {"1990": 1990, "1970": 1970, "preindustrial": 1850}
    assert derive.first_last_valid(ser({1: np.nan, 2: 1.0, 3: 2.0, 4: np.nan})) == (2, 3) and derive.first_last_valid(ser({1: np.nan})) is None
