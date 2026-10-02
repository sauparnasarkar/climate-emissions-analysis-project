import json
import urllib.error

import pytest

from pipeline import common, run


def test_write_provenance_upserts_and_preserves_other_series(tmp_path):
    p = str(tmp_path / "prov.json")
    common.write_provenance("a", {"v": 1}, p)
    common.write_provenance("b", {"v": 2}, p)
    common.write_provenance("a", {"v": 3}, p)
    assert json.load(open(p)) == {"a": {"v": 3}, "b": {"v": 2}}
    assert not (tmp_path / "prov.json.tmp").exists()


def test_fetch_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    class Resp:
        headers = {"Last-Modified": "Fri, 10 Jan 2025 04:48:46 GMT"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("boom")
        return Resp()

    monkeypatch.setattr(common.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    f = common.fetch("http://x", retries=3)
    assert f.content == b"ok" and calls["n"] == 3 and f.last_modified == "2025-01-10T04:48:46+00:00"
    assert f.sha256 == common.sha256_hex(b"ok")


def test_fetch_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(common.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down")))
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.URLError):
        common.fetch("http://x", retries=2)


def test_run_main_exit_codes_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "CLIMATE_DIR", str(tmp_path))
    ok = common.RunReport("good")
    ok.deviate("stale")
    monkeypatch.setitem(run.SOURCES, "noaa_gml", lambda: ok)

    def boom():
        raise RuntimeError("source down")

    monkeypatch.setitem(run.SOURCES, "berkeley_earth", boom)
    assert run.main(["--source", "all"]) == 1  # one failed source -> non-zero, the other still reported
    s = json.loads((tmp_path / "last_run.json").read_text())
    assert s["sources"]["noaa_gml"]["deviations"] == ["stale"] and "RuntimeError" in s["failures"]["berkeley_earth"]
    assert run.main(["--source", "noaa_gml"]) == 0


def test_last_run_json_written_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "CLIMATE_DIR", str(tmp_path))
    monkeypatch.setitem(run.SOURCES, "noaa_gml", lambda: common.RunReport("noaa_gml"))
    assert run.main(["--source", "noaa_gml"]) == 0
    assert json.loads((tmp_path / "last_run.json").read_text())["failures"] == {}
    assert not (tmp_path / "last_run.json.tmp").exists()


def test_write_json_atomic_leaves_old_file_if_serialization_fails(tmp_path):
    p = str(tmp_path / "x.json")
    common.write_json_atomic({"ok": 1}, p)
    with pytest.raises(TypeError):
        common.write_json_atomic({"bad": object()}, p)
    assert json.load(open(p)) == {"ok": 1}  # previous complete file intact, not truncated


def test_require_contiguous_years():
    common.require_contiguous_years([1, 2, 3], 1, 3, "x")
    with pytest.raises(ValueError, match="x: 1 missing year"):
        common.require_contiguous_years([1, 3], 1, 3, "x")


def test_all_runs_active_sources_only_and_never_the_shelved_edgar(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "CLIMATE_DIR", str(tmp_path))
    called = []
    for name in run.SOURCES:  # stub EVERY registered source: a source added later must not make this test hit the network/disk
        monkeypatch.setitem(run.SOURCES, name, lambda n=name: called.append(n) or common.RunReport(n))
    assert run.main(["--source", "all"]) == 0
    assert sorted(called) == sorted([*run.ACTIVE_SOURCES, *run.DERIVED_SOURCES])  # sources, then the derived harmonize stage
    assert called.index("harmonize") > max(called.index(n) for n in run.ACTIVE_SOURCES)  # derived runs after every source
    assert "edgar" in run.INTERNAL_SOURCES and "edgar" not in run.ACTIVE_SOURCES and "edgar" not in called


def test_explicit_edgar_run_warns_that_it_is_internal_only(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(run, "CLIMATE_DIR", str(tmp_path))
    monkeypatch.setitem(run.SOURCES, "edgar", lambda: common.RunReport("edgar"))
    with caplog.at_level("WARNING"):
        assert run.main(["--source", "edgar"]) == 0
    assert any("shelved for publication" in r.message for r in caplog.records)


def test_edgar_defaults_write_outside_the_published_store():
    import inspect

    from pipeline import edgar

    params = inspect.signature(edgar.run).parameters
    for name in ("out_dir", "provenance_path"):
        default = params[name].default
        assert default.startswith(common.INTERNAL_DIR) and not default.startswith(common.CLIMATE_DIR)


def test_build_notification_priorities_and_message():
    ok = {"sources": {"noaa_gml": {"records": {"a": 276, "b": 822}, "deviations": [], "notes": ["n1"]}}, "failures": {}}
    assert run.build_notification(ok)[:2] == ("default", "Area 2 pipeline: OK")
    dev = {"sources": {"owid": {"records": {"x": 5}, "deviations": ["stale file"], "notes": []}}, "failures": {}}
    p, t, m = run.build_notification(dev)
    assert p == "high" and "deviations flagged" in t and "DEVIATION owid: stale file" in m and "owid 5" in m
    bad = {"sources": {}, "failures": {"primap_hist": "ValueError: MD5 mismatch " + "x" * 400}}
    p, t, m = run.build_notification(bad)
    assert p == "urgent" and "FAILED" in t and "FAILED primap_hist" in m and len(m) < 3500
    assert max(len(line) for line in m.splitlines()) < 300  # long errors are truncated for the push


def test_main_writes_notification_files_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "CLIMATE_DIR", str(tmp_path))
    rep = common.RunReport("noaa_gml")
    rep.deviate("something off")
    monkeypatch.setitem(run.SOURCES, "noaa_gml", lambda: rep)
    assert run.main(["--source", "noaa_gml"]) == 0
    assert (tmp_path / "last_run.priority").read_text().strip() == "high"
    assert "deviations flagged" in (tmp_path / "last_run.title").read_text()
    assert "DEVIATION noaa_gml: something off" in (tmp_path / "last_run.message").read_text()
    assert not list(tmp_path.glob("*.tmp"))
