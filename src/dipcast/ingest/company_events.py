"""The companies' own 2025-26 event layers that the EA start/stop files duplicate or run past: Anglian Water's
monthly layers (April 2025 to July 2026), Severn Trent Water 2025, Wessex Water 2025 and 2026 to date, and
Yorkshire Water's "Event Duration Monitoring History" (2026 to date). All are CC BY 4.0 (LAYERS' credits; the
licence text as read on 13 Nov 2026 is in docs/EVENT-RECORDS-2026-11.md).

They are read into their own data/processed/company_events_<company>.parquet in the edm_events columns, never into
edm_events.parquet or the EA files, so nothing here trains or scores a model (scripts/import_company_events.py).

Each read is checked against the layer: the rows fetched must equal the layer's count with no repeated object id,
or it stops. A fetch stops at the first refusal (any HTTP status other than 200, or an ArcGIS error body) and at a
stated request cap, and every request is logged to a ledger.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
from pathlib import Path

import httpx
import pandas as pd

from dipcast import config
from dipcast.ingest.edm_events import COLS, _id_map, stream_times

log = logging.getLogger(__name__)

STREAM = config.STREAM_BASE
WESSEX = "https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services"
YORKSHIRE = "https://services-eu1.arcgis.com/1WqkK5cDKUbF0CkH/arcgis/rest/services"
CC_BY = "licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"


def _layer(company, item, url, site, start, end, lat, lon, months, credit, oid="FID", extra=()):
    return {"company": company, "item": item, "url": url, "oid": oid,
            "fields": {"site_id": site, "event_start": start, "event_end": end, "lat": lat, "lon": lon},
            "extra": list(extra), "months": months, "credit": credit}


def _anglian(item, service, months, title, site="SITE_CODE", start="START_DATE_TIME", end="END_DATE_TIME",
             lat="Column1", lon="Column2"):
    return _layer("Anglian Water", item, f"{STREAM}/{service}/FeatureServer/0", site, start, end, lat, lon, months,
                  f"Anglian Water Event Duration Monitoring ({title}), Anglian Water, via Stream, {CC_BY}")


# Source name -> layer. `months` is the span the title states ("YYYY-MM", first and last), used to check, and for
# Anglian to repair, the dates. Field names differ from layer to layer, even within one company's monthly series.
LAYERS: dict[str, dict] = {
    "Anglian Water 2025-04 to 2025-10": _anglian(
        "1c54905839b341439f83ae5e874924c0", "April_to_October_EDM_for_STREAM", ("2025-04", "2025-10"),
        "Monthly April 2025 to October 2025", site="SiteId", start="EventStart", end="EventEnd",
        lat="OutfallLatitude", lon="OutfallLongtitude"),
    "Anglian Water 2025-11": _anglian(
        "9715999f8a3c44c99247cc9a79638ce0", "Event_Duration_Monitoring_Monthly_(November_2025)",
        ("2025-11", "2025-11"), "Monthly November 2025"),
    "Anglian Water 2025-12": _anglian(
        "44ef5fb6ef0c414b95d6e58a704ab911", "December_EDM_for_Stream", ("2025-12", "2025-12"),
        "Monthly December 2025", lat="Column_1", lon="Column_2"),
    "Anglian Water 2026-01": _anglian(
        "0ebb95a1d23b4583a8eeb89d6d5087be", "January_EDM_for_Stream", ("2026-01", "2026-01"),
        "Monthly January 2026"),
    "Anglian Water 2026-02": _anglian(
        "d34e2e2acd3a4e75880c9c4888d9a03a", "February_EDM_for_Stream", ("2026-02", "2026-02"),
        "Monthly February 2026"),
    "Anglian Water 2026-03": _anglian(
        "05c079a7acc34646a837e83a34d08eb1", "March_EDM_for_Stream", ("2026-03", "2026-03"),
        "Monthly March 2026", lat="Lat", lon="Long"),
    "Anglian Water 2026-04": _anglian(
        "418057ac8d5c431987331dd53e433615", "April_EDM_For_Stream", ("2026-04", "2026-04"),
        "Monthly April 2026", site="SiteId", start="EventStart", end="EventEnd",
        lat="OutfallLatitude", lon="OutfallLongitude"),
    "Anglian Water 2026-05 to 2026-06": _anglian(
        "64de10fa1f06437197a33961ca26e471", "May_to_June_EDM_for_STREAM", ("2026-05", "2026-06"),
        "Monthly May and June 2026", site="SiteID", start="EventStart", end="EventEnd",
        lat="OutfallLatitude", lon="Outfall_Longtitude"),
    "Anglian Water 2026-07": _anglian(
        "a5455681629943aeac94d58664874a14", "Anglian_Water_Event_Duration_Monitoring_(Monhly_July_2026)",
        ("2026-07", "2026-07"), "Monthly July 2026", site="SiteId", start="EventStart", end="EventEnd",
        lat="OutfallLatitude", lon="OutfallLongtitude"),
    "Severn Trent Water 2025": _layer(
        "Severn Trent Water", "5ab094ee53ba421fa99ebd4843cb27e7", f"{STREAM}/STW_Edm_2025/FeatureServer/0",
        "SiteId", "EventStart", "EventEnd", "OutfallLatitude", "OutfallLongitude", ("2025-01", "2025-12"),
        f"Severn Trent Water Event Duration Monitoring 2025, Severn Trent Water, via Stream, {CC_BY}",
        extra=("SiteName",)),
    "Wessex Water 2025": _layer(
        "Wessex Water", "8cb7cef582b34c81994d75bc7f6355ee",
        f"{WESSEX}/Wessex_Water_Event_Duration_Monitoring_2025_view/FeatureServer/0",
        "SiteId", "EventStart", "EventEnd", "OutfallLatitude", "OutfallLongitude", ("2025-01", "2025-12"),
        f"Wessex Water Event Duration Monitoring 2025 © 2025 by Wessex Water, {CC_BY}",
        oid="OBJECTID", extra=("SiteName", "EventId", "EventVerified")),
    "Wessex Water 2026": _layer(
        "Wessex Water", "10f23bbd5086440891be031405185133",
        f"{WESSEX}/Wessex_Water_Event_Duration_Monitoring_2026_view2/FeatureServer/0",
        "SiteId", "EventStart", "EventEnd", "OutfallLatitude", "OutfallLongitude", ("2026-01", "2026-12"),
        f"Wessex Water Event Duration Monitoring Monthly 2026 © 2026 by Wessex Water, {CC_BY}",
        oid="OBJECTID", extra=("SiteName", "EventId", "EventVerified")),
    "Yorkshire Water 2026": _layer(
        "Yorkshire Water", "aefd77a821124897afc69362d5676236",
        f"{YORKSHIRE}/Event Duration Monitoring History/FeatureServer/0",
        "SiteId", "EventStart", "EventEnd", "OutfallLatitude", "OutfallLongitude", ("2026-01", "2026-12"),
        f"Event Duration Monitoring History © 2026 by Yorkshire Water, {CC_BY}",
        oid="OBJECTID", extra=("SiteName", "EventID", "EventVerified")),
}

RAW_CACHE = config.CACHE / "company_events"
PAGE = 2000


class Refused(RuntimeError):
    """A request the server refused, or the request cap reached: the fetch stops here."""


class Ledger:
    """Every request, one JSON line each, and a cap on how many may be sent."""

    def __init__(self, path: Path, cap: int, pace: float = 0.5):
        self.path, self.cap, self.pace, self.sent = Path(path), cap, pace, 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, client: httpx.Client, url: str, params: dict) -> dict:
        if self.sent >= self.cap:
            raise Refused(f"request cap {self.cap} reached")
        self.sent += 1
        t0 = time.time()
        r = client.get(url, params=params, timeout=120)
        rec = {"utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "url": url,
               "offset": params.get("resultOffset"), "status": r.status_code, "bytes": len(r.content),
               "secs": round(time.time() - t0, 2)}
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        time.sleep(self.pace)
        if r.status_code != 200:
            raise Refused(f"HTTP {r.status_code} from {url}")
        body = r.json()
        if "error" in body:
            raise Refused(f"ArcGIS error {body['error']} from {url}")
        return body


def raw_path(source: str) -> Path:
    return RAW_CACHE / (source.replace(" ", "_") + ".parquet")


def fetch_layer(source: str, ledger: Ledger, refresh: bool = False) -> pd.DataFrame:
    """The layer's rows as it gives them (dates as epoch milliseconds), cached in RAW_CACHE. Paged by object id
    order; the read must hold exactly the layer's count of distinct object ids, or it stops."""
    lay, path = LAYERS[source], raw_path(source)
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    oid = lay["oid"]
    fields = [oid, *lay["fields"].values(), *lay["extra"]]
    with httpx.Client(headers={"User-Agent": config.USER_AGENT}, follow_redirects=True) as c:
        n_layer = ledger.get(c, f"{lay['url']}/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]
        rows, offset = [], 0
        while True:
            body = ledger.get(c, f"{lay['url']}/query", {
                "where": "1=1", "outFields": ",".join(fields), "returnGeometry": "false", "orderByFields": oid,
                "resultOffset": offset, "resultRecordCount": PAGE, "f": "json"})
            feats = [f["attributes"] for f in body.get("features", [])]
            rows += feats
            offset += len(feats)
            if not feats or (len(feats) < PAGE and not body.get("exceededTransferLimit")):
                break
    raw = pd.DataFrame(rows, columns=fields)
    check_read(raw, oid, n_layer, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(path, index=False)
    log.info("%s: %d rows", source, len(raw))
    return raw


def check_read(raw: pd.DataFrame, oid: str, n_layer: int, source: str) -> None:
    """Stop unless the read holds the layer's count of rows, each with its own object id."""
    if not len(raw) == raw[oid].nunique() == n_layer:
        raise RuntimeError(f"{source}: layer {n_layer}, fetched {len(raw)}, distinct ids {raw[oid].nunique()}")


def _months(span: tuple[str, str]) -> tuple[pd.Period, pd.Period]:
    return pd.Period(span[0], "M"), pd.Period(span[1], "M")


def swap_day_month(t: pd.Series, span: tuple[str, str]) -> tuple[pd.Series, int]:
    """Times outside the layer's stated months whose day and month, swapped, put them inside it, swapped back.
    Two of Anglian Water's monthly layers (December 2025, March 2026) were built with day-first text read as
    month-first: a 1 March start is stored as 3 January, and only days 1 to 12 are affected. Returns the times
    and how many were swapped. A time outside the months that a swap does not bring inside is left as it is."""
    lo, hi = _months(span)
    p = t.dt.tz_localize(None).dt.to_period("M")
    outside = t.notna() & ((p < lo) | (p > hi)) & (t.dt.day <= 12)
    if not outside.any():
        return t, 0
    s = t[outside]
    swapped = pd.to_datetime(dict(year=s.dt.year, month=s.dt.day, day=s.dt.month, hour=s.dt.hour,
                                  minute=s.dt.minute, second=s.dt.second), utc=True, errors="coerce")
    sp = swapped.dt.tz_localize(None).dt.to_period("M")
    ok = swapped.notna() & (sp >= lo) & (sp <= hi)
    out = t.copy()
    out.loc[ok[ok].index] = swapped[ok]
    return out, int(ok.sum())


def london_wall_as_utc(t: pd.Series) -> pd.Series:
    """The UK wall-clock reading of each time, taken as UTC. Anglian Water's monthly layers hold GMT text that was
    stored as if it were UK local time: in summer each stored time is an hour early (measured against the EA's 2026
    file, docs/EVENT-RECORDS-2026-11.md), and the May-June 2026 layer starts at 30 April 23:00 UTC. Winter times are
    unchanged."""
    return t.dt.tz_convert("Europe/London").dt.tz_localize(None).dt.tz_localize("UTC")


def normalise(raw: pd.DataFrame, source: str, remap_ids: bool = True) -> tuple[pd.DataFrame, dict]:
    """One layer's raw rows in the edm_events columns, and what was done to them (counts)."""
    lay = LAYERS[source]
    f = lay["fields"]
    df = pd.DataFrame({k: raw[v] for k, v in f.items()})
    df["site_name"] = raw["SiteName"] if "SiteName" in raw else None
    df["site_id"] = df["site_id"].astype("string").str.strip()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["event_start"] = stream_times(df["event_start"])
    df["event_end"] = stream_times(df["event_end"])
    notes = {"rows": len(df), "swapped_start": 0, "swapped_end": 0}
    if lay["company"] == "Anglian Water":
        # Back to the text's own reading first, so that a swapped date is not left an hour out.
        df["event_start"], df["event_end"] = london_wall_as_utc(df["event_start"]), london_wall_as_utc(df["event_end"])
        df["event_start"], notes["swapped_start"] = swap_day_month(df["event_start"], lay["months"])
        # An end may fall in the next month; allow one month past the stated span.
        lo, hi = lay["months"]
        df["event_end"], notes["swapped_end"] = swap_day_month(
            df["event_end"], (lo, str(pd.Period(hi, "M") + 1)))
    if remap_ids:
        m = _id_map()
        if m:
            df["site_id"] = df["site_id"].map(m).fillna(df["site_id"])
    df["source"] = source
    n0 = len(df)
    df = df.dropna(subset=["site_id", "event_start"])
    notes["no_id_or_start"] = n0 - len(df)
    df["duration_h"] = (df["event_end"] - df["event_start"]).dt.total_seconds() / 3600.0
    bad = df["duration_h"].notna() & ((df["duration_h"] < 0) | (df["duration_h"] >= 24 * 60))
    notes["negative_or_over_60_days"] = int(bad.sum())
    df = df[~bad]
    n1 = len(df)
    df = df.drop_duplicates(["site_id", "event_start", "event_end"])
    notes["repeated"] = n1 - len(df)
    lo, hi = _months(lay["months"])
    p = df["event_start"].dt.tz_localize(None).dt.to_period("M")
    notes["start_outside_stated_months"] = int(((p < lo) | (p > hi)).sum())
    notes["kept"] = len(df)
    return df[COLS].sort_values(["site_id", "event_start"]).reset_index(drop=True), notes


def coverage(ev: pd.DataFrame) -> pd.DataFrame:
    """Events and overflows by company and month of start (UTC)."""
    d = ev.assign(month=ev["event_start"].dt.strftime("%Y-%m"))
    return (d.groupby(["company", "month"]).agg(events=("site_id", "size"), overflows=("site_id", "nunique"))
            .reset_index())
