"""Run Area 2 ingestion: `python -m pipeline.run [--source noaa_gml|berkeley_earth|primap_hist|owid|harmonize|correlate|composition|country_share|ets_baseline|all]`.

`all` runs the active (publishable) sources, then the derived stages (the harmonized layer), only. Shelved sources (`edgar`) run only when named explicitly
and write to `data/internal/`, never `data/climate/`.

Writes normalized series to `data/climate/` plus `data/climate/provenance.json` and a
`last_run.json` summary (records processed, deviations) the refresh job logs and alerts on.
Exit status: 0 = every selected source ran (deviations are warnings, listed in the summary);
1 = at least one source failed outright (download or parse error).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

from . import berkeley_earth, composition, correlation, country_share, edgar, ets_baseline, harmonize, noaa_gml, owid, primap_hist
from .common import CLIMATE_DIR, check_reshape_environment, utc_now, write_json_atomic, write_text_atomic

ACTIVE_SOURCES = {
    "noaa_gml": noaa_gml.run,
    "berkeley_earth": berkeley_earth.run,
    "primap_hist": primap_hist.run,
    "owid": owid.run,
}
# Shelved for publication (licence): explicit opt-in only, internal output directory.
INTERNAL_SOURCES = {
    "edgar": edgar.run,
}
# Derived stages read what the source steps wrote and run after them in `all` (the harmonized layer).
DERIVED_SOURCES = {
    "harmonize": harmonize.run,
    "correlate": correlation.run,
    "composition": composition.run,
    "country_share": country_share.run,
    "ets_baseline": ets_baseline.run,
}
SOURCES = {**ACTIVE_SOURCES, **DERIVED_SOURCES, **INTERNAL_SOURCES}
# A derived stage that consumes one upstream stage's artifact as a whole must not run when that stage failed in the same run: it would build a
# fresh-looking result (new generated_at) from the previous run's artifact. `correlate` reads exactly what `harmonize` wrote. (harmonize itself is
# deliberately NOT gated on the sources: it merges several independent sources, a partial update is normal, and each source's age is in its provenance.)
DEPENDS_ON = {"correlate": ("harmonize",), "composition": ("primap_hist",), "country_share": ("owid", "primap_hist"), "ets_baseline": ("owid",)}  # composition reads the primap_hist artifact as a whole


def build_notification(summary: dict) -> tuple[str, str, str]:
    """(priority, title, message) for the refresh job's ntfy push, so the shell script needs no JSON
    parsing. urgent = a source failed outright; high = deviations from norm; default = clean."""
    n_ok, n_fail = len(summary["sources"]), len(summary["failures"])
    devs = [(s, d) for s, r in summary["sources"].items() for d in r["deviations"]]
    if n_fail:
        priority, title = "urgent", "Area 2 pipeline: FAILED"
    elif devs:
        priority, title = "high", "Area 2 pipeline: deviations flagged"
    else:
        priority, title = "default", "Area 2 pipeline: OK"
    lines = [f"{n_ok} source(s) ok, {n_fail} failed, {len(devs)} deviation(s)."]
    for name, err in summary["failures"].items():
        lines.append(f"FAILED {name}: {err[:240]}")
    for name, d in devs:
        lines.append(f"DEVIATION {name}: {d[:240]}")
    rec = "; ".join(f"{s} " + "/".join(str(n) for n in r["records"].values()) for s, r in summary["sources"].items() if r["records"])
    if rec:
        lines.append(f"Rows: {rec}.")
    n_notes = sum(len(r.get("notes", [])) for r in summary["sources"].values())
    lines.append(f"{n_notes} note(s) in data/climate/last_run.json.")
    return priority, title, "\n".join(lines)[:3500]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    selected = [*ACTIVE_SOURCES, *DERIVED_SOURCES] if args.source == "all" else [args.source]
    for name in selected:
        if name in INTERNAL_SOURCES:
            logging.warning("%s is shelved for publication: running for internal validation only (output in data/internal/)", name)
    summary: dict = {"started_at": utc_now(), "sources": {}, "failures": {}}
    env_problem = check_reshape_environment()
    if env_problem:  # reported like any other deviation (priority high in the push), never fatal
        logging.warning("environment: DEVIATION: %s", env_problem)
        summary["sources"]["environment"] = {"records": {}, "deviations": [env_problem], "notes": []}
    for name in selected:
        blocked = [d for d in DEPENDS_ON.get(name, ()) if d in summary["failures"]]
        if blocked:
            summary["failures"][name] = f"skipped: upstream stage(s) failed in this run: {', '.join(blocked)} (its last good output is left untouched)"
            logging.error("%s skipped: upstream %s failed", name, ", ".join(blocked))
            continue
        try:
            summary["sources"][name] = SOURCES[name]().as_dict()
        except Exception as exc:  # noqa: BLE001 -- one source failing must not hide the others' results
            summary["failures"][name] = f"{type(exc).__name__}: {exc}"
            logging.error("%s failed:\n%s", name, traceback.format_exc())
    summary["finished_at"] = utc_now()

    os.makedirs(CLIMATE_DIR, exist_ok=True)
    write_json_atomic(summary, os.path.join(CLIMATE_DIR, "last_run.json"))
    priority, title, message = build_notification(summary)
    for name, value in (("priority", priority), ("title", title), ("message", message)):
        write_text_atomic(value + "\n", os.path.join(CLIMATE_DIR, f"last_run.{name}"))
    n_dev = sum(len(s["deviations"]) for s in summary["sources"].values())
    print(f"pipeline: {len(summary['sources'])} ok, {len(summary['failures'])} failed, {n_dev} deviation(s)")
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
