"""Will the river at a spot rise in the next few hours? Coverage and arrival lags, for
docs/RIVER-RISES-SCOPE-2026-10.md.

    uv run python scripts/river_rises_coverage.py --cache <scratch dir> --out <scratch dir> \
        [--network data/processed/river_network.pkl] [--radar data/raw/met_office_radar] [--fetch]

Research only: nothing here feeds the site, a level, a word or a test window. No model is scored.

- **Spots:** the river spots in spots.csv and spots-osm.csv, placed with locate_pin and the build's
  hints (transport.spot_hints). Lakes are left out: the site's "high" and "rising fast" need a
  gauge on the spot's own river (flows.flow_state).
- **Spot gauge:** flows.station_pick, as the site picks it (15 km, the spot's river name), asked
  through the capped client below. "Usable" is the site's own test: the gauge is on the spot's
  river (names.same_river) and has a usual range.
- **Upstream gauges:** every Environment Agency level station (one request for the national list)
  snapped within GAUGE_SNAP_M of a river link and upstream of the spot gauge along the network,
  within UP_MAX_KM.
- **History:** the EA Hydrology API's 15-minute level series ("-level-i-900-...-qualified") for a
  bounded sample of spot-gauge / upstream-gauge pairs: its earliest reading, and its readings over
  WINDOW, from which coverage (share of 15-minute slots, gaps) and the arrival lag of the peak on
  past rises are measured.
- **Publication delay:** one request for the latest reading of every level measure (the call the
  site makes), and the age of each relevant gauge's latest reading at that moment.
- **Rain:** the Met Office radar month files already saved (read only, never fetched here).

Network caps, fixed before any request: at most MAX_REQUESTS a run, one at a time, PAUSE_S apart,
EA hosts only (no Open-Meteo, whose daily ledger is shared with the live site), stop at the first
403, 429 or 5xx, redirects never followed, every answer cached under --cache. Without --fetch only
cached answers are read: a missing one stops the run, so a rerun never reaches the network by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest import flows

# ------------------------------------------------------------------ network caps (stated first)
MAX_REQUESTS = 300            # per run, every host together; cached answers do not count
PAUSE_S = 1.5                 # between requests, one in flight at a time
TIMEOUT_S = 120.0
STOP_STATUS = {403, 429}      # and every 5xx: stop the run, ask nothing more
ALLOWED_HOSTS = {"environment.data.gov.uk"}

# ------------------------------------------------------------------ the prototype's fixed choices
SPOT_FILES = [config.ROOT / "spots.csv", config.ROOT / "spots-osm.csv"]
SPOT_GAUGE_KM = 15            # as the site asks (scripts/build_site.attach_river_levels)
GAUGE_SNAP_M = 250.0          # as scripts/glofas_check.py
RIVER_FORMS = ("inlandRiver", "tidalRiver", "canal")
UP_MAX_KM = 50.0              # upstream along the network: at 1 to 3 m/s, 5 to 14 hours of travel
SAME_SITE_KM = 0.5            # a station closer than this along the network is the same place
PAIR_MIN_KM = 3.0             # a pair's upstream gauge at least this far up ...
PAIR_MIN_AREA = 0.25          # ... with at least this share of the spot gauge's catchment ...
SAMPLE_PAIRS = 25             # ... and at most this many pairs, one per spot gauge
SAMPLE_SEED = 20261026
WINDOW = ("2025-10-01", "2026-10-25")   # readings asked for each sampled gauge
SLOT = pd.Timedelta(minutes=15)
DROP_QUALITY = {"Suspect", "Rejected", "Missing"}
GAP_H = 1.0                   # a gap of at least this many hours is counted
EVENT_SEP_H = 48.0            # spot-gauge rises closer than this are one event
PEAK_AFTER_H = 24.0           # the spot gauge's peak: the highest level this long after the onset
LAG_MAX_H = 36.0              # the upstream peak is looked for up to this long before the spot peak ...
LAG_NEG_H = 6.0               # ... and this long after it (a negative lag: upstream peaked later)
UP_RISE_WIN_H = 24.0          # the upstream gauge must rise this long before its own peak ...
WINDOW_PRESENT = 0.8          # ... and have this share of readings in the windows looked at
XCORR_PAD_H = (24.0, 36.0)    # cross-correlation window: this long before and after the onset

FM = config.EA_FLOOD_MONITORING
HY = config.EA_HYDROLOGY


class Stop(RuntimeError):
    """The run stops: a cap, a refused or failed answer, or a missing cache entry without --fetch."""


class CappedClient:
    """GET with a file cache and the caps above. Every request (not cache reads) is logged to
    <cache>/requests.log. A non-200 answer that is not a stop (a 404) is cached as that status."""

    def __init__(self, cache: Path, fetch: bool, http: httpx.Client | None = None, cap: int = MAX_REQUESTS,
                 pause_s: float = PAUSE_S, sleep=time.sleep):
        self.cache, self.fetch, self.cap, self.pause_s, self.sleep = cache, fetch, cap, pause_s, sleep
        self.http = http or httpx.Client(timeout=TIMEOUT_S, headers=config.EA_HEADERS, follow_redirects=False)
        self.n, self.stopped = 0, None
        cache.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(url: str, params: dict | None) -> str:
        p = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
        return hashlib.sha256(f"{url}?{p}".encode()).hexdigest()[:24]

    def get(self, url: str, params: dict | None = None) -> tuple[int, str]:
        """(status, body) from the cache, else from one request within the caps."""
        k = self.key(url, params)
        meta, body = self.cache / f"{k}.json", self.cache / f"{k}.body"
        if meta.exists():
            m = json.loads(meta.read_text())
            return m["status"], body.read_text() if body.exists() else ""
        if self.stopped:
            raise Stop(f"stopped earlier: {self.stopped}")
        if not self.fetch:
            raise Stop(f"not cached: {url} {params or ''}; rerun with --fetch to ask for it")
        host = urlsplit(url).hostname
        if urlsplit(url).scheme != "https" or host not in ALLOWED_HOSTS:
            raise Stop(f"not an allowed https host: {url}")
        if self.n >= self.cap:
            self.stopped = f"request cap {self.cap} reached"
            raise Stop(self.stopped)
        if self.n:
            self.sleep(self.pause_s)
        self.n += 1
        at = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            r = self.http.get(url, params=params)
        except httpx.HTTPError as e:
            self.stopped = f"{type(e).__name__} for {url}"
            self._log(at, "ERR", 0, url, params)
            raise Stop(self.stopped) from e
        self._log(at, r.status_code, len(r.content), url, params)
        if r.status_code in STOP_STATUS or r.status_code >= 500 or 300 <= r.status_code < 400:
            self.stopped = f"HTTP {r.status_code} for {url}"
            raise Stop(self.stopped)
        if r.status_code == 200:
            body.write_text(r.text)
        meta.write_text(json.dumps({"url": url, "params": params, "status": r.status_code, "at": at}))
        return r.status_code, r.text if r.status_code == 200 else ""

    def get_json(self, url: str, params: dict | None = None) -> dict | None:
        status, text = self.get(url, params)
        return json.loads(text) if status == 200 else None

    def response(self, url: str, params: dict | None = None, **_) -> httpx.Response:
        """An httpx.Response, for code that calls httpx.get (flows.station_pick)."""
        status, text = self.get(url, params)
        return httpx.Response(status, text=text, request=httpx.Request("GET", url, params=params))

    def _log(self, at, status, size, url, params) -> None:
        with open(self.cache / "requests.log", "a") as f:
            f.write(f"{at}\t{status}\t{size}\t{url}\t{json.dumps(params or {}, sort_keys=True)}\n")


@contextmanager
def routed(client: CappedClient):
    """flows' requests (station_pick) through the capped client, for the length of the block."""
    real = flows.httpx.get
    flows.httpx.get = client.response
    try:
        yield
    finally:
        flows.httpx.get = real


# ------------------------------------------------------------------ series: coverage, events, lags
def to_grid(readings: pd.DataFrame, start, end) -> pd.Series:
    """Readings (dateTime, value, quality) as a 15-minute series from `start` to `end` (UTC), NaN
    where there is no usable reading. Quality in DROP_QUALITY is dropped; a reading off the grid is
    put on the slot it falls in (the first kept)."""
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    grid = pd.date_range(start, end, freq=SLOT, inclusive="left")
    if readings.empty:
        return pd.Series(np.nan, index=grid)
    q = readings.copy()
    q["t"] = pd.to_datetime(q["dateTime"], utc=True, errors="coerce").dt.floor(SLOT)
    q["v"] = pd.to_numeric(q["value"], errors="coerce")
    keep = q["t"].notna() & q["v"].notna()
    if "quality" in q:
        keep &= ~q["quality"].fillna("").isin(DROP_QUALITY)
    q = q[keep].drop_duplicates("t")
    return q.set_index("t")["v"].reindex(grid)


def gap_runs(present: np.ndarray) -> list[int]:
    """The lengths, in slots, of each run of missing slots."""
    runs, n = [], 0
    for p in present:
        if p:
            if n:
                runs.append(n)
            n = 0
        else:
            n += 1
    if n:
        runs.append(n)
    return runs


def coverage(s: pd.Series) -> dict:
    """Share of 15-minute slots with a reading, gaps of GAP_H or more, the longest gap, and the
    first and last reading."""
    present = s.notna().to_numpy()
    runs = gap_runs(present)
    per_h = pd.Timedelta(hours=1) / SLOT
    ok = s.dropna()
    return {"slots": int(len(s)), "share": round(float(present.mean()), 4) if len(s) else 0.0,
            "gaps_1h": sum(r >= GAP_H * per_h for r in runs),
            "longest_gap_h": round(max(runs, default=0) / per_h, 2),
            "first": ok.index[0].isoformat() if len(ok) else None,
            "last": ok.index[-1].isoformat() if len(ok) else None}


def slots(hours: float) -> int:
    return int(round(pd.Timedelta(hours=hours) / SLOT))


def rise_onsets(s: pd.Series, rng: float, share: float = flows.RISING_SHARE,
                window_h: float = flows.RISE_WINDOW_H, sep_h: float = EVENT_SEP_H) -> list[pd.Timestamp]:
    """Times the level first rose more than `share` of `rng` over the last `window_h` hours (the
    site's "rising fast" rule, on a regular series), at most one per `sep_h`."""
    if not rng or rng <= 0:
        return []
    rise = s - s.shift(slots(window_h))
    hits = rise.index[(rise > share * rng).to_numpy()]
    out: list[pd.Timestamp] = []
    for t in hits:
        if not out or t - out[-1] >= pd.Timedelta(hours=sep_h):
            out.append(t)
    return out


def _span(s: pd.Series, a, b) -> pd.Series:
    return s.loc[a:b]


def event_lag(down: pd.Series, up: pd.Series, onset: pd.Timestamp, up_rng: float,
              share: float = flows.RISING_SHARE) -> dict:
    """For one spot-gauge onset: its peak in the PEAK_AFTER_H after the onset; the upstream peak
    from LAG_MAX_H before that to LAG_NEG_H after; the lag (spot peak minus upstream peak, hours,
    positive when the upstream peak came first). The upstream gauge counts as having risen only if
    it rose more than `share` of `up_rng` in the UP_RISE_WIN_H before its peak. `why` says why a
    lag is missing."""
    d = _span(down, onset, onset + pd.Timedelta(hours=PEAK_AFTER_H))
    if d.notna().mean() < WINDOW_PRESENT:
        return {"why": "spot gauge readings missing"}
    t_d = d.idxmax()
    u = _span(up, t_d - pd.Timedelta(hours=LAG_MAX_H), t_d + pd.Timedelta(hours=LAG_NEG_H))
    if len(u) == 0 or u.notna().mean() < WINDOW_PRESENT:
        return {"why": "upstream readings missing", "down_peak": t_d}
    t_u = u.idxmax()
    before = _span(up, t_u - pd.Timedelta(hours=UP_RISE_WIN_H), t_u)
    rose = bool(up_rng and up_rng > 0 and (up.loc[t_u] - before.min()) > share * up_rng)
    lag = (t_d - t_u) / pd.Timedelta(hours=1)
    out = {"why": "" if rose else "no upstream rise", "down_peak": t_d, "up_peak": t_u, "lag_h": float(lag)}
    # how long before the spot gauge's own "rising fast" onset the upstream gauge met the same rule
    u_rise = up - up.shift(slots(flows.RISE_WINDOW_H))
    u_hit = _span(u_rise, onset - pd.Timedelta(hours=LAG_MAX_H), onset)
    first = u_hit.index[(u_hit > share * up_rng).to_numpy()] if up_rng else []
    out["onset_lead_h"] = float((onset - first[0]) / pd.Timedelta(hours=1)) if len(first) else None
    return out


def xcorr_lag(down: pd.Series, up: pd.Series, onset: pd.Timestamp, max_h: float = LAG_MAX_H) -> float | None:
    """The lag (hours, 0 to `max_h`) at which the upstream gauge's 15-minute changes best match the
    spot gauge's, around one onset. A secondary measure; None with too few readings."""
    a, b = onset - pd.Timedelta(hours=XCORR_PAD_H[0]), onset + pd.Timedelta(hours=XCORR_PAD_H[1])
    dd = down.loc[a - SLOT:b].diff().loc[a:b]
    du = up.loc[a - pd.Timedelta(hours=max_h) - SLOT:b].diff()   # on the regular grid, shift(k) is k slots
    best, best_r = None, -np.inf
    for k in range(0, slots(max_h) + 1):
        uu = du.shift(k).loc[a:b]
        ok = dd.notna() & uu.notna()
        if ok.sum() < slots(12) or dd[ok].std() == 0 or uu[ok].std() == 0:
            continue
        r = float(np.corrcoef(dd[ok], uu[ok])[0, 1])
        if r > best_r:
            best, best_r = k * SLOT / pd.Timedelta(hours=1), r
    return best


def empirical_range(s: pd.Series) -> float | None:
    """The 5th to 95th percentile spread of a series: a stand-in for a gauge's usual range."""
    v = s.dropna()
    if len(v) < 100:
        return None
    lo, hi = np.percentile(v, [5, 95])
    return float(hi - lo) if hi > lo else None


# ------------------------------------------------------------------ the evaluation's window builder
def issue_rows(series: dict[str, pd.Series], target: str, issues, rng: float, horizon_h: float,
               lookback_h: float = flows.RISE_WINDOW_H, delay_h: dict[str, float] | float = 0.0,
               share: float = flows.RISING_SHARE) -> pd.DataFrame:
    """One row per issue time: inputs from readings each gauge had published by then, and the label.

    A gauge's reading at time r counts at issue time t only if r <= t - delay (its publication
    delay, per gauge or one for all): nothing at or after that cut is read. Inputs per gauge: the
    last level before the cut (`<g>_level`), and its rise over the `lookback_h` hours to that
    reading (`<g>_rise`). The label (`rises`) is 1 when the target gauge's highest reading in
    (t, t + horizon_h] is more than `share` of `rng` above its last reading at or before t; None
    when either is missing. The label alone looks past t."""
    rows = []
    for t in pd.DatetimeIndex(issues):
        row = {"issue": t}
        for g, s in series.items():
            d = delay_h.get(g, 0.0) if isinstance(delay_h, dict) else delay_h
            cut = t - pd.Timedelta(hours=d)
            seen = s.loc[:cut].dropna()
            seen = seen[seen.index <= cut]
            if seen.empty:
                row[f"{g}_level"], row[f"{g}_rise"] = None, None
                continue
            last_t, last_v = seen.index[-1], float(seen.iloc[-1])
            prior = seen[seen.index <= last_t - pd.Timedelta(hours=lookback_h)]
            row[f"{g}_level"] = last_v
            row[f"{g}_rise"] = last_v - float(prior.iloc[-1]) if len(prior) else None
        s = series[target]
        now = s.loc[:t].dropna()
        ahead = s.loc[t:t + pd.Timedelta(hours=horizon_h)].dropna()
        ahead = ahead[ahead.index > t]
        row["rises"] = (int(float(ahead.max()) - float(now.iloc[-1]) > share * rng)
                        if len(now) and len(ahead) and rng and rng > 0 else None)
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ EA parsing
def level_measure_900(station: dict) -> str | None:
    """A Hydrology station's 15-minute level measure ("...-level-i-900-<unit>-qualified")."""
    ms = station.get("measures")
    ms = ms if isinstance(ms, list) else [ms] if isinstance(ms, dict) else []
    found = []
    for m in ms:
        mid = str(m.get("@id", "") if isinstance(m, dict) else m).rstrip("/").rsplit("/", 1)[-1]
        if re.fullmatch(r"[A-Za-z0-9-]+-level-i-900-[A-Za-z]+-qualified", mid):
            found.append(mid)
    return sorted(found, key=lambda m: (not m.endswith("-m-qualified"), m))[0] if found else None


def hydrology_index(items: list[dict]) -> dict[str, dict]:
    """Hydrology stations by every id they carry that the flood-monitoring API also uses
    (stationReference, wiskiID, RLOIid), each with its 15-minute level measure and opening date."""
    out = {}
    for st in items:
        rec = {"measure": level_measure_900(st), "opened": st.get("dateOpened"), "label": st.get("label")}
        for k in ("stationReference", "wiskiID", "RLOIid"):
            v = st.get(k)
            for x in (v if isinstance(v, list) else [v]):
                if x not in (None, ""):
                    out.setdefault(f"{k}:{x}", rec)
    return out


def hydrology_for(fm_station: dict, index: dict[str, dict]) -> dict | None:
    for k in ("stationReference", "wiskiID", "RLOIid"):
        v = fm_station.get(k)
        hit = index.get(f"{k}:{v}") if v not in (None, "") else None
        if hit and hit.get("measure"):
            return hit
    return None


def read_csv_readings(text: str) -> pd.DataFrame:
    if not text.strip():
        return pd.DataFrame(columns=["dateTime", "value", "quality"])
    return pd.read_csv(io.StringIO(text), dtype=str)


def hours(a, b) -> float:
    return (pd.Timestamp(a) - pd.Timestamp(b)) / pd.Timedelta(hours=1)


# ------------------------------------------------------------------ the run
def spots_frame() -> pd.DataFrame:
    spots = pd.concat([pd.read_csv(p) for p in SPOT_FILES if p.exists()], ignore_index=True).fillna("")
    return spots[~spots["id"].duplicated()]


def run(args) -> dict:
    from dipcast.ingest.rainfall import cell_key, grid_cell
    from dipcast.model import transport as T
    from dipcast.network.names import same_river
    from dipcast.network.rivers import RiverNetwork, lonlat_to_bng

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from glofas_check import catchment_at, km

    client = CappedClient(args.cache, args.fetch)
    out, summary = args.out, {"stopped": None}
    out.mkdir(parents=True, exist_ok=True)
    net = RiverNetwork.load(args.network)
    spots = spots_frame()
    rows = []
    try:
        # 1. spot -> the site's gauge
        for r in spots.itertuples(index=False):
            rec = {"id": r.id, "name": r.name, "kind": r.kind, "river": r.river, "lat": float(r.lat), "lon": float(r.lon)}
            if r.kind != "river":
                continue
            kind, river_hint = T.spot_hints(r.kind, r.river)
            pin = T.locate_pin(net, rec["lon"], rec["lat"], kind_hint=kind, river_hint=river_hint, name=r.name)
            river = r.river or pin.watercourse
            rec.update(watercourse=pin.watercourse, pin_mode=pin.mode,
                       spot_link=pin.snap.link_id if pin.snap else None, spot_frac=pin.snap.frac if pin.snap else None)
            cell = grid_cell(rec["lat"], rec["lon"])
            rec["radar_months"] = len(list(args.radar.glob(f"radar_{cell_key(float(cell[0]), float(cell[1]))}_*.parquet"))) if args.radar else None
            with routed(client):
                try:
                    p = flows.station_pick(rec["lat"], rec["lon"], SPOT_GAUGE_KM, river or None)
                except httpx.HTTPStatusError as e:
                    rows.append({**rec, "why": f"stations request {e.response.status_code}"})
                    continue
            if p is None:
                rows.append({**rec, "why": "no gauge with a scale within 15 km"})
                continue
            same = same_river(river, p["river"]) if river else None
            rng = (p["typical_high"] - p["typical_low"]) if None not in (p["typical_low"], p["typical_high"]) else None
            usable = same is True and rng is not None and rng > 0
            rows.append({**rec, "gauge": p["ref"], "gauge_label": p["station"], "gauge_river": p["river"],
                         "g_lat": p["lat"], "g_lon": p["lon"], "typical_low": p["typical_low"],
                         "typical_high": p["typical_high"], "gauge_measure": (p["measures"] or [None])[0],
                         "same_river": same, "gauge_km": round(km(rec["lat"], rec["lon"], p["lat"], p["lon"]), 2),
                         "why": "" if usable else ("gauge on another river" if same is not True else "no usual range")})
        spots_df = pd.DataFrame(rows)

        # 2. every level station, and the ones upstream of each usable spot gauge
        fm = client.get_json(f"{FM}/id/stations", {"parameter": "level", "type": "SingleLevel", "_limit": 10000})
        fm_items = [s for s in (fm or {}).get("items", []) if isinstance(s.get("lat"), (int, float)) and isinstance(s.get("long"), (int, float))]
        fm_by_ref = {s.get("stationReference"): s for s in fm_items}
        usable = spots_df[spots_df["why"] == ""]
        gauges = usable.drop_duplicates("gauge")
        near = [s for s in fm_items if any(km(s["lat"], s["long"], g.g_lat, g.g_lon) <= UP_MAX_KM for g in gauges.itertuples())]
        snaps = {}
        for s in near + [{"stationReference": g.gauge, "lat": g.g_lat, "long": g.g_lon} for g in gauges.itertuples()]:
            x, y = lonlat_to_bng(float(s["long"]), float(s["lat"]))
            sn = net.snap_xy(x, y, max_m=GAUGE_SNAP_M, forms=RIVER_FORMS)
            if sn is not None:
                snaps[s.get("stationReference")] = (sn.link_id, sn.frac)
        ups = []
        near_by_ref = {s.get("stationReference"): s for s in near}
        for g in gauges.itertuples():
            if g.gauge not in snaps:
                ups.append({"gauge": g.gauge, "why": "spot gauge not on a river link"})
                continue
            area_g = catchment_at(net, *snaps[g.gauge])
            cands = {ref: snaps[ref] for ref, s in near_by_ref.items()
                     if ref != g.gauge and ref in snaps and km(s["lat"], s["long"], g.g_lat, g.g_lon) <= UP_MAX_KM}
            for ref, d in sorted(upstream_of(net, snaps[g.gauge], cands, UP_MAX_KM * 1000).items()):
                if d < SAME_SITE_KM * 1000:
                    continue
                s = near_by_ref[ref]
                area_u = catchment_at(net, *snaps[ref])
                ups.append({"gauge": g.gauge, "up": ref, "up_label": s.get("label"), "up_river": name_of(s.get("riverName")),
                            "along_km": round(d / 1000, 2), "area_ratio": round(area_u / area_g, 3) if area_g else None,
                            "same_name": same_river(name_of(s.get("riverName")), name_of(g.gauge_river)),
                            "why": ""})
        ups_df = pd.DataFrame(ups)

        # 3. the latest reading of every level measure, once: the age of each relevant one
        status, text = client.get(f"{FM}/data/readings", {"latest": "", "parameter": "level"})
        latest = flows._readings_by_measure(json.loads(text).get("items", [])) if status == 200 else {}
        meta = json.loads((client.cache / f"{client.key(f'{FM}/data/readings', {'latest': '', 'parameter': 'level'})}.json").read_text())
        fetched_at = pd.Timestamp(meta["at"])
        relevant = set(gauges["gauge"]) | (set(ups_df["up"].dropna()) if "up" in ups_df else set())
        ages = []
        for m, (t, _) in latest.items():
            ref = m.split("-level-", 1)[0]
            if ref in relevant and t:
                ages.append({"station": ref, "measure": m, "reading_at": t, "age_h": round(hours(fetched_at, t), 2),
                             "spot_gauge": ref in set(gauges["gauge"])})
        ages_df = pd.DataFrame(ages).drop_duplicates("station") if ages else pd.DataFrame()

        # 4. Hydrology: the 15-minute history, for a bounded sample of pairs
        hy = client.get_json(f"{HY}/id/stations.json", {"observedProperty": "waterLevel", "_limit": 10000})
        hindex = hydrology_index((hy or {}).get("items", []))
        cand = ups_df[(ups_df["why"] == "") & ups_df["same_name"] & (ups_df["along_km"] >= PAIR_MIN_KM)
                      & (ups_df["area_ratio"] >= PAIR_MIN_AREA)] if len(ups_df) else ups_df
        pairs = []
        for gref, grp in cand.groupby("gauge", sort=True):
            gd = fm_by_ref.get(gref) or {"stationReference": gref}
            hd = hydrology_for(gd, hindex)
            for u in grp.sort_values("along_km").itertuples():
                hu = hydrology_for(fm_by_ref.get(u.up, {"stationReference": u.up}), hindex)
                if hd and hu:
                    pairs.append({"gauge": gref, "up": u.up, "along_km": u.along_km, "area_ratio": u.area_ratio,
                                  "down_measure": hd["measure"], "up_measure": hu["measure"]})
                    break
        pairs_df = pd.DataFrame(pairs)
        if len(pairs_df) > SAMPLE_PAIRS:
            pairs_df = pairs_df.sample(SAMPLE_PAIRS, random_state=SAMPLE_SEED).sort_values("gauge")
        hy_cover = {g: hydrology_for(fm_by_ref.get(g, {"stationReference": g}), hindex) for g in gauges["gauge"]}

        series, cov, earliest = {}, [], {}
        for m in sorted(set(pairs_df.get("down_measure", [])) | set(pairs_df.get("up_measure", []))):
            e = client.get_json(f"{HY}/id/measures/{m}/readings.json", {"earliest": ""})
            items = (e or {}).get("items", [])
            earliest[m] = items[0].get("dateTime") if items else None
            status, text = client.get(f"{HY}/id/measures/{m}/readings.csv",
                                      {"mineq-date": WINDOW[0], "max-date": WINDOW[1], "_limit": 200000})
            df = read_csv_readings(text) if status == 200 else read_csv_readings("")
            s = to_grid(df, WINDOW[0], WINDOW[1])
            series[m] = s
            q = df["quality"].fillna("").value_counts().to_dict() if "quality" in df else {}
            cov.append({"measure": m, "earliest": earliest[m], "rows": int(len(df)), "quality": json.dumps(q), **coverage(s)})
        cov_df = pd.DataFrame(cov)
    except Stop as e:
        summary["stopped"] = str(e)
        print(f"stopped: {e}", file=sys.stderr)
        summary["requests"] = client.n
        (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        raise SystemExit(2)

    # 5. lags on past rises
    events = []
    for p in pairs_df.itertuples() if len(pairs_df) else []:
        d, u = series[p.down_measure], series[p.up_measure]
        g = usable[usable["gauge"] == p.gauge].iloc[0]
        rng = float(g.typical_high - g.typical_low)
        u_rng = empirical_range(u)
        for t0 in rise_onsets(d, rng):
            ev = event_lag(d, u, t0, u_rng) if u_rng else {"why": "upstream range unknown"}
            events.append({"gauge": p.gauge, "up": p.up, "along_km": p.along_km, "onset": t0,
                           "xcorr_lag_h": xcorr_lag(d, u, t0), **ev})
    ev_df = pd.DataFrame(events)
    range_check = []
    for p in pairs_df.itertuples() if len(pairs_df) else []:
        g = usable[usable["gauge"] == p.gauge].iloc[0]
        er = empirical_range(series[p.down_measure])
        range_check.append({"gauge": p.gauge, "ea_range": float(g.typical_high - g.typical_low), "p5_p95": er})

    spots_df.to_csv(out / "spots.csv", index=False)
    ups_df.to_csv(out / "upstream.csv", index=False)
    pairs_df.to_csv(out / "pairs.csv", index=False)
    cov_df.to_csv(out / "coverage.csv", index=False)
    ev_df.to_csv(out / "events.csv", index=False)
    ages_df.to_csv(out / "latest_ages.csv", index=False)
    pd.DataFrame(range_check).to_csv(out / "range_check.csv", index=False)
    summary.update(summarise(spots_df, ups_df, pairs_df, cov_df, ev_df, ages_df, hy_cover, range_check, gauges))
    summary["requests_this_run"] = client.n
    summary["requests_logged_total"] = sum(1 for _ in open(client.cache / "requests.log")) if (client.cache / "requests.log").exists() else 0
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    return summary


def name_of(v) -> str:
    """riverName is a string, a list of strings, or missing (None, or NaN from a table)."""
    if isinstance(v, list):
        return " / ".join(map(str, v))
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def upstream_of(net, gauge: tuple[str, float], cands: dict[str, tuple[str, float]], cap_m: float) -> dict[str, float]:
    """The candidates upstream of a gauge along the network within `cap_m`: {ref: metres}. Positions
    are (link id, fraction along the link in the direction of flow). One upstream trace per gauge."""
    lg, fg = gauge
    length = lambda link: float(net.links.at[link, "length"])  # noqa: E731
    up = net.upstream_edges(net.links.at[lg, "start_node"], cap_m)
    out = {}
    for ref, (lu, fu) in cands.items():
        if lu == lg:
            d = (fg - fu) * length(lg) if fu < fg else None
        elif lu in up:
            d = up[lu] + (1 - fu) * length(lu) + fg * length(lg)
        else:
            d = None
        if d is not None and d <= cap_m:
            out[ref] = d
    return out


def q(x, ps=(10, 25, 50, 75, 90)) -> dict:
    x = pd.Series(x, dtype=float).dropna()
    return {f"p{p}": round(float(np.percentile(x, p)), 2) for p in ps} if len(x) else {}


def summarise(spots_df, ups_df, pairs_df, cov_df, ev_df, ages_df, hy_cover, range_check, gauges) -> dict:
    usable = spots_df[spots_df["why"] == ""]
    ug = set(usable["gauge"])
    have_up = set(ups_df.loc[ups_df["why"] == "", "gauge"]) if len(ups_df) else set()
    have_up_same = set(ups_df.loc[(ups_df["why"] == "") & ups_df["same_name"], "gauge"]) if len(ups_df) else set()
    opened = [v["opened"] for v in hy_cover.values() if v and v.get("opened")]
    good = ev_df[ev_df["why"] == ""] if len(ev_df) else ev_df
    lags = good["lag_h"] if len(good) else []
    speeds = (good["along_km"] * 1000 / (good["lag_h"] * 3600)).where(good["lag_h"] > 0) if len(good) else []
    per_pair = good.groupby("gauge")["lag_h"].median() if len(good) else []
    return {
        "river_spots": int(len(spots_df)),
        "why_counts": spots_df["why"].replace("", "usable").value_counts().to_dict(),
        "usable_spots": int(len(usable)), "usable_gauges": len(ug),
        "spots_with_upstream_gauge": int(usable["gauge"].isin(have_up).sum()),
        "spots_with_upstream_same_river": int(usable["gauge"].isin(have_up_same).sum()),
        "gauges_with_upstream": len(have_up & ug), "gauges_with_upstream_same_river": len(have_up_same & ug),
        "upstream_per_gauge": q(ups_df[ups_df["why"] == ""].groupby("gauge").size().reindex(sorted(ug), fill_value=0)) if len(ups_df) else {},
        "spot_gauges_in_hydrology_15min": sum(1 for v in hy_cover.values() if v),
        "spot_gauge_opened_quantiles_year": q([pd.Timestamp(o).year for o in opened]),
        "spot_gauge_opened_before_2015": sum(pd.Timestamp(o).year < 2015 for o in opened),
        "radar_spots_with_files": int((usable["radar_months"].fillna(0) > 0).sum()) if "radar_months" in usable else None,
        "pairs": int(len(pairs_df)), "pair_along_km": q(pairs_df["along_km"]) if len(pairs_df) else {},
        "coverage_share": q(cov_df["share"]) if len(cov_df) else {},
        "coverage_gaps_1h": q(cov_df["gaps_1h"]) if len(cov_df) else {},
        "coverage_longest_gap_h": q(cov_df["longest_gap_h"]) if len(cov_df) else {},
        "coverage_last": sorted(cov_df["last"].dropna())[:3] + ["..."] + sorted(cov_df["last"].dropna())[-3:] if len(cov_df) else [],
        "earliest_year": q([pd.Timestamp(e).year for e in cov_df["earliest"].dropna()]) if len(cov_df) else {},
        "events": int(len(ev_df)), "events_why": ev_df["why"].replace("", "lag measured").value_counts().to_dict() if len(ev_df) else {},
        "events_pairs_with_one": int(good["gauge"].nunique()) if len(good) else 0,
        "lag_h": q(lags), "lag_h_per_pair_median": q(per_pair), "lag_negative": int((pd.Series(lags) < 0).sum()) if len(good) else 0,
        "xcorr_lag_h": q(good["xcorr_lag_h"]) if len(good) else {},
        "onset_lead_h": q(good["onset_lead_h"]) if len(good) else {},
        "onset_lead_missing": int(good["onset_lead_h"].isna().sum()) if len(good) else 0,
        "implied_speed_ms": q(speeds),
        "latest_age_h_spot_gauges": q(ages_df.loc[ages_df["spot_gauge"], "age_h"]) if len(ages_df) else {},
        "latest_age_h_all": q(ages_df["age_h"]) if len(ages_df) else {},
        "latest_over_1h": int((ages_df["age_h"] > 1).sum()) if len(ages_df) else 0,
        "latest_over_6h": int((ages_df["age_h"] > 6).sum()) if len(ages_df) else 0,
        "latest_n": int(len(ages_df)),
        "range_ratio_p5p95_over_ea": q([r["p5_p95"] / r["ea_range"] for r in range_check if r["p5_p95"] and r["ea_range"]]),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=Path, required=True, help="answers are kept here (outside git)")
    ap.add_argument("--out", type=Path, required=True, help="tables and summary.json (outside git)")
    ap.add_argument("--network", type=Path, default=config.PROCESSED / "river_network.pkl")
    ap.add_argument("--radar", type=Path, default=config.RAW / "met_office_radar", help="saved radar months, read only")
    ap.add_argument("--fetch", action="store_true", help="ask the EA for what is not cached, within the caps")
    args = ap.parse_args(argv)
    if args.radar and not args.radar.exists():
        args.radar = None
    run(args)


if __name__ == "__main__":
    main()
