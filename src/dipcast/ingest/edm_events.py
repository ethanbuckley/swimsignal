"""Pull event-level spill history (one row per discharge event).

United Utilities' files (config.EDM_EVENT_FEEDS) train the spill model. Hafren Dyfrdwy's 2025 file
(fetch_hd_events) is a Welsh test set only, kept apart in data/processed/hd_events.parquet so it
never enters training. Its credit: "Hafren Dyfrdwy Event Duration Monitoring 2025", Hafren
Dyfrdwy, published on Stream, licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).

The Environment Agency's start/stop files for Dŵr Cymru Welsh Water's overflows in England
(read_ea_dcww_events) are a second Welsh-company test set, kept apart in
data/processed/dcww_ea_events.parquet. Their credit: "© Environment Agency copyright and/or
database right", Open Government Licence v3.0, from the EA dataset "Event Duration
Monitoring-Storm Overflow-Start/Stop Detailed Data".
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


# The EA's start/stop files for Dwr Cymru Welsh Water's overflows in England (checked 4 Oct 2026):
# 2024 (sheet Start_Stop, times as Excel dates), 2025 (StartStop, ISO text ending in "Z") and 2026 to
# date (one sheet per month or months, ISO text, sometimes an empty fifth column). Columns: Unique ID
# (DCW00019, the annual returns' site_id), site name, discharge start and finish, both headed "(GMT)".
# The files give no position; it comes from the annual returns.
EA_DCWW_SOURCE = "EA Welsh Water"
EA_DCWW_DATASET = "https://environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7"
EA_DCWW_CREDIT = ("© Environment Agency copyright and/or database right. Licensed under the Open "
                  "Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)")


def read_ea_dcww_events(paths, positions: pd.DataFrame | None = None) -> pd.DataFrame:
    """The EA's Welsh Water workbooks (`paths`), every sheet, in the fetch_events schema. Times are
    read as UTC, as the headings say. `positions` (site_id, lat, lon) defaults to the newest
    position of each id in annual_returns.parquet. For testing the model, never for training."""
    from openpyxl import load_workbook  # dev dependency; only this off-CI path needs it
    frames = []
    for path in paths:
        wb = load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [r[:4] for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]]
            df = pd.DataFrame(rows, columns=["site_id", "site_name", "event_start", "event_end"])
            df["source"] = f"{EA_DCWW_SOURCE} ({path.name if hasattr(path, 'name') else path})"
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["site_id"] = df["site_id"].astype(str).str.strip()
    # Cell by cell: the 2024 file holds Excel dates, the others ISO text. to_utc would read a column
    # of dates as epoch numbers.
    for c in ("event_start", "event_end"):
        df[c] = pd.to_datetime(df[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v),
                               utc=True, errors="coerce", format="ISO8601")
    if positions is None:
        ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet", columns=["site_id", "year", "lat", "lon"])
        positions = ar.dropna(subset=["site_id", "lat"]).sort_values("year").drop_duplicates("site_id", keep="last")
    df = df.merge(positions[["site_id", "lat", "lon"]], on="site_id", how="left")
    df = df.dropna(subset=["event_start"])
    df["duration_h"] = (df["event_end"] - df["event_start"]).dt.total_seconds() / 3600.0
    df = df[(df["duration_h"].isna()) | ((df["duration_h"] >= 0) & (df["duration_h"] < 24 * 60))]
    return df[COLS].sort_values(["site_id", "event_start"]).reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ev = fetch_events()
    write_parquet(ev, config.PROCESSED / "edm_events.parquet")
    print(ev.groupby("source").agg(events=("site_id", "size"), sites=("site_id", "nunique"),
                                    first=("event_start", "min"), last=("event_start", "max")))
