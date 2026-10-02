import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import harmonize, pairing
from pipeline.tests.test_harmonize import write_inputs


def build(tmp_path, edit=None, **kw):
    """Write the synthetic inputs, optionally edit a CSV (edit(dir)), run the harmonize stage, load the result."""
    prov = write_inputs(tmp_path, **kw)
    if edit:
        edit(str(tmp_path))
    harmonize.run(str(tmp_path), prov)
    return pairing.load_harmonized(str(tmp_path))


@pytest.fixture
def h(tmp_path):
    return build(tmp_path)


PPM = lambda y: 280.0 + 0.5 * (y - 1750)
ANOM = lambda y: float(np.linspace(-0.13, 1.6, 175)[y - 1850])


# ---------------------------------------------------------------- loading and series access


def test_load_harmonized_and_series_access(h):
    assert h.meta["baselines"]["preindustrial"]["year"] == 1850 and h.meta["trailing_window_years"] == 5
    s = h.series("co2_concentration_ppm")
    assert s.index.min() == 1750 and s.index.max() == 2025 and s[1900] == pytest.approx(PPM(1900))
    c = h.series("primap_country_ghg_total_mtco2e", "A005")
    assert len(c) == 275 and c[1999] == pytest.approx(6 * (1999 - 1749))


def test_series_enforces_the_scope_contract(h):
    with pytest.raises(ValueError, match="global indicator; it takes no geography"):
        h.series("co2_concentration_ppm", "CHN")
    with pytest.raises(ValueError, match="country indicator; geography .* is required"):
        h.series("primap_country_ghg_total_mtco2e")
    with pytest.raises(ValueError, match="no values for area 'ZZZ'"):
        h.series("primap_country_ghg_total_mtco2e", "ZZZ")
    with pytest.raises(ValueError, match="unknown indicator 'nope'"):
        h.series("nope")


def test_load_refuses_a_missing_catalog_and_an_unknown_schema(tmp_path, h):
    with pytest.raises(FileNotFoundError, match="run `python -m pipeline.run --source harmonize`"):
        pairing.load_harmonized(str(tmp_path / "empty"))
    p = tmp_path / "indicator_catalog.json"
    doc = json.loads(p.read_text())
    doc["schema_version"] = 99
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="schema_version 99"):
        pairing.load_harmonized(str(tmp_path))


# ---------------------------------------------------------------- the pair itself


def test_basic_pair_aligns_on_the_common_range_with_exact_values_and_full_metadata(h):
    f, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    assert list(f.columns) == ["year", "co2_concentration_ppm", "temperature_anomaly_1850_1900_c"]
    assert f.year.min() == 1850 and f.year.max() == 2024 and len(f) == 175 and f.year.is_monotonic_increasing
    r = f[f.year == 1990].iloc[0]
    assert r["co2_concentration_ppm"] == pytest.approx(PPM(1990)) and r["temperature_anomaly_1850_1900_c"] == pytest.approx(ANOM(1990))
    assert m["common_range"] == [1850, 2024] and m["range_used"] == [1850, 2024] and m["range_requested"] == [None, None]
    assert m["n_years_used"] == 175 and m["omitted_years"] == [] and m["n_omitted_years"] == 0 and m["interpolated"] is False
    assert "not proof of causation" in m["note"] and "not a climate model" in m["note"]
    assert m["a"]["unit"] == "ppm" and m["b"]["unit"] == "°C" and m["a"]["coverage"] == [1750, 2025] and m["b"]["coverage"] == [1850, 2024]
    assert m["a"]["provenance"]["series"] == "co2_concentration_annual" and m["b"]["provenance"]["license"] == "CC BY-NC 4.0"
    assert any("Spliced at 1959" in c for c in m["a"]["caveats"])  # the limitation travels with the pair


def test_the_headline_pair_cumulative_emissions_against_temperature(h):
    """OWID cumulative CO2 vs the 1850-1900 anomaly: the TCRE-style pairing the analysis is built on."""
    f, m = pairing.align_pair(h, "owid_co2_world_cumulative_mt", "temperature_anomaly_1850_1900_c")
    cum = lambda y: sum(10.0 * (v - 1749) for v in range(1750, y + 1))
    assert len(f) == 175 and f.iloc[0]["year"] == 1850
    assert f[f.year == 2000].iloc[0]["owid_co2_world_cumulative_mt"] == pytest.approx(cum(2000))
    assert m["a"]["kind"] == "cumulative" and m["b"]["kind"] == "anomaly" and m["geography"] is None


def test_requested_range_wider_than_the_data_lists_every_omitted_year_with_its_reason(h):
    f, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", start=1840, end=2025)
    assert m["range_requested"] == [1840, 2025] and m["range_used"] == [1850, 2024] and m["common_range"] == [1850, 2024]
    assert [o["year"] for o in m["omitted_years"]] == list(range(1840, 1850)) + [2025]
    assert all(o["reason"] == "b missing" for o in m["omitted_years"])  # the temperature series is what is absent
    assert m["n_years_used"] == 175 and m["n_omitted_years"] == 11


def test_interior_gaps_are_omitted_not_interpolated_and_both_missing_is_distinguished(tmp_path):
    def edit(d):
        p = os.path.join(d, "co2_concentration_annual.csv")
        df = pd.read_csv(p)
        pd.DataFrame(df[~df.year.isin([1900, 1901, 1902])]).to_csv(p, index=False)
        p2 = os.path.join(d, "temperature_anomaly_annual.csv")
        t = pd.read_csv(p2)
        t[~t.year.isin([1900, 1950])].to_csv(p2, index=False)

    h = build(tmp_path, edit=edit)
    f, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    reasons = {o["year"]: o["reason"] for o in m["omitted_years"]}
    assert reasons == {1900: "both missing", 1901: "a missing", 1902: "a missing", 1950: "b missing"}
    assert not f.year.isin([1900, 1901, 1902, 1950]).any() and m["n_years_used"] == 175 - 4  # nothing bridged
    assert m["interpolated"] is False


def test_min_overlap_refuses_a_pairing_that_would_mean_nothing(h):
    with pytest.raises(ValueError, match=r"only 15 shared year\(s\) .* at least 20 are required"):
        pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", start=2010, end=2024)
    f, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", start=2010, end=2024, min_overlap=10)
    assert len(f) == 15 and m["min_overlap"] == 10
    with pytest.raises(ValueError, match=r"only 0 shared year\(s\)"):
        pairing.align_pair(h, "owid_co2_international_transport_mt", "temperature_anomaly_1850_1900_c", start=1900, end=1940)  # transport starts in 1950


def test_refusals(h):
    with pytest.raises(ValueError, match="cannot pair an indicator with itself"):
        pairing.align_pair(h, "co2_concentration_ppm", "co2_concentration_ppm")
    with pytest.raises(ValueError, match="cannot pair across scopes: co2_concentration_ppm is global-scope and primap_country_ghg_total_mtco2e is country-scope"):
        pairing.align_pair(h, "co2_concentration_ppm", "primap_country_ghg_total_mtco2e", geography="A005")
    with pytest.raises(ValueError, match="uncertainty series .* not pairable"):
        pairing.align_pair(h, "co2_concentration_ppm", "temperature_uncertainty_95_c")
    with pytest.raises(ValueError, match="empty range: start 2000 is after end 1990"):
        pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", start=2000, end=1990)
    with pytest.raises(ValueError, match="unknown indicator"):
        pairing.align_pair(h, "co2_concentration_ppm", "no_such_indicator")
    with pytest.raises(ValueError, match="takes no geography"):
        pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", geography="A005")


def test_country_pairs_need_one_named_area_and_use_only_its_own_values(h):
    f, m = pairing.align_pair(h, "primap_country_ghg_total_mtco2e", "primap_country_co2_mt", geography="A005")
    assert len(f) == 275 and m["geography"] == "A005"
    r = f[f.year == 2000].iloc[0]
    assert r["primap_country_ghg_total_mtco2e"] == pytest.approx(6 * (2000 - 1749)) and r["primap_country_co2_mt"] == pytest.approx(0.7 * 6 * (2000 - 1749))
    # F-gases only exist from 1990 in the fixture: the common range follows the shorter series
    f2, m2 = pairing.align_pair(h, "primap_country_ghg_total_mtco2e", "primap_country_fgas_mtco2e", geography="A005")
    assert m2["common_range"] == [1990, 2024] and len(f2) == 35
    with pytest.raises(ValueError, match="geography .* is required"):
        pairing.align_pair(h, "primap_country_ghg_total_mtco2e", "primap_country_co2_mt")
    # a different area gives different numbers: nothing leaks between areas
    other, _ = pairing.align_pair(h, "primap_country_ghg_total_mtco2e", "primap_country_co2_mt", geography="A100")
    assert other[other.year == 2000].iloc[0]["primap_country_ghg_total_mtco2e"] == pytest.approx(101 * (2000 - 1749))


def test_derived_indicators_pair_too_and_the_range_follows_their_own_coverage(h):
    f, m = pairing.align_pair(h, "co2_concentration_ppm__index_1990", "temperature_anomaly_1850_1900_c__mean5y")
    assert m["common_range"] == [1854, 2024] and len(f) == 171  # a trailing 5-year mean starts four years into the record
    assert f[f.year == 1990].iloc[0]["co2_concentration_ppm__index_1990"] == pytest.approx(100.0)
    assert f[f.year == 2000].iloc[0]["temperature_anomaly_1850_1900_c__mean5y"] == pytest.approx(np.mean([ANOM(y) for y in range(1996, 2001)]))
    assert m["a"]["kind"] == "derived" and m["b"]["kind"] == "derived"


def test_pairing_does_not_mutate_the_loaded_tables_and_is_repeatable(h):
    before = h.global_long.copy()
    f1, m1 = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    f1.loc[:, "co2_concentration_ppm"] = -1.0  # a caller scribbling on the result
    f2, m2 = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    assert h.global_long.equals(before) and (f2["co2_concentration_ppm"] > 0).all() and m1["common_range"] == m2["common_range"]


# ---------------------------------------------------------------- review follow-ups (remote commits bebf04e, ff15492)


def test_result_metadata_cannot_be_used_to_mutate_the_loaded_catalog(h):
    """The pair's metadata carries copies of the provenance link and caveats, not references into the catalog."""
    before_caveats = list(h.entry("co2_concentration_ppm")["caveats"])
    before_prov = json.loads(json.dumps(h.entry("co2_concentration_ppm")["provenance"]))
    _, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    m["a"]["caveats"].append("scribble")
    m["a"]["caveats"][0] = "changed"
    m["a"]["provenance"]["license"] = "TAMPERED"
    m["a"]["provenance"]["source_release"]["x"] = 999
    assert h.entry("co2_concentration_ppm")["caveats"] == before_caveats
    assert h.entry("co2_concentration_ppm")["provenance"] == before_prov
    _, m2 = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    assert m2["a"]["provenance"]["license"] != "TAMPERED" and "scribble" not in m2["a"]["caveats"]


def test_a_pair_whose_provenance_is_missing_still_works_with_a_null_link(tmp_path):
    h = build(tmp_path, drop=("co2_concentration_annual",))  # no provenance entry for the source series
    _, m = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c")
    assert m["a"]["provenance"] is None and m["b"]["provenance"] is not None


@pytest.mark.parametrize("bad", [0, -1, -20])
def test_min_overlap_below_one_is_rejected_up_front(h, bad):
    with pytest.raises(ValueError, match="min_overlap must be at least 1"):
        pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", min_overlap=bad)  # 175 shared years: still refused
    f, _ = pairing.align_pair(h, "co2_concentration_ppm", "temperature_anomaly_1850_1900_c", min_overlap=1)
    assert len(f) == 175
