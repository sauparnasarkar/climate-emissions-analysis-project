"""EDGAR (European Commission / JRC) total-GHG and gas-split ingestion. Release 21, Phase 1.1b.

The combined `EDGAR_AR5_GHG` workbook has country totals only, so the gas split is built from
EDGAR's separate per-gas files -- fossil CO2 (`IEA_EDGAR_CO2`), CH4, N2O (Gg x IPCC AR5 GWP-100)
and F-gases (the `AR5g` file, already CO2-equivalent) -- then **summed and reconciled against the
combined workbook's total** (`SPEC.md` §5.26 decision 19). Results, per year, are published in the
output and provenance; a global residual beyond `RECON_TOLERANCE_PCT` in a year where every gas
is available raises a deviation.

The release is discovered from EDGAR's directory listing (latest `EDGAR_<year>_GHG`), and coverage
years come from the files themselves, so the yearly release cadence needs no code change.

Known gaps in the 2026 release, handled explicitly rather than papered over:
- the per-gas F-gas file has no data for 1970-1989 or for the latest year (2025), although its
  header advertises 1990-2025; in those years `fgas_mtco2e` is an explicit null, the composition's
  total still comes from the combined workbook, and reconciliation is skipped (noted, not alerted);
- a small, stable residual (~ -0.4% of the total in 1990-2024) between the per-gas sum and the
  combined total is unexplained by the files; it is reported, not adjusted away.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from .common import (
    CLIMATE_DIR,
    PROVENANCE_PATH,
    ROOT,
    RunReport,
    fetch,
    require_contiguous_years,
    write_csv_atomic,
    write_provenance,
)
from .crosswalk import BUNKER_CODES, build_crosswalk, expanded_gaps

EDGAR_ROOT = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/"
SHEET = "TOTALS BY COUNTRY"

# IPCC AR5 GWP-100 (no climate-carbon feedbacks), the basis of EDGAR's own GWP_100_AR5_GHG totals.
GWP_AR5 = {"ch4": 28, "n2o": 265}
RECON_TOLERANCE_PCT = 1.0  # |global residual| above this, in a fully-covered year, raises a deviation
MAX_LAG_YEARS = 2

FILE_PATTERNS = {
    "co2": r"IEA_EDGAR_CO2_(\d{4})_(\d{4})\.zip",
    "ch4": r"EDGAR_CH4_(\d{4})_(\d{4})\.zip",
    "n2o": r"EDGAR_N2O_(\d{4})_(\d{4})\.zip",
    "fgas": r"EDGAR_AR5g_F-gases_(\d{4})_(\d{4})\.zip",
    "total": r"EDGAR_AR5_GHG_(\d{4})_(\d{4})\.zip",
}

SERIES_COUNTRY = "edgar_country_annual"
SERIES_GLOBAL = "edgar_global_composition_annual"
SERIES_CROSSWALK = "country_crosswalk"


# ---------------------------------------------------------------- discovery


def discover_release(root_html: str) -> str:
    """Latest `EDGAR_<year>_GHG` directory name in EDGAR's dataset listing."""
    years = [int(y) for y in re.findall(r'href="EDGAR_(\d{4})_GHG/?"', root_html)]
    if not years:
        raise ValueError("EDGAR listing: no EDGAR_<year>_GHG release directory found")
    return f"EDGAR_{max(years)}_GHG"


def find_files(release_html: str) -> dict[str, str]:
    """File names for the five inputs in a release directory listing."""
    out = {}
    for key, pat in FILE_PATTERNS.items():
        hits = re.findall(r'href="(%s)"' % pat, release_html)
        if not hits:
            raise ValueError(f"EDGAR release listing: no file matching {pat!r}")
        out[key] = max(h[0] for h in hits)  # the longest-range / latest-named file if several
    return out


# ---------------------------------------------------------------- parsing


def read_totals(zip_bytes: bytes) -> tuple[pd.DataFrame, dict[str, str]]:
    """The TOTALS BY COUNTRY sheet as (wide frame: ISO3 x year, in Gg; ISO3 -> entity name).
    The header row is located by content (`Country_code_A3`), not by position."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        member = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        raw = pd.read_excel(io.BytesIO(z.read(member)), sheet_name=SHEET, header=None)
    hdr_rows = raw.index[(raw == "Country_code_A3").any(axis=1)]
    if len(hdr_rows) == 0:
        raise ValueError(f"EDGAR workbook: 'Country_code_A3' header not found in {SHEET!r}")
    h = hdr_rows[0]
    df = raw.iloc[h + 1 :].copy()
    df.columns = [str(c) for c in raw.iloc[h].tolist()]
    df = df.dropna(subset=["Country_code_A3"])
    ycols = [c for c in df.columns if re.fullmatch(r"Y_\d{4}", c)]
    if not ycols:
        raise ValueError("EDGAR workbook: no Y_<year> columns")
    names = df.drop_duplicates("Country_code_A3").set_index("Country_code_A3")["Name"].to_dict()
    wide = df.groupby("Country_code_A3")[ycols].sum(min_count=1).astype(float)
    wide.columns = [int(c[2:]) for c in wide.columns]
    return wide, names


# ---------------------------------------------------------------- tables


def _ranges(years: list[int]) -> str:
    years = sorted(years)
    out, start, prev = [], None, None
    for y in years:
        if start is None:
            start = prev = y
        elif y == prev + 1:
            prev = y
        else:
            out.append((start, prev))
            start = prev = y
    if start is not None:
        out.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def build_tables(gas: dict[str, pd.DataFrame], total: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(country-year table, global composition table), all in MtCO2e. `gas` has co2/ch4/n2o/fgas
    wide frames in Gg (CH4/N2O raw mass; fgas already CO2e); `total` is the combined workbook."""
    idx, years = total.index, list(total.columns)
    for k in ("co2", "ch4", "n2o"):
        missing = [y for y in years if y not in gas[k].columns]
        if missing:
            raise ValueError(f"EDGAR {k} file lacks year(s) present in the combined total: {_ranges(missing)}")

    def al(df):
        return df.reindex(index=idx, columns=years)

    co2 = al(gas["co2"]).fillna(0) / 1000
    ch4 = al(gas["ch4"]).fillna(0) * GWP_AR5["ch4"] / 1000
    n2o = al(gas["n2o"]).fillna(0) * GWP_AR5["n2o"] / 1000
    fg_raw = al(gas["fgas"])
    fgas_year = fg_raw.notna().any(axis=0)  # a year is covered if any entity has an F-gas value
    # Per-year mask broadcast across entities (DataFrame.where would align a Series mask on rows).
    covered = np.tile(fgas_year.to_numpy(), (len(idx), 1))
    fgas = pd.DataFrame(np.where(covered, fg_raw.fillna(0).to_numpy(), np.nan), index=idx, columns=years) / 1000
    tot = al(total) / 1000

    comp = co2 + ch4 + n2o + fgas  # NaN wherever F-gases are unavailable for the year
    resid = comp - tot

    def long(df, name):
        s = df.stack(future_stack=True)
        s.index.names = ["iso3", "year"]
        return s.rename(name)

    country = pd.concat(
        [long(co2, "co2_mt"), long(ch4, "ch4_mtco2e"), long(n2o, "n2o_mtco2e"), long(fgas, "fgas_mtco2e"),
         long(tot, "total_ghg_mtco2e"), long(comp, "components_sum_mtco2e"), long(resid, "residual_mtco2e")],
        axis=1,
    ).reset_index()
    country = country.assign(year=country["year"].astype(int))
    country = country.assign(
        entity_type=country["iso3"].map(lambda c: "bunker" if c in BUNKER_CODES else "country"),
        fgas_available=country["year"].map(fgas_year.to_dict()).astype(bool),
    )

    bunker = idx.isin(list(BUNKER_CODES))
    g = pd.DataFrame(
        {
            "year": years,
            "co2_mt": co2.sum().values,
            "ch4_mtco2e": ch4.sum().values,
            "n2o_mtco2e": n2o.sum().values,
            "fgas_mtco2e": fgas.sum(min_count=1).values,
            "total_ghg_mtco2e": tot.sum().values,
            "bunkers_mtco2e": tot[bunker].sum().values,
            "national_total_mtco2e": tot[~bunker].sum().values,
        }
    )
    comp_sum = g[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1, min_count=4)
    g = g.assign(
        components_sum_mtco2e=comp_sum,
        residual_mtco2e=comp_sum - g["total_ghg_mtco2e"],
        residual_pct=(comp_sum - g["total_ghg_mtco2e"]) / g["total_ghg_mtco2e"] * 100,
        fgas_available=g["fgas_mtco2e"].notna(),
    )
    return country.round(6), g.round(6)


def reconcile(g: pd.DataFrame, report: RunReport) -> None:
    """Deviation if the per-gas sum strays beyond tolerance from the combined total in a year
    where every gas is available; known F-gas-missing years are noted, not alerted."""
    covered = g[g["fgas_available"]]
    bad = covered[covered["residual_pct"].abs() > RECON_TOLERANCE_PCT]
    if len(bad):
        worst = bad.loc[bad["residual_pct"].abs().idxmax()]
        report.deviate(
            f"per-gas sum differs from the combined EDGAR total by more than {RECON_TOLERANCE_PCT}% in {_ranges(bad['year'].astype(int).tolist())} "
            f"(worst {int(worst['year'])}: {worst['residual_pct']:.2f}%)"
        )
    if len(covered):
        report.note(
            f"per-gas sum vs combined total, years with all four gases ({int(covered['year'].min())}-{int(covered['year'].max())}): "
            f"global residual {covered['residual_pct'].min():.2f}% to {covered['residual_pct'].max():.2f}% (not adjusted)"
        )
    gap = g.loc[~g["fgas_available"], "year"].astype(int).tolist()
    if gap:
        report.note(f"F-gas per-gas file has no data for {_ranges(gap)}: fgas_mtco2e is null there and reconciliation is skipped; total_ghg comes from the combined workbook")


# ---------------------------------------------------------------- run


def _default_owid_and_expanded(root: str = ROOT):
    owid_path = os.path.join(root, "data", "owid-co2-data.csv")
    sel_path = os.path.join(root, "data", "selected_countries.json")
    owid = pd.read_csv(owid_path, usecols=["country", "iso_code"]) if os.path.exists(owid_path) else None
    expanded = json.load(open(sel_path)).get("expanded") if os.path.exists(sel_path) else None
    return owid, expanded


def run(fetcher=fetch, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None, owid=None, expanded=None, root_url: str = EDGAR_ROOT) -> RunReport:
    today = today or date.today()
    report = RunReport("edgar")

    root_page = fetcher(root_url)
    release = discover_release(root_page.text())
    rel_url = f"{root_url}{release}/"
    files = find_files(fetcher(rel_url).text())
    fetched = {k: fetcher(rel_url + name) for k, name in files.items()}

    wide, names = {}, {}
    for k, f in fetched.items():
        wide[k], names_k = read_totals(f.content)
        names.update(names_k)
    for k, w in wide.items():
        if not w.columns.is_monotonic_increasing:
            raise ValueError(f"EDGAR {k}: years out of order")
        require_contiguous_years(w.columns, int(w.columns.min()), int(w.columns.max()), f"EDGAR {k}")

    country, glob = build_tables(wide, wide["total"])
    latest = int(glob["year"].max())
    if today.year - latest > MAX_LAG_YEARS:
        report.deviate(f"latest EDGAR year is {latest}, more than {MAX_LAG_YEARS} years behind {today.year}")
    reconcile(glob, report)

    if owid is None and expanded is None:
        owid, expanded = _default_owid_and_expanded()
    crosswalk = None
    if owid is not None:
        crosswalk = build_crosswalk({c: names[c] for c in wide["total"].index}, owid, expanded)
        if expanded:
            gaps = expanded_gaps(crosswalk, expanded)
            if gaps:
                report.deviate(f"expanded-set countries without an exact ISO3 match in EDGAR: {', '.join(gaps)}")
        report.note(f"crosswalk: {crosswalk['match'].value_counts().to_dict()}")
        if crosswalk.attrs.get("excluded_owid_codes"):
            report.note(f"OWID non-ISO3 codes excluded from the crosswalk: {', '.join(crosswalk.attrs['excluded_owid_codes'])}")
    else:
        report.deviate("country crosswalk not built: data/owid-co2-data.csv not found")

    write_csv_atomic(country, os.path.join(out_dir, "edgar_country_annual.csv"))
    write_csv_atomic(glob, os.path.join(out_dir, "edgar_global_composition_annual.csv"))
    report.count(SERIES_COUNTRY, len(country))
    report.count(SERIES_GLOBAL, len(glob))
    if crosswalk is not None:
        write_csv_atomic(crosswalk, os.path.join(out_dir, "country_crosswalk.csv"))
        report.count(SERIES_CROSSWALK, len(crosswalk))

    first = int(glob["year"].min())
    common_meta = {
        "source": f"EDGAR {release} (European Commission / JRC): IEA-EDGAR CO2, EDGAR CH4, N2O, F-gases; combined AR5 totals",
        "source_urls": [rel_url + n for n in files.values()],
        "retrieved_at": fetched["total"].retrieved_at,
        "source_release": {"release": release, "files": files},
        "raw_sha256": {k: f.sha256 for k, f in fetched.items()},
        "coverage": [first, latest],
        "units": "MtCO2e (CO2 in Mt; CH4/N2O converted with IPCC AR5 GWP-100: CH4 28, N2O 265; F-gases from EDGAR's AR5g CO2e file)",
        "gas_scope": "CO2 (fossil, excl. short-cycle biogenic), CH4, N2O, F-gases; excludes LULUCF",
        "update_cadence": "annual release (EDGAR_<year>_GHG); pipeline runs monthly and discovers the latest release",
        "license": (
            "EDGAR: CC BY 4.0 (European Union). CAUTION: the IEA-EDGAR CO2 component (fuel-combustion CO2) is based on IEA data licensed "
            "CC BY-NC-ND 4.0; the workbook asks users of IEA-EDGAR CO2 data to contact the IEA (compliance@iea.org) for permission to use. "
            "Review before public/derivative use."
        ),
    }
    write_provenance(
        SERIES_GLOBAL,
        {
            **common_meta,
            "geography": "global (sum of all EDGAR entities, international aviation/shipping included)",
            "reconciliation": {
                "tolerance_pct": RECON_TOLERANCE_PCT,
                "fgas_unavailable_years": glob.loc[~glob["fgas_available"], "year"].astype(int).tolist(),
                "residual_pct_by_year": {int(y): (None if pd.isna(r) else round(float(r), 4)) for y, r in zip(glob["year"], glob["residual_pct"])},
            },
            "methodology": "Per-gas files summed in CO2e and checked against the combined EDGAR AR5 total per year. total_ghg_mtco2e is the combined workbook's figure; components_sum is the per-gas sum; residual is components_sum minus total.",
            "caveats": [
                "F-gas per-gas data is unavailable for 1970-1989 and for the latest year in the 2026 release; fgas_mtco2e is null there (no interpolation).",
                "A small stable residual (about -0.4% in 1990-2024) between the per-gas sum and the combined total is unexplained by the files.",
                "Differences of roughly 5-8% from OWID/GCP fossil CO2 are expected (scope boundaries, bunkers, cement/process, methodology, vintage) and are disclosed, not reconciled.",
            ],
            "rows": len(glob),
        },
        provenance_path,
    )
    write_provenance(
        SERIES_COUNTRY,
        {
            **common_meta,
            "geography": "country/territory entities by ISO3 plus bunkers (entity_type='bunker': AIR, SEA)",
            "methodology": "Same construction as the global series, per entity. national_total (global series) excludes AIR/SEA so country shares sum to 100% of national emissions.",
            "caveats": ["Entities absent from a per-gas file are treated as zero for that gas; the F-gas file covers fewer entities than the others."],
            "rows": len(country),
        },
        provenance_path,
    )
    if crosswalk is not None:
        write_provenance(
            SERIES_CROSSWALK,
            {
                "source": "Derived: EDGAR entity list x OWID iso_code/country",
                "retrieved_at": fetched["total"].retrieved_at,
                "methodology": "Matched on ISO3; unmatched entities and many-to-one cases flagged from the data's own names (see pipeline/crosswalk.py). Rebuilt every run.",
                "match_counts": crosswalk["match"].value_counts().to_dict(),
                "license": "Derived metadata",
                "rows": len(crosswalk),
            },
            provenance_path,
        )
    return report
