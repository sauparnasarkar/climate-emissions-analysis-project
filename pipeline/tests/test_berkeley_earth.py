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
    assert prov["non_commercial_only"] is True and prov["attribution_required"] is True and "essd-12-3469-2020" in prov["citations"][0]
    assert "CC BY 4.0" not in prov["license"]  # it is CC BY-NC; a plain CC BY claim here was an error
    assert prov["coverage"] == [1850, 2024] and prov["license"].startswith("CC BY-NC 4.0") and "berkeleyearth.org" in prov["license"]


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


# ---------------------------------------------------------------- provider correspondence (pipeline/source_notices.json)


def _notices(tmp_path, replies=None, sent_at="2026-10-02T14:20:19Z", name="notices.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"berkeley_earth": {"notifications": [{
        "type": "inquiry", "sent_at": sent_at, "to": "data@example.test", "dataset_version_at_notification": "v-old", "status": "sent", "replies": replies or []}]}}))
    return str(p)


def _run_with(tmp_path, berkeley_text, notices_path, last_modified="2025-01-10T04:48:46+00:00"):
    fetcher = lambda url: make_fetched(url, berkeley_text, last_modified=last_modified)  # noqa: E731
    return be.run(fetcher, out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=_Today, notices_path=notices_path)


def test_open_inquiry_is_copied_into_provenance_and_noted_not_alerted(tmp_path, berkeley_text):
    rep = _run_with(tmp_path, berkeley_text, _notices(tmp_path))
    prov = json.loads((tmp_path / "p.json").read_text())["temperature_anomaly_annual"]
    c = prov["provider_correspondence"]["notices"]
    assert len(c) == 1 and c[0]["type"] == "inquiry" and c[0]["sent_at"] == "2026-10-02T14:20:19Z" and c[0]["to"] == "data@example.test"
    assert any("inquiry to Berkeley Earth" in n and "no recorded reply" in n and "2026-10-02" in n for n in rep.notes)
    assert not any("inquiry" in d for d in rep.deviations)  # the stale-source deviation is the alert; the inquiry is context


def test_source_file_changing_after_the_inquiry_is_called_out(tmp_path, berkeley_text):
    rep = _run_with(tmp_path, berkeley_text, _notices(tmp_path), last_modified="2026-10-20T00:00:00+00:00")
    assert any("source file has changed since that inquiry (last modified 2026-10-20)" in n and "record the reply" in n for n in rep.notes)
    rep2 = _run_with(tmp_path, berkeley_text, _notices(tmp_path, name="n2.json"), last_modified="2025-01-10T04:48:46+00:00")
    assert not any("source file has changed" in n for n in rep2.notes)  # an unchanged file says nothing extra


def test_answered_inquiry_is_no_longer_noted_as_open(tmp_path, berkeley_text):
    rep = _run_with(tmp_path, berkeley_text, _notices(tmp_path, replies=[{"received_at": "2026-10-09T00:00:00Z", "summary": "new URL"}]))
    assert not any("no recorded reply" in n for n in rep.notes)
    prov = json.loads((tmp_path / "p.json").read_text())["temperature_anomaly_annual"]
    assert prov["provider_correspondence"]["notices"][0]["replies"][0]["summary"] == "new URL"


def test_no_notices_file_is_fine_for_berkeley_unlike_primap(tmp_path, berkeley_text):
    rep = _run_with(tmp_path, berkeley_text, str(tmp_path / "missing.json"))
    assert not any("notif" in d or "inquiry" in d for d in rep.deviations)  # Berkeley asks only for attribution
    assert json.loads((tmp_path / "p.json").read_text())["temperature_anomaly_annual"]["provider_correspondence"]["notices"] == []


def test_the_real_tracked_file_records_the_berkeley_inquiry_sent_2026_10_02():
    from pipeline.common import NOTICES_PATH, load_source_notices

    (n,) = load_source_notices("berkeley_earth", NOTICES_PATH)
    assert n["type"] == "inquiry" and n["sent_at"] == "2026-10-02T14:20:19Z" and n["to"] == "data@berkeleyearth.org"
    assert "Land_and_Ocean_summary.txt" in n["subject"] and "2025-01-10" in n["dataset_version_at_notification"]
    assert len(n["questions"]) == 2 and len(n["context"]) == 3 and n["replies"] == []
    assert any("1.44" in c and "1.52" in c for c in n["context"])  # the January 2026 report figures the question rests on
