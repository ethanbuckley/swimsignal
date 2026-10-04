"""Dŵr Cymru Welsh Water's live overflow layer (Wales plan, task W5). Off by default.

Off unless DIPCAST_DWR_CYMRU=1 (config.DWR_CYMRU). The layer has no licence, and Dŵr Cymru's site
asks for written permission before reuse (Wales plan, sections 2.1 and 2.2). So while the setting is
off, nothing here runs: no request, no file, nothing in the state release, nothing on the site. Turn
it on only after Dŵr Cymru agrees. Even then this module writes only its own two files in STATE:

  dwr_cymru_latest.parquet   one row per overflow: status, latest discharge, data state
  dwr_cymru_history.parquet  one row per discharge, keyed by (site_id, latest_event_start)

site.yml publishes a fixed list of state files to the public `state` release, and these two are not
on it (a test checks). Feeding Dŵr Cymru's rows to the map is task W6, which starts with its 140
overflows in England.

The layer (checked, plain requests on 4 Oct 2026; Wales plan 2.1 at 15:05 UTC, and again for this
module at 18:26 UTC): `Spill_Prod__view`, the layer Dŵr Cymru's map draws. Two pages of at most 2,000
rows (2,362 rows, one per `GlobalID`), no asset id field. Status is text. One discharge per overflow:
start and stop as text with no time zone ("2026-10-04T10:15:00"), duration in hours as text. Each
row has an `EditDate`, but the plan found it marks a change, not a check, so it is kept
(`row_edited_at`) and not used for the data state.

Status (Wales plan 5.1, and section 10 item 5 for "Under Investigation"):

  "Overflow Operating"                                  ->  1  discharging; no stop time
  "Overflow Not Operating (Has in the last 24 hours)"   ->  0  not discharging; the last stop time
  "Overflow Not Operating"                              ->  0  not discharging
  "Under Investigation"                                 -> -1  status unknown (see below)
  anything else                                         -> -1  offline, as ingest.live reads an
                                                               unparsed Status

"Under Investigation" is the map's word for a status of "Under Maintenance" (Wales plan 2.1). Until
Dŵr Cymru explains it (question 8.1.4), it is read as status unknown, the plan's plainest choice:
`status` -1, `under_investigation` True, and data state stale, as an English row from a feed that
may be frozen is. Its last discharge and its times are kept, so the row can show "last discharge
<time>". It is never read as "not discharging". This is the one row type with status -1 and data
state stale; England has none.

Times. The layer gives none a zone. *Inferred* UK local time, from the plan's check and mine: at
18:26 UTC on 4 Oct 2026 the 11 open discharges' start plus duration ran to 17:19-17:21, which is
about 16:20 UTC, 2 minutes before the layer's last data edit (16:22:25 UTC). Read as UTC they would end after
it. Question 8.1.5 asks Dŵr Cymru. In the hour the clocks go back, a local time happens twice: a
start is read as the earlier of the two and a stop as the later, so a discharge is never shortened.
A time in the hour the clocks go forward does not exist and is moved to the end of the gap. A time
that does carry a zone (none on 4 Oct 2026) is read with it.

Feed time and data state. The rows carry no update stamp, so the feed time is the layer's last data
edit (arcgis.layer_edit_time), as ingest.live.fetch_live reads for an English company whose records
carry none. ingest.live.data_states then gives the state by the same rule as England: live when
that edit is within FEED_CURRENT_H of the poll, stale when it is older or unknown, offline for -1.

Emergency overflows are marked (`emergency`, from `Overflow` = "Emergency"; 305 of 2,362 on 4 Oct
2026). Wales plan 5.2: show their status, never forecast them.
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.arcgis import fetch_all, layer_edit_time
from dipcast.ingest.common import write_parquet
from dipcast.ingest.live import LOCAL_TZ, STALE, data_states

log = logging.getLogger(__name__)

COMPANY = "Dwr Cymru Welsh Water"   # the Environment Agency's spelling in annual_returns.parquet, for W6
LATEST_FILE = "dwr_cymru_latest.parquet"
HISTORY_FILE = "dwr_cymru_history.parquet"
UNDER_INVESTIGATION = "Under Investigation"
STATUS = {
    "Overflow Operating": 1,
    "Overflow Not Operating (Has in the last 24 hours)": 0,
    "Overflow Not Operating": 0,
    UNDER_INVESTIGATION: -1,
}
_ZONE = re.compile(r"(?:Z|[+-]\d\d:?\d\d)$")

LATEST_COLS = [
    "site_id", "company", "site_name", "asset_location", "asset_type", "emergency", "status", "status_text",
    "under_investigation", "latest_event_start", "latest_event_end", "duration_h", "duration_7d_h",
    "data_state", "lat", "lon", "easting", "northing", "receiving_watercourse", "bathing_water", "row_edited_at",
    "layer_edited_at", "feed_updated_at", "fetched_at",
]
HISTORY_COLS = ["site_id", "company", "status", "latest_event_start", "latest_event_end", "duration_h",
                "under_investigation", "first_seen", "fetched_at"]


def local_to_utc(s: pd.Series, *, stop: bool) -> pd.Series:
    """UK local times as text, to UTC. Twice-happening times go to the earlier instant for a start
    and the later for a stop (`stop`); times in the spring gap move forward. A time with its own zone
    is read with it."""
    text = s.astype("string").str.strip().replace("", pd.NA)
    zoned = text.str.contains(_ZONE).fillna(False).astype(bool)
    naive = pd.to_datetime(text.where(~zoned), errors="coerce", format="ISO8601")
    out = naive.dt.tz_localize(LOCAL_TZ, ambiguous=np.full(len(text), not stop), nonexistent="shift_forward"
                               ).dt.tz_convert("UTC")
    if zoned.any():
        out[zoned] = pd.to_datetime(text[zoned], utc=True, errors="coerce", format="ISO8601")
    return out


def _text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().replace("", pd.NA)


def parse(rows: list[dict], fetched_at: pd.Timestamp, layer_edited_at: pd.Timestamp | None) -> pd.DataFrame:
    """One row per overflow (LATEST_COLS) from the layer's features (arcgis.fetch_all's flat dicts,
    geometry in WGS84 as `_x`, `_y`), read at `fetched_at`, with the layer's last data edit."""
    raw = pd.DataFrame(rows)
    if raw.empty:
        return pd.DataFrame(columns=LATEST_COLS)
    want = ["GlobalID", "asset_name", "asset_location", "status", "Overflow", "start_date_time_discharge",
            "stop_date_time_discharge", "discharge_duration_hours", "discharge_duration_last_7_daysH",
            "Receiving_Water", "Linked_Bathing_Water", "EditDate", "discharge_x_location",
            "discharge_y_location", "_x", "_y"]
    raw = raw.reindex(columns=sorted(set(raw.columns) | set(want)))
    fetched_at = pd.Timestamp(fetched_at).tz_convert("UTC")
    status_text = _text(raw["status"])
    df = pd.DataFrame({
        "site_id": _text(raw["GlobalID"]).str.strip("{}").str.lower(),   # as wales_annual's live_global_id
        "company": COMPANY,
        "site_name": _text(raw["asset_name"]),
        "asset_location": _text(raw["asset_location"]),
        "asset_type": _text(raw["Overflow"]),
        "status": status_text.map(STATUS).fillna(-1).astype(int),
        "status_text": status_text,
        "under_investigation": status_text.eq(UNDER_INVESTIGATION).fillna(False).astype(bool),
        "latest_event_start": local_to_utc(raw["start_date_time_discharge"], stop=False),
        "latest_event_end": local_to_utc(raw["stop_date_time_discharge"], stop=True),
        "duration_h": pd.to_numeric(raw["discharge_duration_hours"], errors="coerce"),
        "duration_7d_h": pd.to_numeric(raw["discharge_duration_last_7_daysH"], errors="coerce"),
        "lat": pd.to_numeric(raw["_y"], errors="coerce"),
        "lon": pd.to_numeric(raw["_x"], errors="coerce"),
        "easting": pd.to_numeric(raw["discharge_x_location"], errors="coerce"),    # outlet, BNG; W2 and W6
        "northing": pd.to_numeric(raw["discharge_y_location"], errors="coerce"),   # match by it
        "receiving_watercourse": _text(raw["Receiving_Water"]),
        "bathing_water": _text(raw["Linked_Bathing_Water"]),
        "row_edited_at": pd.to_datetime(pd.to_numeric(raw["EditDate"], errors="coerce"), unit="ms", utc=True),
    })
    unknown = sorted(set(status_text.dropna()) - set(STATUS))
    if unknown:
        log.warning("%s: status text not in the mapping, read as offline: %s", COMPANY, unknown)
    df = df[df["site_id"].notna()]
    df["emergency"] = df["asset_type"].str.lower().eq("emergency").fillna(False).astype(bool)
    df["fetched_at"] = fetched_at
    df["last_updated"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")   # the rows carry none
    df["layer_edited_at"] = pd.Timestamp(layer_edited_at) if layer_edited_at is not None else pd.NaT
    df["layer_edited_at"] = pd.to_datetime(df["layer_edited_at"], utc=True)
    df["has_live"] = True
    df = pd.concat([df, data_states(df)], axis=1)
    df.loc[df["under_investigation"], "data_state"] = STALE
    dup = df["site_id"].duplicated(keep="last")
    if dup.any():
        log.warning("%s: %d rows repeat a GlobalID; keeping the last of each", COMPANY, int(dup.sum()))
    return df.loc[~dup, LATEST_COLS].reset_index(drop=True)


def events(snap: pd.DataFrame) -> pd.DataFrame:
    """The latest discharge of every overflow that has one (HISTORY_COLS). Status 1 for an open
    discharge on an Operating overflow, 0 for one with a stop time, -1 for an open one on an overflow
    Under Investigation (8 rows at 15:05 UTC on 4 Oct 2026, 4 at 18:26), which forecast_log.observed_spill_days
    counts on its start day only."""
    ev = snap[snap["latest_event_start"].notna()].copy()
    is_open = ev["latest_event_end"].isna()
    ev["status"] = np.where(~is_open, 0, np.where(ev["status"] == 1, 1, -1))
    ev["first_seen"] = ev["fetched_at"]
    return ev[HISTORY_COLS].reset_index(drop=True)


def merge_history(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """One row per (site_id, latest_event_start): the latest sighting, with `first_seen` from the
    earliest. The layer keeps one discharge per overflow, so a second one between two polls is lost."""
    h = new if old is None or old.empty else pd.concat([old[HISTORY_COLS], new], ignore_index=True)
    h = h.sort_values("fetched_at", kind="stable")
    first = h.groupby(["site_id", "latest_event_start"])["first_seen"].transform("min")
    h = h.assign(first_seen=first).drop_duplicates(["site_id", "latest_event_start"], keep="last")
    return h.sort_values(["site_id", "latest_event_start"]).reset_index(drop=True)


def fetch() -> tuple[list[dict], pd.Timestamp | None]:
    """The layer's rows and its last data edit (None if the layer does not say)."""
    rows = fetch_all(config.DWR_CYMRU_LIVE, geometry=True, key="GlobalID")
    ms = layer_edit_time(config.DWR_CYMRU_LIVE)
    return rows, (pd.Timestamp(int(ms), unit="ms", tz="UTC") if ms is not None else None)


def save(snap: pd.DataFrame) -> pd.DataFrame:
    """Write this poll's snapshot and add its discharges to the history. Returns the history. An empty
    snapshot writes nothing."""
    if snap.empty:
        return pd.DataFrame(columns=HISTORY_COLS)
    write_parquet(snap, config.state_write(LATEST_FILE))
    p = config.state_read(HISTORY_FILE)
    hist = merge_history(pd.read_parquet(p) if p.exists() else None, events(snap))
    write_parquet(hist, config.state_write(HISTORY_FILE))
    return hist


def poll() -> dict:
    """Fetch, parse and save once, only when config.DWR_CYMRU is on. Never raises."""
    if not config.DWR_CYMRU:
        return {"ok": False, "error": "off (DIPCAST_DWR_CYMRU is not 1)"}
    try:
        rows, edited = fetch()
        snap = parse(rows, pd.Timestamp.now(tz="UTC"), edited)
        hist = save(snap)
    except Exception as e:  # noqa: BLE001 - one more feed must not stop the English refresh
        log.error("%s poll failed: %s", COMPANY, e)
        return {"ok": False, "error": str(e)}
    summary = {"ok": True, "overflows": len(snap), "discharging": int((snap["status"] == 1).sum()),
               "under_investigation": int(snap["under_investigation"].sum()),
               "data_states": snap["data_state"].value_counts().to_dict(), "history_events": len(hist)}
    log.info("%s (not shown): %s", COMPANY, summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(poll())
