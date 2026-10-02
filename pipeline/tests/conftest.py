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
        "% Berkeley fixture",
        "% The land analysis was run on 04-Jan-2025 19:11:11",
        "% The ocean analysis was published on 06-Jan-2025 11:47:59",
        "%   Using air temperature above sea ice:   14.102 +/- 0.019",
        "%   Using water temperature below sea ice: 14.698 +/- 0.019",
        "% Year, Annual Anomaly, Annual Unc., Five-year Anomaly, Five-year Unc., Annual Anomaly, Annual Unc., Five-year Anomaly, Five-year Unc.",
        "",
    ]
    for y in range(1850, 2025):
        # anomaly: -0.4 for 1850-1900, then rising 0.02/yr -- known offset of exactly -0.4
        a = -0.4 if y <= 1900 else -0.4 + (y - 1900) * 0.02
        lines.append(f"  {y}      {a:.3f}        0.100              NaN             NaN            {a - 0.1:.3f}        0.100              NaN             NaN")
    return "\n".join(lines) + "\n"
