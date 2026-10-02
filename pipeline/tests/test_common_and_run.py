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
