"""Pull the current status of every monitored storm overflow.

Each company feed is a snapshot: one row per overflow with its current status
and the start/end of its latest event. We keep the latest snapshot and append
every distinct (site, status, status_start) to a history file so that polling
over time accumulates an event log for companies that publish no history. A
feed that publishes no status start (South West Water's) keeps one row per
(site, status, local day polled) instead, so a discharge seen on one day is not
overwritten by the next day's.

A company whose feed fails, or returns no rows, keeps its last snapshot in
live_latest.parquet with status FEED_DOWN and the time of that snapshot in
`feed_down_since`, so the map says the feed is down rather than that its
overflows have no live feed. Only fresh rows reach the history, the coverage
file and the poll log.

Each overflow also gets a data state (data_states): whether its status can be
taken as current, so that a frozen feed never reads as "not discharging".
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.arcgis import fetch_all, layer_edit_time
from dipcast.ingest.common import to_utc, write_parquet

log = logging.getLogger(__name__)

COLS = [
    "site_id", "company", "status", "status_start", "latest_event_start",
    "latest_event_end", "lat", "lon", "receiving_watercourse", "last_updated", "fetched_at",
    "layer_edited_at",
]
# What the nine live layers carry, from each layer's own description (`<layer>?f=json`, read once
# each at 00:29 BST on 4 Oct 2026, no data query; the README's live-feed table has it company by
# company). Every one is the National Storm Overflow Hub's schema and nothing else: the ten fields
# below and an object id. Status is a coded value in all nine: 1 "Start" (discharging), 0 "Stop"
# (not discharging), -1 "Offline" (the monitor is not reporting). South West Water's layer spells
# every field but Id in camelCase (status, statusStart, lastUpdated, ...), which hub_names maps.
# No layer has a field for a record's validation or verification, a dry-weather spill or a high
# river: where a company shows such a flag, it is not in these feeds, so data_states cannot say it.
RENAME = {
    "Id": "site_id", "Company": "company", "Status": "status", "StatusStart": "status_start",
    "LatestEventStart": "latest_event_start", "LatestEventEnd": "latest_event_end",
    "Latitude": "lat", "Longitude": "lon", "ReceivingWaterCourse": "receiving_watercourse",
    "LastUpdated": "last_updated",
}


def hub_names(df: pd.DataFrame) -> pd.DataFrame:
    """Field names in the hub's spelling, whatever their case. Until 4 Oct 2026 the names were
    matched exactly, so South West Water's statusStart, latestEventStart, latestEventEnd,
    lastUpdated, receivingWaterCourse, latitude and longitude were never read, whatever they held.
    A name already in the hub's spelling is left alone."""
    want = {k.lower(): k for k in RENAME}
    return df.rename(columns={c: want[c.lower()] for c in df.columns
                              if c.lower() in want and c != want[c.lower()] and want[c.lower()] not in df.columns})


def _layer_edited_at(company: str, url: str) -> pd.Timestamp:
    """The layer's last data edit (arcgis.layer_edit_time), or NaT if it cannot be read."""
    try:
        ms = layer_edit_time(url)
    except Exception as e:  # noqa: BLE001 - optional: without it the feed reads as stale, never as current
        log.warning("%s: layer edit time unavailable: %s", company, e)
        return pd.NaT
    return pd.NaT if ms is None else pd.Timestamp(int(ms), unit="ms", tz="UTC")


def fetch_live(companies: dict[str, str] | None = None) -> pd.DataFrame:
    feeds = companies or config.LIVE_FEEDS
    frames = []
    for company, url in feeds.items():
        try:
            rows = fetch_all(url, geometry=True, key="Id")   # key: re-read a torn multi-page read
        except Exception as e:  # noqa: BLE001 - one dead feed must not kill the poll
            log.error("live feed failed for %s: %s", company, e)
            continue
        df = hub_names(pd.DataFrame(rows)).rename(columns=RENAME)
        df["company"] = company
        # A layer whose records carry no stamp at all: its own last edit is the only evidence the
        # feed is current, read for data_states (one more small request). The coverage file and the
        # scorer do not use it (coverage_rows says why).
        if "last_updated" not in df or df["last_updated"].isna().all():
            df["layer_edited_at"] = _layer_edited_at(company, url)
        # Some feeds (South West Water) carry location only as geometry.
        for col, geo in (("lat", "_y"), ("lon", "_x")):
            if col not in df:
                df[col] = np.nan
            if geo in df:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(df[geo])
        frames.append(df)
        log.info("%s: %d overflows", company, len(df))
    if not frames:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(frames, ignore_index=True)
    for c in ["status_start", "latest_event_start", "latest_event_end", "last_updated"]:
        df[c] = to_utc(df[c]) if c in df else pd.NaT
    df["status"] = pd.to_numeric(df["status"], errors="coerce").fillna(-1).astype(int)
    df["fetched_at"] = pd.Timestamp.now(tz="UTC")
    df["layer_edited_at"] = (pd.to_datetime(df["layer_edited_at"], utc=True) if "layer_edited_at" in df
                             else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]"))
    df = df.dropna(subset=["lat", "lon"])
    return one_row_per_site(df[COLS])


def one_row_per_site(df: pd.DataFrame) -> pd.DataFrame:
    """The snapshot with one row per site_id, the most recently updated. A feed can
    list an overflow twice (Anglian Water's AWS00528 on 3 Oct 2026, both rows the same),
    and a torn read that fetch_all could not repair repeats rows. Every reader treats
    site_id as a key: a repeated row is counted twice in coverage, and one upstream of a spot
    failed its forecast with "Index contains duplicate entries, cannot reshape"."""
    dup = df["site_id"].duplicated(keep=False)
    if not dup.any():
        return df
    for c, n in df.loc[dup, "company"].value_counts().items():
        log.warning("%s: %d rows share a site_id with another; keeping the most recently updated", c, n)
    order = df["last_updated"].sort_values(na_position="first", kind="stable").index if "last_updated" in df else df.index
    return df.loc[order].drop_duplicates("site_id", keep="last").sort_index()


LOCAL_TZ = "Europe/London"
COVERAGE_FILE = "live_coverage.parquet"
POLL_LOG_FILE = "poll_log.parquet"
SLOTS_PER_DAY = 48          # half-hour slots; the site polls every 30 min
FEED_CURRENT_H = 6.0        # a feed whose freshest LastUpdated is older than this, or that has none, is stale
FEED_DOWN = -3              # status of a carried-forward row: the company's feed failed this poll
COVERAGE_COLS = ["site_id", "day", "n_known", "n_unknown", "n_stale", "slots"]


def feed_age_hours(df: pd.DataFrame) -> pd.Series:
    """Per company, the age of the freshest `last_updated` in this poll. Six companies
    stamp every record on every refresh (age under an hour); Northumbrian and Southern
    stamp a record only when it changes; South West Water publishes no stamp (NaN).
    A successful HTTP response is not evidence the feed is current; this is, so a
    NaN age is treated as not current (see coverage_rows)."""
    if df.empty or "last_updated" not in df:
        return pd.Series(dtype=float)
    age = (pd.to_datetime(df["fetched_at"], utc=True) - pd.to_datetime(df["last_updated"], utc=True)).dt.total_seconds() / 3600
    return age.groupby(df["company"]).min()


# An overflow's data state (data_states). Kept beside `status`, which keeps its numbers.
LIVE, STALE, OFFLINE, NO_FEED = "live", "stale", "offline", "no_feed"


def feed_updated_at(df: pd.DataFrame) -> pd.Series:
    """Per company, when its feed last updated as far as these rows (one poll that answered) show:
    the freshest record stamp, or, for a company whose records carry none, the layer's own last
    edit (`layer_edited_at`). NaT where neither is known."""
    if df.empty:
        return pd.Series(dtype="datetime64[ns, UTC]")
    stamp = pd.to_datetime(df["last_updated"], utc=True).groupby(df["company"]).max()
    if "layer_edited_at" in df:
        stamp = stamp.fillna(pd.to_datetime(df["layer_edited_at"], utc=True).groupby(df["company"]).max())
    return stamp


def data_states(ov: pd.DataFrame) -> pd.DataFrame:
    """`data_state` and `feed_updated_at` for each row of the overflow table (overflows.py):

      live      a status (1 or 0) from a feed that updated within FEED_CURRENT_H of the poll
      stale     a status from a feed that did not, or that gives no time at all: the reading may
                be frozen, so its "not discharging" says nothing about now
      offline   no status: the monitor is offline (-1), the company's feed did not answer the poll
                (-3, carry_forward), or the overflow is missing from the live feed of a company
                that has one (-2)
      no_feed   its company publishes no live feed (-2; Dwr Cymru Welsh Water's overflows)

    Current is the test coverage_rows applies, a company's freshest record stamp under
    FEED_CURRENT_H old, so a poll the scorer counts as stale is stale here too. One addition: a
    company whose records carry no stamp at all is current when its layer was last written within
    FEED_CURRENT_H (`layer_edited_at`). That is enough to say what the feed shows now; it is not
    enough to say a day had no spill, so the scorer does not take it. `feed_updated_at` is the
    company's feed time (feed_updated_at) on every row with a status from this poll (1, 0, -1).
    A table without the poll's times (a test's) gets its states from the status alone."""
    out = pd.DataFrame(index=ov.index)
    if ov.empty:
        return out.assign(data_state=pd.Series(dtype=object), feed_updated_at=pd.Series(dtype="datetime64[ns, UTC]"))
    status = ov["status"]
    known, polled = status.isin([0, 1]), status.isin([0, 1, -1])
    if {"fetched_at", "last_updated"} <= set(ov.columns):
        p = ov[polled]
        fetched = pd.to_datetime(p["fetched_at"], utc=True).groupby(p["company"]).max()
        updated = feed_updated_at(p)
        age_h = ((fetched - updated).dt.total_seconds() / 3600).reindex(fetched.index)
        current = ov["company"].map(age_h <= FEED_CURRENT_H).eq(True)   # a NaN age (no time) is not current
        when = pd.to_datetime(ov["company"].map(updated), utc=True)
    else:
        current = pd.Series(True, index=ov.index)
        when = pd.Series(pd.NaT, index=ov.index, dtype="datetime64[ns, UTC]")
    has_feed = ov["company"].isin(ov.loc[ov["has_live"].astype(bool), "company"]) if "has_live" in ov else status.ne(-2)
    out["data_state"] = np.select([known & current, known, status.ne(-2) | has_feed], [LIVE, STALE, OFFLINE], NO_FEED)
    out["feed_updated_at"] = when.where(polled)
    return out


def with_data_states(ov: pd.DataFrame) -> pd.DataFrame:
    """The table with `data_state` and `feed_updated_at`, worked out if it has none (a table cached
    before 4 Oct 2026, or a test's). One with no status at all is returned as it is."""
    if "data_state" in ov or "status" not in ov:
        return ov
    return pd.concat([ov.drop(columns=["feed_updated_at"], errors="ignore"), data_states(ov)], axis=1)


def coverage_rows(df: pd.DataFrame) -> pd.DataFrame:
    """One row per overflow for this poll: local day, whether the status was known
    (0 or 1) or unknown (offline, missing), whether the company's feed looked stale,
    and the half-hour slot as a bit in `slots`. OR-ing the slot bits over a day gives
    the distinct times the overflow was observed, from which the scorer derives the
    first and last observation and the longest gap; a repeated poll in the same slot
    adds nothing. A company with no `last_updated` at all (age NaN) gives no evidence
    that its feed is current, so its polls count as stale: South West Water's feed
    carries neither a record stamp nor event times, so a poll sees only what is
    discharging at that moment, and a day of such polls cannot support "no spill".
    The layer's own last edit (`layer_edited_at`) is not used here for the same reason:
    it says the snapshot is current, not what happened between polls."""
    if df.empty:
        return pd.DataFrame(columns=COVERAGE_COLS)
    local = pd.to_datetime(df["fetched_at"], utc=True).dt.tz_convert(LOCAL_TZ)
    known = df["status"].isin([0, 1])
    age = df["company"].map(feed_age_hours(df))
    stale = known & ~(age <= FEED_CURRENT_H)     # NaN (no stamp) is not current
    slot = (local.dt.hour * 2 + local.dt.minute // 30).astype(int)
    slots = np.where(known & ~stale, np.left_shift(np.int64(1), slot.to_numpy()), np.int64(0))
    return pd.DataFrame({"site_id": df["site_id"].astype(str).to_numpy(), "day": local.dt.date.to_numpy(),
                         "n_known": known.astype(int).to_numpy(), "n_unknown": (~known).astype(int).to_numpy(),
                         "n_stale": stale.astype(int).to_numpy(), "slots": slots})


def update_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Add this poll to live_coverage.parquet and return the merged table. Compact:
    one row per overflow per day, counts summed and slot bits OR-ed."""
    new = coverage_rows(df)
    p = config.state_read(COVERAGE_FILE)
    if p.exists():
        old = pd.read_parquet(p)
        old["day"] = pd.to_datetime(old["day"]).dt.date
        for c, dflt in (("n_stale", 0), ("slots", 0)):   # files from before 17 Sep 2026
            if c not in old:
                old[c] = dflt
        new = pd.concat([old[COVERAGE_COLS], new], ignore_index=True)
    new["slots"] = new["slots"].astype("int64")
    cov = new.groupby(["site_id", "day"], as_index=False).agg(
        n_known=("n_known", "sum"), n_unknown=("n_unknown", "sum"), n_stale=("n_stale", "sum"),
        slots=("slots", lambda s: int(np.bitwise_or.reduce(s.to_numpy(dtype="int64")))))
    cov["day"] = pd.to_datetime(cov["day"])
    write_parquet(cov, config.state_write(COVERAGE_FILE))
    return cov


def log_poll(df: pd.DataFrame, feeds: dict[str, str] | None = None) -> None:
    """Append one row per company per poll: rows returned, how many had a known
    status, and the age of the freshest record. A company absent from a poll (feed
    failure) appears with zero rows, so feed outages are visible afterwards."""
    fetched = df["fetched_at"].iloc[0] if len(df) else pd.Timestamp.now(tz="UTC")
    companies = list((feeds or config.LIVE_FEEDS).keys())
    g = df.groupby("company") if len(df) else None
    ages = feed_age_hours(df)
    rows = []
    for c in companies:
        sub = g.get_group(c) if g is not None and c in g.groups else df.iloc[0:0]
        rows.append({"fetched_at": fetched, "company": c, "n_rows": len(sub),
                     "n_known": int(sub["status"].isin([0, 1]).sum()) if len(sub) else 0,
                     "feed_age_h": float(ages.get(c, np.nan))})
    new = pd.DataFrame(rows)
    p = config.state_read(POLL_LOG_FILE)
    if p.exists():
        new = pd.concat([pd.read_parquet(p), new], ignore_index=True)
    write_parquet(new, config.state_write(POLL_LOG_FILE))


def carry_forward(df: pd.DataFrame, previous: pd.DataFrame | None,
                  feeds: dict[str, str] | None = None) -> pd.DataFrame:
    """This poll's rows plus, for each company that returned none, its rows from the
    previous snapshot with status FEED_DOWN and `feed_down_since` the time of the last
    poll that answered. Event times are kept: they were true at that poll."""
    out = df.copy()
    out["feed_down_since"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    if previous is None or previous.empty:
        return out
    companies = list((feeds or config.LIVE_FEEDS).keys())
    present = set(df["company"].unique()) if len(df) else set()
    down = [c for c in companies if c not in present]
    old = one_row_per_site(previous[previous["company"].isin(down)]).copy()
    if old.empty:
        return out
    since = pd.to_datetime(old["fetched_at"], utc=True)
    if "feed_down_since" in old:
        since = pd.to_datetime(old["feed_down_since"], utc=True).fillna(since)
    old["feed_down_since"] = since
    old["status"] = FEED_DOWN
    for c in sorted(set(old["company"])):
        log.warning("%s: no rows this poll; keeping its last snapshot (%s) as feed down", c,
                    old.loc[old["company"] == c, "feed_down_since"].min())
    cols = list(out.columns)
    return pd.concat([out, old.reindex(columns=cols)], ignore_index=True)


def history_key(h: pd.DataFrame) -> pd.Series:
    """The local day polled where a row has no status start, else missing. Part of the
    history's de-duplication key: with a blank status start every poll of a site with
    the same status looks alike, so without the day each site would keep one row per
    status and a discharge seen on one day would be overwritten by the next."""
    day = pd.to_datetime(h["fetched_at"], utc=True).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d")
    return day.where(pd.to_datetime(h["status_start"], utc=True).isna())


def save_live(df: pd.DataFrame) -> None:
    prev_path = config.state_read("live_latest.parquet")
    previous = pd.read_parquet(prev_path) if prev_path.exists() else None
    write_parquet(carry_forward(df, previous), config.state_write("live_latest.parquet"))
    hist_read = config.state_read("live_history.parquet")
    keep = df[["site_id", "company", "status", "status_start", "latest_event_start",
               "latest_event_end", "fetched_at"]]
    if hist_read.exists():
        old = pd.read_parquet(hist_read)
        keep = pd.concat([old, keep], ignore_index=True)
    # The history keeps one row per distinct (site, status, status_start): an event
    # log, not an observation log. Observation counts live in the coverage file. Rows
    # with no status start are kept once per local day polled (history_key).
    keep = keep.assign(_day=history_key(keep)).drop_duplicates(
        subset=["site_id", "status", "status_start", "_day"], keep="last").drop(columns="_day")
    write_parquet(keep, config.state_write("live_history.parquet"))
    update_coverage(df)
    log_poll(df)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    save_live(fetch_live())
