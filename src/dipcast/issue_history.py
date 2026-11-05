"""The issued-forecast history: what each spot's page showed at each issue, kept as it was issued, and the
previous successful issue published for the pages to compare with (docs/ISSUED-HISTORY-2026-10.md).

One row per spot per issue, in a Parquet file per UTC month in the state directory (issued-2026-10.parquet),
so the history travels with the rest of the state: the Actions cache, and the rolling release the workflow
uploads twice a day. Each row:

* issue_id: the build's commit and the issue time in UTC to the minute, as the printed records say it
  (site/printed.js, issueId): 3ed1b5a-20261020T1216Z.
* issued_at, commit, source ("issued", the only kind this store takes), spot.
* record: the spot's record as JSON, made by the page's own rules at issue time (scripts/issue_records.cjs,
  since.js seenRecord): each day's level and what set it, the sewage spill risk, rain here, overflows expected
  to spill, missing rain data; right now; the live statuses and how many overflows gave one; the rating,
  sample, algae check and official advice; the model stamp without its code part.

Rows are only ever added. An issue already in the file is left alone when its rows are the same (a rerun) and
refused when they differ, so a record cannot be rewritten after the fact. A forecast reconstructed later for a
past time is not an issued one: append() refuses an issue time more than MAX_ISSUE_AGE before the clock, and
any reconstruction belongs in a store of its own, never here.

The comparison itself is the page's (since.js, lastSaid), from data/since-last.json: the previous issue's
records, its id and time; one more than MAX_PREVIOUS_AGE old is not compared with ("stale"). "Previous" is the
issue the site is showing while this build runs (`published_at`, read from the live spots-lite.json), not
merely the last one kept: a build that kept its records and then failed to deploy (a later workflow step, the
deploy job) was never seen, and a visitor must not be told what changed since an update they could not have
read. Where that issue is not kept (the history began after it, or its month's file was lost), there is no
comparison ("not kept"). Only where the live site could not be read does it fall back to the last issue kept,
and the build's health says so (`previous_checked`: "unverified").
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.request
from datetime import timedelta
from pathlib import Path

import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)
SCRIPT = config.ROOT / "scripts" / "issue_records.cjs"
MAX_ISSUE_AGE = timedelta(hours=6)       # an issue time further back than this is a reconstruction, not an issue
MAX_PREVIOUS_AGE = timedelta(hours=24)   # a previous issue older than this is not compared with
COLUMNS = ["issue_id", "issued_at", "commit", "source", "spot", "record"]


class HistoryError(ValueError):
    """A row the history must not take: a reconstruction, or a different record under an existing issue id."""


def issue_id(commit: str | None, issued_at: pd.Timestamp) -> str:
    """The id the printed records give an issue (printed.js, issueId): the commit, then the UTC minute."""
    return f"{commit or 'nogit'}-{issued_at.tz_convert('UTC'):%Y%m%dT%H%M}Z"


def month_file(issued_at: pd.Timestamp, state: Path | None = None) -> Path:
    return (state or config.STATE) / f"issued-{issued_at.tz_convert('UTC'):%Y-%m}.parquet"


def make_records(lite: Path) -> dict:
    """{issued_at, records: {spot id: record}} for a build's spots-lite.json, from the page's own rules (Node)."""
    out = subprocess.run(["node", str(SCRIPT), str(lite)], capture_output=True, text=True, check=True, timeout=120)
    return json.loads(out.stdout)


def _rows(doc: dict, commit: str | None) -> pd.DataFrame:
    at = pd.Timestamp(doc["issued_at"]).tz_convert("UTC")
    iid = issue_id(commit, at)
    return pd.DataFrame([{"issue_id": iid, "issued_at": at, "commit": commit or "nogit", "source": "issued", "spot": sid,
                          "record": json.dumps(rec, sort_keys=True, separators=(",", ":"))}
                         for sid, rec in sorted(doc["records"].items())], columns=COLUMNS)


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_parquet(path)
    df["issued_at"] = pd.to_datetime(df["issued_at"], utc=True)
    return df


def append(doc: dict, commit: str | None, now: pd.Timestamp | None = None, state: Path | None = None) -> dict:
    """Add one issue's records to its month's file. Refuses a reconstruction (an issue time more than
    MAX_ISSUE_AGE before `now`) and a different record under an issue id already kept; an identical rerun adds
    nothing. The file is written whole to a temporary name and moved into place, so a crash leaves the old one."""
    now = now or pd.Timestamp.now(tz="UTC")
    at = pd.Timestamp(doc["issued_at"]).tz_convert("UTC")
    if now - at > MAX_ISSUE_AGE:
        raise HistoryError(f"issue time {at:%Y-%m-%d %H:%M}Z is {now - at} before now: a reconstruction, not an issue")
    rows, path = _rows(doc, commit), month_file(at, state)
    old, iid = _read(path), issue_id(commit, at)
    kept = old[old["issue_id"] == iid]
    if len(kept):
        same = kept.sort_values("spot")[["spot", "record"]].reset_index(drop=True).equals(rows[["spot", "record"]].reset_index(drop=True))
        if not same:
            raise HistoryError(f"{iid} is already kept with different records: the history is never rewritten")
        return {"issue_id": iid, "spots": len(rows), "added": 0, "file": path.name, "bytes": path.stat().st_size}
    out = pd.concat([old, rows], ignore_index=True) if len(old) else rows
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, path)
    return {"issue_id": iid, "spots": len(rows), "added": len(rows), "file": path.name, "bytes": path.stat().st_size}


def previous(issued_at: pd.Timestamp, state: Path | None = None,
             published_at: pd.Timestamp | None = None) -> tuple[dict, pd.DataFrame]:
    """The issue to compare with, kept before `issued_at` (this month's file and last month's), as ({issue_id,
    issued_at}, its rows), or ({why}, empty). With `published_at`, the issue the site is showing, that one or
    "not kept"; without, the last one kept, or "first" where none is. "stale" where it is over MAX_PREVIOUS_AGE old."""
    at = issued_at.tz_convert("UTC")
    last_month = at.replace(day=1) - timedelta(days=1)
    df = pd.concat([_read(month_file(last_month, state)), _read(month_file(at, state))], ignore_index=True)
    df = df[df["issued_at"] < at]
    if published_at is not None:
        pub = published_at.tz_convert("UTC")
        if not (df["issued_at"] == pub).any():
            return {"why": "not kept", "published_at": pub.isoformat()}, df.iloc[0:0]
        df = df[df["issued_at"] == pub]
    if df.empty:
        return {"why": "first"}, df
    t = df["issued_at"].max()
    if at - t > MAX_PREVIOUS_AGE:
        return {"why": "stale", "latest_at": t.isoformat()}, df.iloc[0:0]
    rows = df[df["issued_at"] == t]
    return {"issue_id": rows["issue_id"].iloc[0], "issued_at": t.isoformat()}, rows


def since_last(doc: dict, commit: str | None, state: Path | None = None, published_at: pd.Timestamp | None = None) -> dict:
    """data/since-last.json: this issue's id and time, and the previous issue's id, time and records, or why
    there is none ("first", "stale"). The page compares its own forecast with these (since.js, lastSaid)."""
    at = pd.Timestamp(doc["issued_at"]).tz_convert("UTC")
    meta, rows = previous(at, state, published_at)
    prev = {"issue_id": meta["issue_id"], "issued_at": meta["issued_at"]} if "issue_id" in meta else None
    return {"issue_id": issue_id(commit, at), "issued_at": doc["issued_at"], "previous": prev,
            **({} if prev else {"why": meta["why"]}),
            "spots": {r.spot: json.loads(r.record) for r in rows.itertuples()}}


def published_issue(site_url: str, timeout: float = 20) -> pd.Timestamp | None:
    """The issue time of the forecast the live site is showing (its data/spots-lite.json), or None when it cannot be
    read. A query string of the clock's own makes the CDN ask the host rather than serve its ten-minute copy."""
    url = f"{site_url.rstrip('/')}/data/spots-lite.json?issued={pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%S}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return pd.Timestamp(json.load(r)["generated_at"]).tz_convert("UTC")
    except Exception as e:  # noqa: BLE001 - any failure means "not known", and the caller says so
        log.warning("live issue not read from %s: %s", url, e)
        return None


def record_and_publish(site: Path, commit: str | None, now: pd.Timestamp | None = None, state: Path | None = None,
                       keep: bool = True, published_at: pd.Timestamp | None = None) -> dict:
    """The build's step: this issue's records from site/data/spots-lite.json, the previous issue's into
    site/data/since-last.json (the one the site is showing, `published_at`, where it was read), then (keep) this
    issue added to the history. The previous one is read before the append, so it is never this issue. Returns
    the build's health entry."""
    doc = make_records(site / "data" / "spots-lite.json")
    out = since_last(doc, commit, state, published_at)
    (site / "data" / "since-last.json").write_text(json.dumps(out, separators=(",", ":")))
    health = {"previous": (out["previous"] or {}).get("issue_id"), **({"why": out["why"]} if "why" in out else {}),
              "previous_checked": "live" if published_at is not None else "unverified",
              "since_last_bytes": (site / "data" / "since-last.json").stat().st_size}
    if keep:
        health |= append(doc, commit, now, state)
    return health
