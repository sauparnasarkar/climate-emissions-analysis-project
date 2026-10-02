"""Shared plumbing for the Area 2 ingestion scripts (Release 21, Phase 1.1).

Every source script does the same four things -- fetch, parse, validate, record provenance --
so the generic parts live here: a retrying downloader, a sha256 helper, a provenance store
(one JSON file, one entry per normalized series) and a `RunReport` that collects the
"records processed" counts and "deviations from norm" the refresh job logs and alerts on.

Normalized output lands in `data/climate/` (gitignored, like the rest of `data/`), which is
the store `api/` will read from in Phase 1.2.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIMATE_DIR = os.path.join(ROOT, "data", "climate")
PROVENANCE_PATH = os.path.join(CLIMATE_DIR, "provenance.json")
# Sources that are shelved for publication (e.g. EDGAR, pending licence) write here, never to CLIMATE_DIR,
# so nothing the API reads can contain them.
INTERNAL_DIR = os.path.join(ROOT, "data", "internal")

log = logging.getLogger("pipeline")

USER_AGENT = "climate-emissions-pipeline/1.0 (+https://climate-analytics.syena.io)"


@dataclass
class Fetched:
    """A downloaded raw source file plus what the server told us about its vintage."""

    url: str
    content: bytes
    sha256: str
    retrieved_at: str  # ISO-8601 UTC
    last_modified: str | None  # ISO-8601 UTC from the Last-Modified header, if present

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, errors="replace")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str, retries: int = 3, timeout: int = 60, backoff: float = 2.0) -> Fetched:
    """Download `url`, retrying transient failures with exponential backoff. Raises the last
    error if every attempt fails -- a source being down must fail the run loudly rather than
    silently leaving yesterday's data in place."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                lm = resp.headers.get("Last-Modified")
            last_modified = None
            if lm:
                try:
                    last_modified = parsedate_to_datetime(lm).astimezone(timezone.utc).replace(microsecond=0).isoformat()
                except (TypeError, ValueError):
                    last_modified = None
            return Fetched(url, content, sha256_hex(content), utc_now(), last_modified)
        except Exception as exc:  # noqa: BLE001 -- retry on any transport/HTTP error
            last_exc = exc
            log.warning("fetch %s failed (attempt %d/%d): %s", url, attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff ** attempt)
    assert last_exc is not None
    raise last_exc


@dataclass
class RunReport:
    """What one source's run did: counts and anything outside the norm. Deviations are
    warnings the refresh job turns into alerts; they do not fail the run on their own
    (a source that is merely stale is still usable, it just must not be silent)."""

    source: str
    records: dict[str, int] = field(default_factory=dict)
    deviations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # known, expected data gaps: logged, never alerting

    def note(self, message: str) -> None:
        self.notes.append(message)
        log.info("%s: note: %s", self.source, message)

    def count(self, series_id: str, n: int) -> None:
        self.records[series_id] = n
        log.info("%s: %s -> %d rows", self.source, series_id, n)

    def deviate(self, message: str) -> None:
        self.deviations.append(message)
        log.warning("%s: DEVIATION: %s", self.source, message)

    def as_dict(self) -> dict:
        return {"source": self.source, "records": self.records, "deviations": self.deviations, "notes": self.notes}


def write_provenance(series_id: str, entry: dict, path: str = PROVENANCE_PATH) -> None:
    """Upsert one series' provenance entry. The file is rewritten atomically so a crashed
    run never leaves a half-written store the API would choke on."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    store: dict = {}
    if os.path.exists(path):
        with open(path) as f:
            store = json.load(f)
    store[series_id] = entry
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def require_contiguous_years(years, first: int, last: int, label: str) -> None:
    """Missing-year validation (an acceptance criterion of every ingestion phase): the series
    must cover `first..last` with no gaps. A gap raises rather than publishing an incomplete
    series -- the API returns explicit nulls for genuine source gaps, never a silently short one."""
    missing = sorted(set(range(first, last + 1)) - set(int(y) for y in years))
    if missing:
        shown = ", ".join(map(str, missing[:10])) + (" ..." if len(missing) > 10 else "")
        raise ValueError(f"{label}: {len(missing)} missing year(s) in {first}-{last}: {shown}")


def write_json_atomic(obj, path: str) -> None:
    """Write-then-replace, so an interrupted run can't leave truncated JSON for monitoring to read."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def write_csv_atomic(df, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
