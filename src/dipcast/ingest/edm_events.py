"""Pull event-level spill history (one row per discharge event).

United Utilities' files (config.EDM_EVENT_FEEDS) train the spill model. Hafren Dyfrdwy's 2025 file
(fetch_hd_events) is a Welsh test set only, kept apart in data/processed/hd_events.parquet so it
never enters training. Its credit: "Hafren Dyfrdwy Event Duration Monitoring 2025", Hafren
Dyfrdwy, published on Stream, licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).
"""

from __future__ import annotations

import logging

import pandas as pd

from dipcast import config
from dipcast.arcgis import fetch_all
from dipcast.ingest.common import to_utc, write_parquet

log = logging.getLogger(__name__)

RENAME = {
    "SiteId": "site_id", "SiteName": "site_name", "OutfallLatitude": "lat",
    "OutfallLongitude": "lon", "EventStart": "event_start", "EventEnd": "event_end",
    "ReceivingWatercourse": "receiving_watercourse",
}
OUT_FIELDS = "SiteId,SiteName,OutfallLatitude,OutfallLongitude,EventStart,EventEnd,ReceivingWatercourse"
COLS = ["site_id", "site_name", "lat", "lon", "event_start", "event_end", "duration_h", "source"]


RAW_CACHE = config.CACHE / "edm"

# Hafren Dyfrdwy, the Severn Trent company that serves north-east and mid Wales. Not in Severn
# Trent's live feed or the EA's event files. Its 2025 file: 3,942 discharges at 43 site ids,
# EventStart/EventEnd as ISO text ending in "Z", latitude and longitude as text (checked 4 Oct 2026).
HD_SOURCE = "Hafren Dyfrdwy 2025"
HD_EVENTS_2025 = f"{config.STREAM_BASE}/HD_EDM_2025_Final_File/FeatureServer/0"
HD_LICENCE = "CC BY 4.0"
HD_CREDIT = ("Hafren Dyfrdwy Event Duration Monitoring 2025, Hafren Dyfrdwy, via Stream, "
             "licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)")


def _id_map() -> dict[str, str]:
    """Pre-2024 overflow IDs -> current IDs (Hub lookup table, then EA annual returns)."""
    m: dict[str, str] = {}
    ar_path = config.PROCESSED / "annual_returns.parquet"
    if ar_path.exists():
        ar = pd.read_parquet(ar_path, columns=["site_id", "old_site_id"]).dropna()
        m.update(dict(zip(ar["old_site_id"], ar["site_id"], strict=True)))
    lk_path = config.PROCESSED / "id_lookup.parquet"
    if lk_path.exists():
        lk = pd.read_parquet(lk_path).dropna()
        m.update(dict(zip(lk["old_site_id"], lk["site_id"], strict=True)))
    return m


def _normalise(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = df.rename(columns=RENAME)
    df["source"] = source
    # Hafren Dyfrdwy's layer stores the outfall position as text.
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    m = _id_map()
    if m:
        mapped = df["site_id"].map(m)
        n = int(mapped.notna().sum())
        if n:
            log.info("%s: remapped %d rows from pre-2024 IDs", source, n)
        df["site_id"] = mapped.fillna(df["site_id"])
    # Each feed has one timestamp encoding; normalise before any concatenation.
    df["event_start"] = to_utc(df["event_start"])
    df["event_end"] = to_utc(df["event_end"])
    df = df.dropna(subset=["site_id", "event_start"])
    df["duration_h"] = (df["event_end"] - df["event_start"]).dt.total_seconds() / 3600.0
    df = df[(df["duration_h"].isna()) | ((df["duration_h"] >= 0) & (df["duration_h"] < 24 * 60))]
    return df[COLS]


def fetch_events(feeds: dict[str, str] | None = None, refresh: bool = False,
                 out_fields: str = OUT_FIELDS) -> pd.DataFrame:
    feeds = feeds or config.EDM_EVENT_FEEDS
    RAW_CACHE.mkdir(parents=True, exist_ok=True)
    frames = []
    for source, url in feeds.items():
        raw_path = RAW_CACHE / (source.replace(" ", "_") + ".parquet")
        if raw_path.exists() and not refresh:
            raw = pd.read_parquet(raw_path)
            log.info("%s: %d events (cached)", source, len(raw))
        else:
            log.info("fetching %s ...", source)
            rows = fetch_all(
                url,
                geometry=False,
                out_fields=out_fields,
            )
            raw = pd.DataFrame(rows)
            raw.to_parquet(raw_path, index=False)
            log.info("%s: %d events", source, len(raw))
        frames.append(_normalise(raw, source))
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["site_id", "event_start"]).reset_index(drop=True)


def fetch_hd_events(refresh: bool = False) -> pd.DataFrame:
    """Hafren Dyfrdwy's 2025 discharges in the same schema as fetch_events (CC BY 4.0; see the
    module docstring for the credit). For testing the model in Wales, never for training."""
    # The layer has no ReceivingWatercourse field, and ArcGIS refuses a query that names one.
    return fetch_events({HD_SOURCE: HD_EVENTS_2025}, refresh=refresh,
                        out_fields=OUT_FIELDS.removesuffix(",ReceivingWatercourse"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ev = fetch_events()
    write_parquet(ev, config.PROCESSED / "edm_events.parquet")
    print(ev.groupby("source").agg(events=("site_id", "size"), sites=("site_id", "nunique"),
                                    first=("event_start", "min"), last=("event_start", "max")))
