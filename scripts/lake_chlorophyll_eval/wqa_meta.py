"""docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md: the Water Quality Archive (WQA) read without its values.

Before the statement is approved, the harness may ask the WQA which sampling points have chlorophyll-a results and on
which dates. It may never read a result. Every WQA response that can carry a result goes through `keep_only` (CSV
rows) or `keep_only_jsonld` (JSON-LD members) before anything else touches it. They keep the columns in KEEP and
nothing else: no result, no qualifier ("<", ">"), no bound, no flag. A parsed frame is checked by `assert_no_values`
before it is printed, saved or logged.

Every request goes through `client()`, a net.Capped (scripts/lake_algae_sat_eval) limited to the EA host: one request
at a time, at least 1 second apart, a 60-second timeout, stop on HTTP 429, any 5xx or any other status not 200, a
ledger line per request, no credentials. Its caps for the selection step are in META_* below.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lake_algae_sat_eval"))
import net  # noqa: E402

API = "https://environment.data.gov.uk/water-quality"
HOST = "environment.data.gov.uk"
USER_AGENT = "swimsignal-lake-chlorophyll-eval/1"
# The selection step (select_lakes.py): metadata and dates only, at most 200 requests and 100 MB over all its runs.
META_MAX_REQUESTS_TOTAL = 200
META_MAX_BYTES_TOTAL = 100 * 1024**2
META_MAX_REQUESTS_PER_RUN = 200
META_MAX_BYTES_PER_RUN = 100 * 1024**2
CSV_LIMIT = 2500        # the service's page limit for CSV (API description, /data/observation)

# The only columns a parsed WQA observation keeps. Everything else, the result first, is dropped on parsing.
KEEP = {
    "samplingPoint.notation": "wqa_point",
    "samplingPoint.prefLabel": "point_label",
    "samplingPoint.easting": "easting",
    "samplingPoint.northing": "northing",
    "samplingPoint.samplingPointType": "point_type",
    "phenomenonTime": "sample_time",
    "determinand.notation": "determinand",
    "unit": "unit",
    "samplingPurpose": "purpose",
    "sampleMaterialType": "material",
}
KEPT = tuple(KEEP.values())
# Words that mark a column as a result. A kept column must not contain any of them (assert_no_values).
VALUE_WORDS = ("result", "value", "qualifier", "bound", "flag", "numeric", "simple")


class ValueLeak(RuntimeError):
    """A parsed WQA frame holds a column that is not in KEEP: stop before anything is printed or saved."""


class Capped(net.Capped):
    """net.Capped with the EA host as the only host. Pace, timeout, stop rules and ledger are net.Capped's."""

    def _check_url(self, url: str, headers: dict | None) -> None:
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != HOST or not u.path.startswith("/water-quality"):
            raise net.CapReached(f"host not allowed: {u.scheme}://{u.hostname}{u.path}")
        bad = {k.lower() for k in (headers or {})} & {"authorization", "cookie", "x-api-key"}
        if bad:
            raise net.CapReached(f"credentials refused: {sorted(bad)}")


def client(ledger: Path, http=None, sleep=None) -> Capped:
    if http is None:
        import httpx
        http = httpx.Client(timeout=net.TIMEOUT_S, follow_redirects=False, headers={"User-Agent": USER_AGENT})
    kw = {"sleep": sleep} if sleep is not None else {}
    return Capped(ledger=ledger, client=http, max_requests=META_MAX_REQUESTS_PER_RUN,
                  max_bytes=META_MAX_BYTES_PER_RUN, max_requests_total=META_MAX_REQUESTS_TOTAL,
                  max_bytes_total=META_MAX_BYTES_TOTAL, **kw)


def url(path: str, **params) -> str:
    q = {k: v for k, v in params.items() if v is not None}
    return f"{API}{path}" + (f"?{urlencode(q)}" if q else "")


def _norm(name: str) -> str:
    return name.strip().lstrip("﻿")


def keep_only(text: str) -> pd.DataFrame:
    """CSV observations -> only the KEEP columns, renamed. The other columns are never stored: each row is cut to
    KEEP as it is read. A header without samplingPoint.notation or phenomenonTime raises (names only, no row)."""
    rd = csv.reader(io.StringIO(text))
    try:
        header = [_norm(h) for h in next(rd)]
    except StopIteration:
        return pd.DataFrame(columns=list(KEPT))
    where = {KEEP[h]: i for i, h in enumerate(header) if h in KEEP}
    if "wqa_point" not in where or "sample_time" not in where:
        raise ValueLeak(f"unexpected CSV header (names only): {header}")
    rows = [{k: (r[i] if i < len(r) else None) for k, i in where.items()} for r in rd if r]
    out = pd.DataFrame(rows, columns=list(KEPT))
    assert_no_values(out)
    return out


def _get(d: dict | None, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def keep_only_jsonld(members: list[dict]) -> pd.DataFrame:
    """JSON-LD observation members -> the same columns as keep_only. hasResult and hasSimpleResult are never read."""
    rows = []
    for o in members:
        sp = o.get("hasSamplingPoint") or {}
        rows.append({
            "wqa_point": _get(sp, "notation"), "point_label": _get(sp, "prefLabel"),
            "easting": None, "northing": None,
            "point_type": _get(sp, "samplingPointType", "notation"),
            "sample_time": o.get("phenomenonTime"),
            "determinand": _get(o, "observedProperty", "notation") if isinstance(o.get("observedProperty"), dict)
            else None,
            "unit": o.get("hasUnit") if isinstance(o.get("hasUnit"), str) else None,
            "purpose": _get(o, "hasSample", "isResultOf", "samplingPurpose", "notation"),
            "material": _get(o, "hasSample", "sampleMaterialType", "notation"),
        })
    out = pd.DataFrame(rows, columns=list(KEPT))
    assert_no_values(out)
    return out


def assert_no_values(df: pd.DataFrame) -> None:
    """The check before anything is printed, saved or logged: only KEEP's columns, none named like a result."""
    extra = [c for c in df.columns if c not in KEPT]
    named = [c for c in df.columns if any(w in c.lower() for w in VALUE_WORDS)]
    if extra or named:
        raise ValueLeak(f"columns not allowed: {sorted(set(extra) | set(named))}")

