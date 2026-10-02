import hashlib
import io
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from pipeline import primap_hist as ph
from pipeline.common import Fetched, RunReport
from pipeline.crosswalk import build_crosswalk

YEARS = list(range(1990, 2026))  # 2025 is the (partial) trailing year, like v2.8
AREAS = ["AAA", "BBB", "CCC", "DDD"]
CSV_KEY = "Guetschow_et_al_2026-PRIMAP-hist_v9.9_final_no_extrap_22-Sep-2026.csv"
YAML_KEY = CSV_KEY.replace(".csv", ".yaml")


def make_csv(partial_2025=True, jump_year=None, drop_small_area_from=None, gap_year=None) -> bytes:
    """Synthetic PRIMAP-hist CSV: HISTCR/M.0.EL real series plus decoy rows (HISTTP scenario,
    another category) that must be ignored. Gg values; baskets consistent with the components."""
    rows = []
    for a_i, a in enumerate(AREAS):
        size = 1000.0 * (a_i + 1) if a != "DDD" else 1.0  # DDD is a tiny emitter
        for y in YEARS:
            g = 1.02 ** (y - 1990)
            if jump_year and y >= jump_year:
                g *= 1.4
            co2, ch4, n2o, fg = size * g, size * 0.05 * g, size * 0.002 * g, size * 0.01 * g
            vals = {"CO2": co2, "CH4": ch4, "N2O": n2o, "FGASES (AR5GWP100)": fg}
            vals["KYOTOGHG (AR5GWP100)"] = co2 + 28 * ch4 + 265 * n2o + fg
            if y == 2025 and partial_2025:
                vals["CH4"] = ch4 if a == "AAA" and False else np.nan  # no CH4, N2O, F-gases in 2025
                vals["N2O"] = np.nan
                vals["FGASES (AR5GWP100)"] = np.nan
                vals["KYOTOGHG (AR5GWP100)"] = co2
            if drop_small_area_from and a == "DDD" and y >= drop_small_area_from:
                vals = {k: np.nan for k in vals}
            if gap_year and y == gap_year:
                vals["CH4"] = np.nan
                vals["N2O"] = np.nan
                vals["FGASES (AR5GWP100)"] = np.nan
                vals["KYOTOGHG (AR5GWP100)"] = np.nan
            for ent, v in vals.items():
                rows.append({"source": "PRIMAP-hist_v9.9_final_ne", "scenario (PRIMAP-hist)": "HISTCR", "provenance": "derived", "area (ISO3)": a,
                             "entity": ent, "unit": "x", "category (IPCC2006_PRIMAP)": "M.0.EL", "year": y, "v": v})
                # decoys: wrong scenario / wrong category with absurd values
                rows.append({"source": "PRIMAP-hist_v9.9_final_ne", "scenario (PRIMAP-hist)": "HISTTP", "provenance": "derived", "area (ISO3)": a,
                             "entity": ent, "unit": "x", "category (IPCC2006_PRIMAP)": "M.0.EL", "year": y, "v": 9e9})
                rows.append({"source": "PRIMAP-hist_v9.9_final_ne", "scenario (PRIMAP-hist)": "HISTCR", "provenance": "derived", "area (ISO3)": a,
                             "entity": ent, "unit": "x", "category (IPCC2006_PRIMAP)": "1", "year": y, "v": 9e9})
    long = pd.DataFrame(rows)
    wide = long.pivot_table(index=["source", "scenario (PRIMAP-hist)", "provenance", "area (ISO3)", "entity", "unit", "category (IPCC2006_PRIMAP)"],
                            columns="year", values="v", aggfunc="first", dropna=False).reset_index()
    wide.columns = [str(c) for c in wide.columns]
    return wide.to_csv(index=False).encode()


def release_json(csv_bytes: bytes, yaml_bytes=b"attrs: {}\n", licence="cc-by-nc-sa-4.0", published="2026-09-29"):
    def f(key, content):
        return {"key": key, "checksum": "md5:" + hashlib.md5(content).hexdigest(), "links": {"self": f"https://zenodo.test/{key}"}, "size": len(content)}

    return {
        "doi": "10.5281/zenodo.999", "conceptdoi": "10.5281/zenodo.4479171",
        "metadata": {"version": "v9.9", "publication_date": published, "license": {"id": licence}},
        "files": [f(CSV_KEY, csv_bytes), f(YAML_KEY, yaml_bytes),
                  f(CSV_KEY.replace("no_extrap", "no_extrap_no_rounding"), b"decoy1"), f(CSV_KEY.replace("_no_extrap", ""), b"decoy2")],
    }


def fetcher_for(csv_bytes, release=None, corrupt=False):
    rel = release or release_json(csv_bytes)
    blobs = {f["links"]["self"]: (b"corrupted" if corrupt and f["key"] == CSV_KEY else csv_bytes if f["key"] == CSV_KEY else b"attrs: {}\n") for f in rel["files"]}

    def fetch(url):
        content = json.dumps(rel).encode() if url == ph.ZENODO_CONCEPT_URL else blobs[url]
        return Fetched(url, content, hashlib.sha256(content).hexdigest(), "2026-10-02T00:00:00+00:00", None)

    return fetch


@pytest.fixture
def wides():
    return ph.parse_primap(make_csv())


# ---------------------------------------------------------------- discovery & integrity


def test_pick_files_takes_only_the_no_extrap_default_rounding_pair():
    rel = release_json(b"x")
    picked = ph.pick_files(rel)
    assert picked["csv"]["key"] == CSV_KEY and picked["yaml"]["key"] == YAML_KEY


def test_pick_files_fails_when_ambiguous_or_missing():
    rel = release_json(b"x")
    with pytest.raises(ValueError, match="found 0"):
        ph.pick_files({"files": [f for f in rel["files"] if f["key"] != CSV_KEY]})
    dup = {"files": rel["files"] + [dict(rel["files"][0], key=CSV_KEY.replace("22-Sep", "23-Sep"))]}
    with pytest.raises(ValueError, match="found 2"):
        ph.pick_files(dup)


def test_verify_checksum():
    ph.verify_checksum(b"abc", "md5:" + hashlib.md5(b"abc").hexdigest(), "f")
    with pytest.raises(ValueError, match="MD5 mismatch"):
        ph.verify_checksum(b"abd", "md5:" + hashlib.md5(b"abc").hexdigest(), "f")
    with pytest.raises(ValueError, match="unsupported checksum"):
        ph.verify_checksum(b"abc", "sha1:00", "f")


# ---------------------------------------------------------------- parsing


def test_parse_primap_ignores_other_scenarios_and_categories(wides):
    assert set(wides) == {"co2", "ch4", "n2o", "fgas", "total"}
    assert wides["co2"].loc["AAA", 1990] == pytest.approx(1000.0)  # not the 9e9 decoys
    assert wides["total"].shape == (len(AREAS), len(YEARS))


def test_parse_primap_missing_entity_or_duplicate_areas_raise():
    df = pd.read_csv(io.BytesIO(make_csv()))
    no_n2o = df[df["entity"] != "N2O"].to_csv(index=False).encode()
    with pytest.raises(ValueError, match="no rows for entity 'N2O'"):
        ph.parse_primap(no_n2o)
    dup = pd.concat([df, df[(df.entity == "CO2") & (df["scenario (PRIMAP-hist)"] == "HISTCR") & (df["category (IPCC2006_PRIMAP)"] == "M.0.EL")].head(1)]).to_csv(index=False).encode()
    with pytest.raises(ValueError, match="duplicate areas"):
        ph.parse_primap(dup)
    with pytest.raises(ValueError, match="expected column"):
        ph.parse_primap(df.rename(columns={"area (ISO3)": "area"}).to_csv(index=False).encode())


# ---------------------------------------------------------------- completeness


def test_weighted_coverage_ignores_tiny_dropouts_but_not_big_ones():
    w = pd.DataFrame({2000: [1000.0, 1.0, 500.0], 2001: [1010.0, np.nan, 505.0]}, index=list("ABC"))
    assert ph.weighted_coverage(w)[2001] == pytest.approx(1500 / 1501)  # tiny area dropped: ~99.93%
    w2 = pd.DataFrame({2000: [1000.0, 1.0, 500.0], 2001: [np.nan, 1.0, 505.0]}, index=list("ABC"))
    assert ph.weighted_coverage(w2)[2001] == pytest.approx(501 / 1501)  # the big one dropped: 33%


def test_weighted_coverage_is_nan_when_previous_year_has_no_emissions():
    w = pd.DataFrame({2000: [0.0, 0.0], 2001: [5.0, np.nan]}, index=list("AB"))
    assert np.isnan(ph.weighted_coverage(w)[2001])


def test_partial_trailing_year_is_trimmed_with_metrics(wides):
    a = ph.assess_years(wides)
    last, excluded = ph.trim_incomplete(a)
    assert last == 2024 and [e["year"] for e in excluded] == [2025]
    e = excluded[0]
    assert e["weighted_coverage_pct"]["ch4"] == 0.0 and e["weighted_coverage_pct"]["co2"] == 100.0
    assert e["areas"]["fgas"] == 0 and "ch4 coverage" in e["reasons"] and e["yoy_pct"] < -15
    assert a.loc[a.year == 2024, "complete"].item() and a.loc[a.year == 1990, "complete"].item()  # first year has no reference: passes


def test_small_area_dropping_out_does_not_make_a_year_incomplete():
    # the real-world F-gas drift: an area stops reporting but holds ~0.04% of emissions
    w = ph.parse_primap(make_csv(partial_2025=False, drop_small_area_from=2020))
    a = ph.assess_years(w)
    assert a["complete"].all()
    assert a.loc[a.year == 2024, "areas_fgas"].item() == 3 < a.loc[a.year == 2019, "areas_fgas"].item()


def test_interior_failure_raises_never_silently_dropped():
    w = ph.parse_primap(make_csv(partial_2025=False, gap_year=2010))
    with pytest.raises(ValueError, match="interior year 2010"):
        ph.trim_incomplete(ph.assess_years(w))


def test_total_jump_beyond_yoy_limit_fails_a_trailing_year():
    w = ph.parse_primap(make_csv(partial_2025=False, jump_year=2025))  # +40% in the last year
    last, excluded = ph.trim_incomplete(ph.assess_years(w))
    assert last == 2024 and "vs prior year" in excluded[0]["reasons"]


def test_no_passing_year_raises():
    a = pd.DataFrame({"year": [2000, 2001], "complete": [False, False], "reasons": ["x", "y"], "total_gt": [1, 1], "yoy": [np.nan, 0.0]})
    with pytest.raises(ValueError, match="no year passes"):
        ph.trim_incomplete(a)


# ---------------------------------------------------------------- tables


def test_build_tables_units_nulls_and_consistency(wides):
    country, g = ph.build_tables(wides, 2024)
    assert g["year"].max() == 2024 and country["year"].max() == 2024  # 2025 never published
    r = g[g.year == 1990].iloc[0]
    # sizes 1000+2000+3000+1 Gg => CO2 6.001 Mt; CH4 0.05*size*28 etc.
    assert r["co2_mt"] == pytest.approx(6.001)
    assert r["ch4_mtco2e"] == pytest.approx(6.001 * 0.05 * 28)
    assert r["n2o_mtco2e"] == pytest.approx(6.001 * 0.002 * 265)
    assert abs(r["residual_pct"]) < 1e-6  # components reproduce the Kyoto basket
    assert len(country) == len(AREAS) * (2024 - 1990 + 1) and set(country["entity_type"]) == {"country"}


def test_missing_values_stay_null_not_zero():
    w = ph.parse_primap(make_csv(partial_2025=False, drop_small_area_from=2020))
    country, _ = ph.build_tables(w, 2024)
    d = country[(country.iso3 == "DDD") & (country.year == 2022)].iloc[0]
    assert pd.isna(d["total_ghg_mtco2e"]) and pd.isna(d["co2_mt"])


def test_check_consistency_flags_basket_mismatch(wides):
    _, g = ph.build_tables(wides, 2024)
    rep = RunReport("primap_hist")
    ph.check_consistency(g, rep)
    assert rep.deviations == [] and any("per-gas sum vs Kyoto basket" in n for n in rep.notes)
    wides["total"] = wides["total"] * 1.02  # basket 2% off the components
    _, g2 = ph.build_tables(wides, 2024)
    rep2 = RunReport("primap_hist")
    ph.check_consistency(g2, rep2)
    assert len(rep2.deviations) == 1 and "Kyoto basket" in rep2.deviations[0]


# ---------------------------------------------------------------- end to end


def owid_df():
    return pd.DataFrame({"country": ["Alpha", "Beta", "Gamma", "World", "Delta"], "iso_code": ["AAA", "BBB", "CCC", np.nan, "ZZZ"]})


def test_run_end_to_end(tmp_path):
    csv = make_csv()
    rep = ph.run(fetcher_for(csv), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=date(2026, 10, 2), owid=owid_df(), expanded=["Alpha", "Delta"])
    assert rep.records["primap_global_composition_annual"] == 2024 - 1990 + 1
    assert any("excluded incomplete year 2025" in n for n in rep.notes)
    assert any("expanded-set countries without a PRIMAP-hist area: Delta" in d for d in rep.deviations)
    g = pd.read_csv(tmp_path / "primap_global_composition_annual.csv")
    assert g["year"].max() == 2024
    prov = json.loads((tmp_path / "p.json").read_text())
    p = prov["primap_global_composition_annual"]
    assert p["coverage"] == [1990, 2024] and p["excluded_incomplete_years"][0]["year"] == 2025
    assert p["source_release"]["version"] == "v9.9" and p["checksum_verified"]["csv"].startswith("md5:")
    assert "CC BY-NC-SA 4.0" in p["license"] and p["attribution_required"] is True and p["published"] is True and len(p["citations"]) == 2
    assert p["completeness_rule"]["coverage_min_weighted"] == 0.98 and p["completeness_rule"]["yoy_max"] == 0.15
    cw = pd.read_csv(tmp_path / "country_crosswalk.csv")
    assert "primap_name" in cw.columns and set(cw.loc[cw.match == "iso3_exact", "iso3"]) == {"AAA", "BBB", "CCC"}


def test_run_rejects_corrupt_download(tmp_path):
    with pytest.raises(ValueError, match="MD5 mismatch"):
        ph.run(fetcher_for(make_csv(), corrupt=True), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=date(2026, 10, 2), owid=owid_df())
    assert not (tmp_path / "primap_global_composition_annual.csv").exists()  # nothing published from a bad download


def test_run_flags_licence_change_and_stale_release(tmp_path):
    csv = make_csv()
    rel = release_json(csv, licence="cc-by-nc-nd-4.0", published="2024-01-01")
    rep = ph.run(fetcher_for(csv, rel), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=date(2026, 10, 2), owid=owid_df())
    assert any("licence changed" in d for d in rep.deviations) and any("days ago" in d for d in rep.deviations)


def test_run_flags_more_than_one_trailing_year_excluded(tmp_path):
    # drop the F-gas/CH4/N2O data for 2024 too -> two trailing incomplete years
    df = pd.read_csv(io.BytesIO(make_csv()))
    m = df["entity"].isin(["CH4", "N2O", "FGASES (AR5GWP100)"])
    df.loc[m, "2024"] = np.nan
    csv = df.to_csv(index=False).encode()
    rep = ph.run(fetcher_for(csv), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=date(2026, 10, 2), owid=owid_df())
    assert any("2 trailing years excluded" in d for d in rep.deviations)
    assert pd.read_csv(tmp_path / "primap_global_composition_annual.csv")["year"].max() == 2023


def test_crosswalk_with_code_only_source_names():
    cw = build_crosswalk({"AAA": None, "XXX": None}, owid_df(), source_label="primap").set_index("iso3")
    assert cw.loc["AAA", "match"] == "iso3_exact" and not cw.loc["AAA", "name_differs"]
    assert cw.loc["XXX", "match"] == "primap_only" and "primap_name" in cw.columns


# ---------------------------------------------------------------- author-notification record (pipeline/source_notices.json)


def write_notices(tmp_path, version="v9.9", sent_at="2026-10-02T06:27:27Z", replies=None, name="notices.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"primap_hist": {"notifications": [{
        "type": "notification_of_use", "sent_at": sent_at, "to": "nc-support@example.test",
        "dataset_version_at_notification": version, "status": "sent", "replies": replies or []}]}}))
    return str(p)


def run_with_notices(tmp_path, notices_path, today=date(2026, 10, 2)):
    return ph.run(fetcher_for(make_csv()), out_dir=str(tmp_path), provenance_path=str(tmp_path / "p.json"), today=today,
                  owid=owid_df(), notices_path=notices_path)


def test_notification_record_is_copied_into_provenance_every_run(tmp_path):
    rep = run_with_notices(tmp_path, write_notices(tmp_path))
    n = json.loads((tmp_path / "p.json").read_text())["primap_global_composition_annual"]["author_notification"]
    assert n["covers_current_version"] is True and n["requested_by_provider"] is True
    assert n["notices"][0]["sent_at"] == "2026-10-02T06:27:27Z" and n["notices"][0]["to"] == "nc-support@example.test"
    assert not any("notifying" in d for d in rep.deviations)
    # and in the country series too (both entries carry it)
    assert json.loads((tmp_path / "p.json").read_text())["primap_country_annual"]["author_notification"]["covers_current_version"] is True


def test_missing_record_is_an_alert_because_the_provider_asks_to_be_notified(tmp_path):
    rep = run_with_notices(tmp_path, str(tmp_path / "does_not_exist.json"))
    assert any("no record of notifying the PRIMAP-hist authors" in d for d in rep.deviations)
    assert json.loads((tmp_path / "p.json").read_text())["primap_global_composition_annual"]["author_notification"]["notices"] == []


def test_new_release_not_covered_by_the_notification_is_a_note_not_an_alert(tmp_path):
    rep = run_with_notices(tmp_path, write_notices(tmp_path, version="v2.8"))  # release in the test is v9.9
    assert any("notifications on file cover ['v2.8']" in n and "consider notifying" in n for n in rep.notes)
    assert not any("notifying" in d for d in rep.deviations)
    assert json.loads((tmp_path / "p.json").read_text())["primap_global_composition_annual"]["author_notification"]["covers_current_version"] is False


def test_unanswered_notification_after_60_days_is_noted_not_alerted(tmp_path):
    p = write_notices(tmp_path)
    assert not any("no recorded reply" in n for n in run_with_notices(tmp_path, p, today=date(2026, 11, 1)).notes)  # 30 days
    rep = run_with_notices(tmp_path, p, today=date(2026, 12, 15))  # 74 days
    assert any("has had no recorded reply for 74 days" in n for n in rep.notes) and not any("reply" in d for d in rep.deviations)
    answered = write_notices(tmp_path, replies=[{"received_at": "2026-10-05T00:00:00Z", "summary": "ok"}], name="answered.json")
    assert not any("no recorded reply" in n for n in run_with_notices(tmp_path, answered, today=date(2026, 12, 15)).notes)


def test_malformed_notices_raise_instead_of_silently_dropping_the_record(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"primap_hist": {"notifications": [{"type": "notification_of_use", "to": "x"}]}}))
    with pytest.raises(ValueError, match="missing sent_at"):
        run_with_notices(tmp_path, str(bad))
    badtime = tmp_path / "badtime.json"
    badtime.write_text(json.dumps({"primap_hist": {"notifications": [{"type": "t", "sent_at": "yesterday", "to": "x", "dataset_version_at_notification": "v1", "status": "s"}]}}))
    with pytest.raises(ValueError, match="invalid sent_at"):
        run_with_notices(tmp_path, str(badtime))


def test_the_real_tracked_notices_file_records_the_2026_10_02_notification():
    from pipeline.common import NOTICES_PATH, load_source_notices

    n = load_source_notices("primap_hist", NOTICES_PATH)
    assert len(n) == 1
    assert n[0]["sent_at"] == "2026-10-02T06:27:27Z" and n[0]["to"] == "nc-support@johannes-guetschow.de"
    assert n[0]["dataset_version_at_notification"] == "v2.8" and n[0]["dataset_doi"] == "10.5281/zenodo.22876287"
    assert len(n[0]["questions"]) == 2 and n[0]["replies"] == []
    assert load_source_notices("noaa_gml", NOTICES_PATH) == []  # a source with no entry has none
