"""Thames Water's discharge alert stream (review task D8; docs/EARLIER-SPILL-HISTORY-2026-10.md).

GET config.THAMES_ALERTS with no key (19 Oct 2026: HTTP 200 without credentials). The portal
(docs.api.thameswater.co.uk) says the stream "provides historical event data from April 2022", with
"specific rules governing the visibility" of events before the 30 December 2022 go-live; a request for
January to March 2022 returns nothing. Each alert is one row: locationName, permitNumber,
locationGridRef, x and y (British National Grid), receivingWaterCourse, alertType ("Start", "Stop",
"Offline start", "Offline stop") and datetime (UTC, no zone written). Pages hold at most 1,000 rows
(limit=5000 returns none), newest first; dateStart and dateEnd are inclusive days. One request per day,
paged by offset when a day has 1,000, so rows tied on a time never straddle two pages of a long window.
The portal asks for no more than 5 requests a second, but the API answers 429 well below that: three
readers at about 2 requests a second between them were refused for minutes on 19 Oct 2026, while one
reader at under 1 a second was not. Read with one process only.

Credit: Thames Water Utilities Limited, discharge alert stream, used under the Thames Water API
Portal's terms of use (https://docs.api.thameswater.co.uk/s/terms-of-service): a worldwide,
royalty-free licence to share and adapt, with attribution and no added restrictions. The licence is
not named; its wording is that of CC BY 4.0.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta

import httpx
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

PAGE = 1000
PAUSE_S = 0.25
TRIES = 8
LIMITED_WAIT_S = 60.0
FIRST_DAY = date(2022, 4, 1)
RAW_CACHE = config.CACHE / "thames_alerts"
CREDIT = ("Thames Water Utilities Limited, discharge alert stream (Open Data API), used under the Thames "
          "Water API Portal terms of use (https://docs.api.thameswater.co.uk/s/terms-of-service)")
FIELDS = ["locationName", "permitNumber", "locationGridRef", "x", "y", "receivingWaterCourse",
          "alertType", "datetime"]


def _day(client: httpx.Client, d: date) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"dateStart": d.isoformat(), "dateEnd": d.isoformat(), "limit": PAGE, "offset": offset}
        for attempt in range(TRIES):
            try:
                r = client.get(config.THAMES_ALERTS, params=params, timeout=120)
                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After") or LIMITED_WAIT_S)
                    log.warning("Thames alerts %s: 429, waiting %.0f s", d, wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                items = r.json().get("items", [])
                break
            except (httpx.HTTPError, ValueError) as e:
                log.warning("Thames alerts %s offset %d failed (%s); retry", d, offset, e)
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"Thames alerts {d}: {TRIES} failures")
        rows.extend(items)
        time.sleep(PAUSE_S)
        if len(items) < PAGE:
            return rows[::-1]   # oldest first, alerts that share a minute in the stream's own order
        offset += PAGE


def fetch_month(year: int, month: int, refresh: bool = False) -> pd.DataFrame:
    """Every alert dated in one month, cached in data/cache/thames_alerts/ once the month is over."""
    RAW_CACHE.mkdir(parents=True, exist_ok=True)
    path = RAW_CACHE / f"{year}-{month:02d}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    first = date(year, month, 1)
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    today = datetime.now(UTC).date()
    rows: list[dict] = []
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}) as c:
        d = first
        while d <= min(last, today):
            rows.extend(_day(c, d))
            d += timedelta(days=1)
    df = pd.DataFrame(rows, columns=FIELDS)
    if last < today:
        df.to_parquet(path, index=False)
    log.info("Thames alerts %d-%02d: %d rows", year, month, len(df))
    return df


def fetch_alerts(start: date = FIRST_DAY, end: date | None = None, refresh: bool = False) -> pd.DataFrame:
    """Every alert from `start`'s month to `end`'s, repeats dropped, oldest first."""
    end = end or datetime.now(UTC).date()
    frames = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        frames.append(fetch_month(y, m, refresh=refresh))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    df["time"] = pd.to_datetime(df["datetime"], format="ISO8601").dt.tz_localize("UTC")
    return df.sort_values(["permitNumber", "locationName", "time"], kind="stable").reset_index(drop=True)


def alerts_to_events(alerts: pd.DataFrame) -> pd.DataFrame:
    """One row per discharge: each "Start" with the next alert at the same location if that is a "Stop"
    (the portal: "A 'start' event is invariably followed by a 'stop' event"; an offline start that cuts
    a discharge comes with a stop at the same time). A start with no stop after it (still running when
    read, or followed by another start) keeps an empty end. Alerts in the same minute keep the order
    fetch_alerts gives them. A location is permitNumber with
    locationName, because some temporary permits cover more than one outlet. Columns: location,
    site_name, permit, x, y, event_start, event_end, duration_h."""
    a = alerts.copy()
    a["kind"] = a["alertType"].str.lower().str.strip()
    a["location"] = a["permitNumber"].astype(str) + "|" + a["locationName"].astype(str)
    a = a[a["kind"].isin(["start", "stop"])].sort_values(["location", "time"], kind="stable")
    nxt = a.groupby("location")[["kind", "time"]].shift(-1)
    starts = a[a["kind"] == "start"].copy()
    paired = nxt.loc[starts.index, "kind"] == "stop"
    starts["event_end"] = nxt.loc[starts.index, "time"].where(paired)
    ev = starts.rename(columns={"time": "event_start", "locationName": "site_name", "permitNumber": "permit"})
    ev["duration_h"] = (ev["event_end"] - ev["event_start"]).dt.total_seconds() / 3600.0
    return ev[["location", "site_name", "permit", "x", "y", "event_start", "event_end", "duration_h"]] \
        .reset_index(drop=True)

