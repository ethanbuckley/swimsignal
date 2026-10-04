"""Scottish Water's near-real-time overflow API, polled in shadow (Scotland plan, task S4).

Off unless DIPCAST_SCOTTISH_WATER=1 (config.SCOTTISH_WATER). When on, jobs.refresh_all calls poll()
after the English feeds, and poll() keeps two files in STATE:

  scottish_water_latest.parquet   one row per asset: the status, both events, a data state
  scottish_water_history.parquet  one row per discharge, keyed by (site_id, discharge_id)

Nothing here writes live_latest.parquet, live_history.parquet, the coverage file or the overflow table,
so no Scottish row reaches the site, the scorer or the English history. site.yml publishes a fixed list
of state files to the `state` release, and these two are not on it. Decided on 4 Oct 2026 (plan,
section 10): "right now" for Scotland goes live with the forecast, after the outside review.

What the API gives (checked: one request each on 4 Oct 2026, from a Mac at 14:37 and 18:19 UTC and
from a GitHub runner in a throwaway workflow, run 37223860337): HTTP 200, about 2.96 MB of JSON, no
key, no compression. `{"results": [...], "last_updated": <epoch ms>}`, one row per asset (2,074 rows
at 14:37 and at 18:19), every value a string, times in UTC with a Z. Each row carries its latest event and the
one before it: start, end, minutes and a discharge id. The API page asks users to "respect rate
limits and cache data where possible" (no rate given) and to "cite Scottish Water as the data
source" (CREDIT). It says the monitors "do not confirm overflow events, they only indicate them".

Status (plan section 5.1; the codes and their meanings are from the API page, read 4 Oct 2026):

  13 Overflowing        ->  1  discharging; the latest event has no end
  14 Recent Overflow    ->  0  not discharging; the latest event ended in the last 48 hours
  15 No Overflows       ->  0  not discharging
  16 No Data Available  -> -1  offline; INTERNAL_OVERFLOW_STATUS_ID says why (NO_DATA_REASONS)

Any other code reads as -1, as ingest.live reads a Status it cannot parse.

Data state per asset (ingest.live's LIVE, STALE, OFFLINE). Unlike the English feeds, each asset has
its own transmit times, so a stale monitor is marked one by one, not by company. An asset is live
when its status is 1 or 0 and the older of its two transmit times (`transmitted_at`) is within
live.FEED_CURRENT_H of the poll; stale when its status is 1 or 0 but either time is older or missing;
offline when its status is -1. The older time is used because the two can disagree: on 4 Oct 2026 at
18:19 UTC, CSO003333 read "No valid data received in the past 48 hours" with
DEVICE_LAST_TRANSMITTED_DATETIME 2.2 hours old and LAST_TRANSMITTED_DATETIME 54.1 hours old
(checked). *Inferred* from that row: the device time is a heartbeat and the other the last data.
The API page defines neither field. In that answer LAST_TRANSMITTED_DATETIME was never the later
of the two (1,800 of 1,834 rows earlier, the rest equal).

Stuck monitors (plan section 5.2). An asset that has read Overflowing for more than STUCK_H hours is
marked `stuck`, and its data state is stale: the reading may be frozen. Its status stays 1, so it is
never read as "not discharging", and its events stay in the history with the same flag, so a scorer
can leave them out. The rule flags and never drops, because a long discharge can be real (*inferred*:
groundwater keeps some overflows running for weeks in a wet winter). At 18:19 UTC on 4 Oct 2026, 2
of 37 Overflowing assets passed 168 hours (223.6 and 687.7 hours); the next longest was 52.3
(checked). England's live feeds have the same risk and no rule yet (plan section 5.2 asks for one
rule for both); the English snapshot of 11:48 UTC that day had 6 discharging overflows, the longest
at 145.6 hours, so the same rule would have marked none.

Events. Both events of every asset go to the history, keyed by discharge id, so an event that moves
from `latest` to `previous` between two polls is kept once, with its end. Checked on two answers an
hour apart (feed times 18:01 and 19:03 UTC on 4 Oct 2026): of the 2,866 events in both, none changed
its discharge id, including the 3 that ended between them, and 11 moved from latest to previous. A
third event between polls is still lost: the feed keeps two. 242 assets at 14:37 and 243 at 18:19
had both starts within 3 hours, and in that one hour 4 assets had two new events, so the latest of
the first answer was in neither slot of the second (checked). If that event was open, the history
keeps it open from its last sighting, which observed_spill_days ends at that poll.
The column names `status`, `latest_event_start` and `latest_event_end` are those
forecast_log.observed_spill_days reads, so task S5 can score from this file as it is.
"""

from __future__ import annotations

import logging
import time

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.common import write_parquet
from dipcast.ingest.live import FEED_CURRENT_H, LIVE, OFFLINE, STALE

log = logging.getLogger(__name__)

COMPANY = "Scottish Water"
CREDIT = "Contains data from Scottish Water (overflow event monitoring, near-real-time API)."
LATEST_FILE = "scottish_water_latest.parquet"
HISTORY_FILE = "scottish_water_history.parquet"
TIMEOUT_S = 120.0
RETRIES = 3
STUCK_H = 168.0    # an asset Overflowing for longer than this is flagged stuck (module docstring)

STATUS = {"13": 1, "14": 0, "15": 0, "16": -1}
STATUS_TEXT = {"13": "Overflowing", "14": "Recent Overflow", "15": "No Overflows", "16": "No Data Available"}
NO_DATA_REASONS = {
    "17": "No data received in the past 48 hours",
    "18": "No valid data received in the past 48 hours",
    "19": "Under Maintenance",
    "20": "Non real-time monitored",
    "21": "Non Active Device",
    "22": "Non-Active Site (unmonitored)",
    "23": "Non-matching Asset ID (unmonitored)",
}

LATEST_COLS = [
    "site_id", "company", "site_name", "asset_type", "emergency", "status", "status_code", "status_text",
    "no_data_code", "no_data_reason", "latest_event_start", "latest_event_end", "discharge_id",
    "previous_event_start", "previous_event_end", "previous_discharge_id", "open_h", "stuck",
    "transmitted_at", "device_transmitted_at", "data_state", "lat", "lon", "receiving_watercourse",
    "rain_48h_mm", "feed_updated_at", "fetched_at",
]
HISTORY_COLS = [
    "site_id", "company", "discharge_id", "event", "status", "latest_event_start", "latest_event_end",
    "duration_min", "stuck", "first_seen", "fetched_at",
]


def fetch() -> dict:
    """The API's whole answer, parsed. Raises after RETRIES failed attempts."""
    last: Exception | None = None
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}, timeout=TIMEOUT_S) as c:
        for attempt in range(RETRIES):
            try:
                r = c.get(config.SCOTTISH_WATER_API)
                r.raise_for_status()
                body = r.json()
                if not isinstance(body.get("results"), list):
                    raise TypeError("no results list in the answer")
                return body
            except (httpx.HTTPError, ValueError, TypeError) as e:
                last = e
                log.warning("%s API failed (%s); retry in %ss", COMPANY, e, 2**attempt)
                time.sleep(2**attempt)
    raise RuntimeError(f"{COMPANY} API failed after {RETRIES} attempts: {last}")


def _time(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.replace("", None), utc=True, errors="coerce", format="ISO8601")


def _text(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


def parse(body: dict, fetched_at: pd.Timestamp) -> pd.DataFrame:
    """One row per asset (LATEST_COLS) from the API's answer, read at `fetched_at`."""
    raw = pd.DataFrame(body.get("results") or [])
    if raw.empty:
        return pd.DataFrame(columns=LATEST_COLS)
    raw = raw.reindex(columns=sorted(set(raw.columns) | {
        "ASSET_ID", "ASSET_NAME", "OVERFLOW_TYPE", "OVERFLOW_STATUS_ID", "INTERNAL_OVERFLOW_STATUS_ID",
        "OVERFLOW_START_DATETIME", "OVERFLOW_END_DATETIME", "OVERFLOW_DISCHARGEID",
        "OVERFLOW_START_DATETIME_PREVIOUS", "OVERFLOW_END_DATETIME_PREVIOUS", "OVERFLOW_DISCHARGEID_PREVIOUS",
        "LAST_TRANSMITTED_DATETIME", "DEVICE_LAST_TRANSMITTED_DATETIME", "RECEIVING_WATER", "RAINFALL_HISTORY",
        "DISCHARGE_OVERFLOW_LOCATION_LATITUDE", "DISCHARGE_OVERFLOW_LOCATION_LONGITUDE"}))
    fetched_at = pd.Timestamp(fetched_at).tz_convert("UTC")
    code = _text(raw["OVERFLOW_STATUS_ID"])
    reason = _text(raw["INTERNAL_OVERFLOW_STATUS_ID"])
    df = pd.DataFrame({
        "site_id": _text(raw["ASSET_ID"]),
        "company": COMPANY,
        "site_name": _text(raw["ASSET_NAME"]),
        "asset_type": _text(raw["OVERFLOW_TYPE"]),
        "status": code.map(STATUS).fillna(-1).astype(int),
        "status_code": code,
        "status_text": code.map(STATUS_TEXT),
        "no_data_code": reason.replace("", None),
        "no_data_reason": reason.map(NO_DATA_REASONS),
        "latest_event_start": _time(raw["OVERFLOW_START_DATETIME"]),
        "latest_event_end": _time(raw["OVERFLOW_END_DATETIME"]),
        "discharge_id": _text(raw["OVERFLOW_DISCHARGEID"]).replace("", None),
        "previous_event_start": _time(raw["OVERFLOW_START_DATETIME_PREVIOUS"]),
        "previous_event_end": _time(raw["OVERFLOW_END_DATETIME_PREVIOUS"]),
        "previous_discharge_id": _text(raw["OVERFLOW_DISCHARGEID_PREVIOUS"]).replace("", None),
        "device_transmitted_at": _time(raw["DEVICE_LAST_TRANSMITTED_DATETIME"]),
        "lat": pd.to_numeric(raw["DISCHARGE_OVERFLOW_LOCATION_LATITUDE"], errors="coerce"),
        "lon": pd.to_numeric(raw["DISCHARGE_OVERFLOW_LOCATION_LONGITUDE"], errors="coerce"),
        "receiving_watercourse": _text(raw["RECEIVING_WATER"]).replace("", None),
        "rain_48h_mm": pd.to_numeric(raw["RAINFALL_HISTORY"], errors="coerce"),
    })
    df = df[df["site_id"] != ""]
    # Emergency overflows "should only operate in the event of sewer system failure" (Scottish Water):
    # EO alone or in a mixed type (CSO/EO). Plan 5.2: show their live status, never forecast them.
    df["emergency"] = df["asset_type"].str.upper().str.split("/").map(lambda parts: "EO" in parts)
    data_time = _time(raw.loc[df.index, "LAST_TRANSMITTED_DATETIME"])
    # The older of the two times; NaT if either is missing (module docstring).
    df["transmitted_at"] = data_time.where(data_time.isna() | (data_time <= df["device_transmitted_at"]),
                                           df["device_transmitted_at"])
    df.loc[df["device_transmitted_at"].isna(), "transmitted_at"] = pd.NaT
    df["open_h"] = ((fetched_at - df["latest_event_start"]).dt.total_seconds() / 3600).where(
        (df["status"] == 1) & df["latest_event_end"].isna())
    df["stuck"] = df["open_h"].gt(STUCK_H)
    df["fetched_at"] = fetched_at
    feed_ms = pd.to_numeric(pd.Series([body.get("last_updated")]), errors="coerce").iloc[0]
    df["feed_updated_at"] = pd.Timestamp(int(feed_ms), unit="ms", tz="UTC") if pd.notna(feed_ms) else pd.NaT
    df["data_state"] = data_states(df)
    dup = df["site_id"].duplicated(keep="last")
    if dup.any():
        log.warning("%s: %d rows repeat an asset id; keeping the last of each", COMPANY, int(dup.sum()))
    return df.loc[~dup, LATEST_COLS].reset_index(drop=True)


def data_states(df: pd.DataFrame) -> pd.Series:
    """LIVE, STALE or OFFLINE for each asset (module docstring): by its own transmit time, not its
    company's, and stale for a stuck monitor."""
    known = df["status"].isin([0, 1])
    age_h = (pd.to_datetime(df["fetched_at"], utc=True) - pd.to_datetime(df["transmitted_at"], utc=True)
             ).dt.total_seconds() / 3600
    current = age_h.le(FEED_CURRENT_H) & ~df["stuck"].astype(bool)   # a missing time is not current
    return pd.Series(np.select([known & current, known], [LIVE, STALE], OFFLINE), index=df.index)


def events(snap: pd.DataFrame) -> pd.DataFrame:
    """Both events of every asset in this snapshot, one row per discharge id (HISTORY_COLS). Status 1
    for the latest event of an Overflowing asset; 0 for an event with an end; -1 for an open event on
    an asset that is not Overflowing (none on 4 Oct 2026), which forecast_log.observed_spill_days
    counts on its start day only."""
    parts = []
    for which, pre in (("latest", "latest_"), ("previous", "previous_")):
        start, end = snap[f"{pre}event_start"], snap[f"{pre}event_end"]
        ev = pd.DataFrame({"site_id": snap["site_id"], "company": snap["company"],
                           "discharge_id": snap["discharge_id" if which == "latest" else "previous_discharge_id"],
                           "event": which,
                           "latest_event_start": start, "latest_event_end": end,
                           "stuck": snap["stuck"] if which == "latest" else False,
                           "fetched_at": snap["fetched_at"]})
        is_open = end.isna()
        ev["status"] = np.where(~is_open, 0, np.where((snap["status"] == 1) & (which == "latest"), 1, -1))
        parts.append(ev)
    ev = pd.concat(parts, ignore_index=True)
    ev = ev[ev["discharge_id"].notna() & ev["latest_event_start"].notna()].copy()
    ev["duration_min"] = (ev["latest_event_end"] - ev["latest_event_start"]).dt.total_seconds() / 60
    ev["first_seen"] = ev["fetched_at"]
    return ev[HISTORY_COLS].reset_index(drop=True)


def merge_history(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """One row per (site_id, discharge_id): the latest sighting (an end time filled in, a stuck flag
    cleared or set), with `first_seen` from the earliest."""
    h = new if old is None or old.empty else pd.concat([old[HISTORY_COLS], new], ignore_index=True)
    h = h.sort_values("fetched_at", kind="stable")
    first = h.groupby(["site_id", "discharge_id"])["first_seen"].transform("min")
    h = h.assign(first_seen=first).drop_duplicates(["site_id", "discharge_id"], keep="last")
    return h.sort_values(["site_id", "latest_event_start"]).reset_index(drop=True)


def save(snap: pd.DataFrame) -> pd.DataFrame:
    """Write this poll's snapshot and add its events to the history. Returns the history. An empty
    snapshot (a failed poll) writes nothing, so the last good one stays."""
    if snap.empty:
        return pd.DataFrame(columns=HISTORY_COLS)
    write_parquet(snap, config.state_write(LATEST_FILE))
    p = config.state_read(HISTORY_FILE)
    hist = merge_history(pd.read_parquet(p) if p.exists() else None, events(snap))
    write_parquet(hist, config.state_write(HISTORY_FILE))
    return hist


def poll() -> dict:
    """Fetch, parse and save once. Never raises: a shadow feed must not stop the English refresh."""
    try:
        snap = parse(fetch(), pd.Timestamp.now(tz="UTC"))
        hist = save(snap)
    except Exception as e:  # noqa: BLE001 - shadow only; the English poll has already been saved
        log.error("%s shadow poll failed: %s", COMPANY, e)
        return {"ok": False, "error": str(e)}
    summary = {"ok": True, "assets": len(snap), "discharging": int((snap["status"] == 1).sum()),
               "data_states": snap["data_state"].value_counts().to_dict(), "stuck": int(snap["stuck"].sum()),
               "history_events": len(hist)}
    log.info("%s (shadow, not shown): %s", COMPANY, summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(poll())
