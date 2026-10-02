"""Run Area 2 ingestion: `python -m pipeline.run [--source noaa_gml|berkeley_earth|all]`.

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

from . import berkeley_earth, edgar, noaa_gml
from .common import CLIMATE_DIR, utc_now, write_json_atomic

SOURCES = {
    "noaa_gml": noaa_gml.run,
    "berkeley_earth": berkeley_earth.run,
    "edgar": edgar.run,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    selected = list(SOURCES) if args.source == "all" else [args.source]
    summary: dict = {"started_at": utc_now(), "sources": {}, "failures": {}}
    for name in selected:
        try:
            summary["sources"][name] = SOURCES[name]().as_dict()
        except Exception as exc:  # noqa: BLE001 -- one source failing must not hide the others' results
            summary["failures"][name] = f"{type(exc).__name__}: {exc}"
            logging.error("%s failed:\n%s", name, traceback.format_exc())
    summary["finished_at"] = utc_now()

    os.makedirs(CLIMATE_DIR, exist_ok=True)
    write_json_atomic(summary, os.path.join(CLIMATE_DIR, "last_run.json"))
    n_dev = sum(len(s["deviations"]) for s in summary["sources"].values())
    print(f"pipeline: {len(summary['sources'])} ok, {len(summary['failures'])} failed, {n_dev} deviation(s)")
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
