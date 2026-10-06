"""Synthetic fixtures shaped like the real source files (no network in tests)."""

import pytest

from pipeline.common import Fetched


def make_fetched(url: str, text: str, last_modified: str | None = "2026-09-01T00:00:00+00:00") -> Fetched:
    data = text.encode("latin-1")
    return Fetched(url, data, "deadbeef", "2026-10-01T00:00:00+00:00", last_modified)


@pytest.fixture
def noaa_annual_text():
    rows = "\n".join(f"{y},{315.98 + (y - 1959) * 1.5:.2f},0.12" for y in range(1959, 2026))
    return "# comment line\n# another\n\nyear,mean,unc\n" + rows + "\n"


@pytest.fixture
def noaa_monthly_text():
    rows = []
    for y in range(1958, 2027):
        for m in range(1, 13):
            if (y, m) < (1958, 3) or (y, m) > (2026, 8):
                continue
            rows.append(f"{y},{m},{y + (m - 0.5) / 12:.4f},{315.0 + (y - 1958) * 1.5:.2f},{314.5 + (y - 1958) * 1.5:.2f},20,0.5,0.2")
    return "# comment\nyear,month,decimal date,average,deseasonalized,ndays,sdev,unc\n" + "\n".join(rows) + "\n"


@pytest.fixture
def law_text():
    # Preamble containing the words CO2/ppm (must be ignored), then the spline table.
    head = "Law Dome\nPrecision 0.1 ppm CO2\n\nDATA:\nColumn 1: Year AD\n\nYearAD CH4spl  GrwthRt NOAA04      YearAD  CO2spl  GrwthRt     YearAD  N2Ospl  GrwthRt\n"
    rows = []
    for y in range(1, 2005):
        co2 = 277.0 if y < 1750 else 277.0 + (y - 1750) * 0.2  # 1959 -> 318.8? keep simple, overridden below
        if y >= 1750:
            co2 = 277.0 + (y - 1750) * (315.7 - 277.0) / (1959 - 1750)
        rows.append(f"{y}  650.0  0.1  660.0  {y}.0  {co2:.1f}  0.1  {y}.0  264.0  0.0")
    return head + "\n".join(rows) + "\n\nEnd of file\n"


@pytest.fixture
def berkeley_text():
    lines = [
        "% PRELIMINARY DATA - SUBJECT TO CHANGE WITHOUT NOTICE - NOT YET PEER REVIEWED",
        "% Berkeley high-resolution fixture",
        "% The land analysis was run on 11-Sep-2026 19:47:26",
        "% The ocean analysis was published on 13-Aug-2026 16:15:21",
        "% Estimated Jan 1951-Dec 1980 global mean temperature (\u00b0C):",
        "%    14.107 +/- 0.0000.0000.0000.0000.0000.0000.0000.0000.0000.000",
        "% Land + Ocean temperature anomaly",
        "% Year, Annual Anomaly, Annual Unc., Five-year Anomaly, Five-year Unc.",
        "",
    ]
    for y in range(1850, 2026):
        # anomaly: -0.4 for 1850-1900, then rising 0.02/yr -- known offset of exactly -0.4
        a = -0.4 if y <= 1900 else -0.4 + (y - 1900) * 0.02
        lines.append(f"  {y}      {a:.3f}        0.100              NaN             NaN")
    return "\n".join(lines) + "\n"


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Unit tests must never touch the network (a test that did so silently downloaded 73 MB of
    PRIMAP-hist per run and only passed when the live site happened to be reachable). Tests that
    exercise `common.fetch` install their own fake `urlopen`, which takes precedence."""
    import urllib.request

    def blocked(*args, **kwargs):
        raise RuntimeError("real network access attempted inside a unit test -- stub the source or pass a fake fetcher")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)


@pytest.fixture(autouse=True)
def _neutral_reshape_canary(monkeypatch):
    """`pipeline.run.main` runs an environment canary that, on a stack with the numpy-2.2.6/Python-3.14 reshape bug,
    adds an 'environment' deviation. Tests of `main` must not depend on which stack they run on, so it is neutral here;
    the canary has its own tests that call `common.check_reshape_environment` directly."""
    import pipeline.run as run_module

    monkeypatch.setattr(run_module, "check_reshape_environment", lambda: None)
