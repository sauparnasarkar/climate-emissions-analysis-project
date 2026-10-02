import json

import pytest

from pipeline import berkeley_earth as be

from .conftest import make_fetched


def test_parse_summary_uses_air_version_and_skips_comments(berkeley_text):
    df = be.parse_summary(berkeley_text)
    assert list(df.columns) == ["year", "anomaly_1951_1980_c", "uncertainty_95_c"]
    assert df["year"].min() == 1850 and df["year"].max() == 2024
    assert df.loc[df["year"] == 1900, "anomaly_1951_1980_c"].iloc[0] == pytest.approx(-0.4)  # air column, not the water one (-0.5)


def test_parse_summary_empty_raises():
    with pytest.raises(ValueError):
        be.parse_summary("% only comments\n")


def test_parse_release(berkeley_text):
    r = be.parse_release(berkeley_text)
    assert r["land_analysis_run"].startswith("04-Jan-2025") and r["abs_mean_1951_1980_air_c"] == pytest.approx(14.102)


def test_preindustrial_offset_is_computed_from_data(berkeley_text):
    off = be.preindustrial_offset(be.parse_summary(berkeley_text))
    assert off["value_c"] == pytest.approx(-0.4) and off["years"] == 51 and off["reference_period"] == [1850, 1900]


def test_preindustrial_offset_requires_full_window(berkeley_text):
    df = be.parse_summary(berkeley_text)
    with pytest.raises(ValueError, match="of 51 years"):
        be.preindustrial_offset(df[df["year"] != 1875])


def test_to_normalized_rebases_anomaly(berkeley_text):
    df = be.parse_summary(berkeley_text)
    out = be.to_normalized(df, -0.4)
    assert out.loc[out["year"] == 1900, "anomaly_1850_1900_c"].iloc[0] == pytest.approx(0.0)
    assert out.loc[out["year"] == 2000, "anomaly_1850_1900_c"].iloc[0] == pytest.approx(2.0)


class _Today:
    year, month, day = 2026, 10, 1


def test_run_flags_stale_source_file(tmp_path, berkeley_text):
    fetcher = lambda url: make_fetched(url, berkeley_text, last_modified="2025-01-10T04:48:46+00:00")  # noqa: E731
    report = be.run(fetcher, out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=_Today)
    assert report.records == {"temperature_anomaly_annual": 175}
    assert any("last modified 2025-01-10" in d for d in report.deviations)
    prov = json.loads((tmp_path / "p.json").read_text())["temperature_anomaly_annual"]
    assert prov["preindustrial_offset"]["value_c"] == pytest.approx(-0.4)
    assert prov["coverage"] == [1850, 2024] and prov["license"].startswith("Berkeley Earth data: CC BY 4.0")


def test_run_fresh_source_has_no_deviations(tmp_path, berkeley_text):
    fetcher = lambda url: make_fetched(url, berkeley_text, last_modified="2026-09-20T00:00:00+00:00")  # noqa: E731
    class T:  # one year after the data end is within MAX_LAG_YEARS
        year, month, day = 2026, 10, 1
    report = be.run(fetcher, out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=T)
    assert report.deviations == []


def test_parse_summary_rejects_missing_year_after_1900(berkeley_text):
    text = "\n".join(ln for ln in berkeley_text.splitlines() if not ln.strip().startswith("1950 "))
    with pytest.raises(ValueError, match="missing year.*1950"):
        be.parse_summary(text)


def test_parse_summary_rejects_missing_1850(berkeley_text):
    text = "\n".join(ln for ln in berkeley_text.splitlines() if not ln.strip().startswith("1850 "))
    with pytest.raises(ValueError, match="1850"):
        be.parse_summary(text)
