import json

import pandas as pd
import pytest

from pipeline import noaa_gml
from pipeline.noaa_gml import build_concentration, parse_law_dome_co2, parse_noaa_annual, parse_noaa_monthly

from .conftest import make_fetched


def test_parse_noaa_annual_skips_comments(noaa_annual_text):
    df = parse_noaa_annual(noaa_annual_text)
    assert list(df.columns) == ["year", "co2_ppm", "uncertainty_ppm"]
    assert df["year"].iloc[0] == 1959 and df["year"].iloc[-1] == 2025


def test_parse_noaa_monthly(noaa_monthly_text):
    df = parse_noaa_monthly(noaa_monthly_text)
    assert list(df.columns) == ["year", "month", "co2_ppm", "co2_deseasonalized_ppm"]
    assert len(df) == 2 and df["month"].tolist() == [3, 8]


def test_parse_law_dome_reads_co2_columns_not_ch4(law_text):
    df = parse_law_dome_co2(law_text)
    row = df[df["year"] == 1750].iloc[0]
    assert row["co2_ppm"] == pytest.approx(277.0)  # CO2 column, not the 650 ppb CH4 column
    assert df["year"].max() == 2004


def test_parse_law_dome_missing_header_raises():
    with pytest.raises(ValueError, match="YearAD"):
        parse_law_dome_co2("no table here")


def test_build_concentration_splices_at_1959(noaa_annual_text, law_text):
    series, check = build_concentration(parse_noaa_annual(noaa_annual_text), parse_law_dome_co2(law_text))
    assert series["year"].min() == 1750 and series["year"].max() == 2025
    assert series["year"].is_unique and series["year"].is_monotonic_increasing
    by = series.set_index("year")
    assert by.loc[1958, "source"] == "law_dome_spline" and by.loc[1959, "source"] == "noaa_gml_mlo"
    assert pd.isna(by.loc[1958, "uncertainty_ppm"])  # explicit null, not invented
    assert check["splice_year"] == 1959 and check["overlap_years"] == [1959, 2004]
    assert check["gap_at_splice_ppm"] == pytest.approx(315.7 - 315.98, abs=0.01)


def test_build_concentration_requires_noaa_at_splice_year(law_text):
    noaa = pd.DataFrame({"year": [1962, 1963], "co2_ppm": [317.0, 318.0], "uncertainty_ppm": [0.1, 0.1]})
    with pytest.raises(ValueError, match="splice year"):
        build_concentration(noaa, parse_law_dome_co2(law_text))


def _fetcher(texts):
    def f(url):
        return make_fetched(url, texts[url])

    return f


def test_run_writes_outputs_and_provenance(tmp_path, noaa_annual_text, noaa_monthly_text, law_text):
    texts = {noaa_gml.NOAA_ANNUAL_URL: noaa_annual_text, noaa_gml.NOAA_MONTHLY_URL: noaa_monthly_text, noaa_gml.LAW_DOME_URL: law_text}
    prov = tmp_path / "provenance.json"
    report = noaa_gml.run(_fetcher(texts), out_dir=str(tmp_path), provenance_path=str(prov), today_year=2026)
    assert report.records == {"co2_concentration_annual": 276, "co2_concentration_monthly_mlo": 2}
    assert report.deviations == []
    assert (tmp_path / "co2_concentration_annual.csv").exists()
    p = json.loads(prov.read_text())["co2_concentration_annual"]
    assert p["splice"]["splice_year"] == 1959 and p["coverage"] == [1750, 2025]
    assert p["gas_scope"] == "CO2" and p["units"].startswith("ppm") and p["caveats"] and p["license"]


def test_run_flags_stale_series(tmp_path, noaa_annual_text, noaa_monthly_text, law_text):
    texts = {noaa_gml.NOAA_ANNUAL_URL: noaa_annual_text, noaa_gml.NOAA_MONTHLY_URL: noaa_monthly_text, noaa_gml.LAW_DOME_URL: law_text}
    report = noaa_gml.run(_fetcher(texts), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today_year=2030)
    assert any("behind 2030" in d for d in report.deviations)


def test_run_flags_large_splice_gap(tmp_path, noaa_annual_text, noaa_monthly_text, law_text):
    shifted = noaa_annual_text.replace("1959,315.98", "1959,320.98")  # 5 ppm above Law Dome at the splice
    texts = {noaa_gml.NOAA_ANNUAL_URL: shifted, noaa_gml.NOAA_MONTHLY_URL: noaa_monthly_text, noaa_gml.LAW_DOME_URL: law_text}
    report = noaa_gml.run(_fetcher(texts), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today_year=2026)
    assert any("splice" in d for d in report.deviations)
