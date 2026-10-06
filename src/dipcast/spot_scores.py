"""How the forecast has done at each spot's upstream overflows (roadmap rank 14).

The live scores are per overflow, not per spot: each row of the published scored CSV
(data/verification_live.csv, forecast_log.SCORED_CSV) is one overflow on one day at one lead. So a
spot's figures here are the plain sum of its upstream overflows' rows, under the Accuracy page's own
rules: the same rows, the same warning line (forecast_log.SPILL_WARN_AT, where a spot right beside
the overflow reads High risk) and the same counting (forecast_log.warning_counts), so that every count
here can be found by filtering that CSV to the spot's overflows. Nothing is weighted by reach: a
weighted count would no longer be found in the CSV, and a share weighted by reach needs a paragraph
to explain.

Each count is of forecasts, as on the Accuracy page: a spill at one overflow on one day was forecast
up to five times, from four days ahead to that morning, and each of those forecasts is a hit or a
miss. Below MIN_SPILLS spill days the page gives the counts and no share.

The build writes data/spot_scores.json (write); the spot page reads it (site/spotscores.js).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

from dipcast.forecast_log import SPILL_WARN_AT, warning_counts

log = logging.getLogger(__name__)

FILE = "spot_scores.json"
# A share is given once a spot's overflows have had this many spill days (overflow-days with a spill):
# the Accuracy page calls its E. coli comparison too few to judge below 10 events (ECOLI_MIN_EXCEEDANCES),
# and the same number keeps one rule across the site. Below it, the counts alone.
MIN_SPILLS = 10
_SPOT_ID = re.compile(r"[A-Za-z0-9_-]+")


def read_rows(path: Path) -> pd.DataFrame | None:
    """The published scored CSV, its comment lines skipped. None when there is no file."""
    if not path.exists():
        return None
    return pd.read_csv(path, comment="#", dtype={"overflow_id": str})


def _counts(r: pd.DataFrame) -> dict:
    w = warning_counts(r["observed"], r["forecast_calibrated"], SPILL_WARN_AT)
    days = r.drop_duplicates(["overflow_id", "day"])
    return {"overflow_days": len(days), "spill_days": int(days["observed"].sum()), "forecasts": w["n"],
            "hits": w["hits"], "misses": w["misses"], "false_alarms": w["false_alarms"],
            "days": int(r["day"].nunique()),
            "first_day": str(r["day"].min()) if len(r) else None, "last_day": str(r["day"].max()) if len(r) else None}


def summarise(rows: pd.DataFrame, upstream: dict[str, list[dict]]) -> dict:
    """Per spot with any monitored overflow upstream: how many overflows it has (overflows), at how many
    any day was scored (scored_overflows), and the scored rows' counts: overflow-days, spill days,
    forecasts, hits, misses and false alarms at the High risk line, and the days they span. A spot with
    nothing upstream (or a failed forecast, which has no overflows) is left out: there is nothing to
    score. `all` is the same counts over every row, which equal the Accuracy page's warning table."""
    rows = rows.assign(overflow_id=rows["overflow_id"].astype(str))
    by_id = {k: g for k, g in rows.groupby("overflow_id")}
    spots = {}
    for sid, ups in upstream.items():
        ids = sorted({str(o.get("site_id")) for o in ups or [] if o.get("site_id") is not None})
        if not ids or not _SPOT_ID.fullmatch(str(sid)):
            continue
        mine = [by_id[i] for i in ids if i in by_id]
        r = pd.concat(mine) if mine else rows.iloc[0:0]
        spots[sid] = {"overflows": len(ids), "scored_overflows": len(mine), **_counts(r)}
    return {"warn_at": SPILL_WARN_AT, "min_spills": MIN_SPILLS, "unit": "overflow-day forecast",
            "first_day": str(rows["day"].min()) if len(rows) else None,
            "last_day": str(rows["day"].max()) if len(rows) else None,
            "all": _counts(rows), "spots": spots}


def write(site: Path, upstream: dict[str, list[dict]], generated: pd.Timestamp, credits: dict) -> int | None:
    """data/spot_scores.json, from the scored CSV this build has just published (build_site.publish_scored_csv
    publishes it only when it agrees with verification.json). Without that file any old copy is removed and
    the spot pages show no tile. Returns the number of spots written, or None."""
    dst = site / "data" / FILE
    rows = read_rows(site / "data" / "verification_live.csv")
    if rows is None:
        dst.unlink(missing_ok=True)
        log.info("no scored rows published: %s not written", FILE)
        return None
    out = {"generated_at": generated.isoformat(), **summarise(rows, upstream), "credits": credits}
    dst.write_text(json.dumps(out, separators=(",", ":"), default=str))
    return len(out["spots"])
