"""The radar shadow (docs/RADAR-SHADOW-2026-11.md, stated before any row was logged): for every overflow of the nine
English companies upstream of a listed spot, at lead 0, on every build, the chance #697's frozen candidate gives with
cell radar up to the build's listing time, beside its frozen reference on the build's forecast rain alone, logged in
its own table, `shadow_radar_v1`, in the state database.

  candidate  R0S@H (status known) or C (not known): the frame's seven short rain features rebuilt from the build's
             forecast rain with radar put in where the bucket had published it (radar_live, coverage >= 0.9)
  reference  PS@H (status known) or P (not known): production's own site-day frame, unchanged
  H          the issue hour nearest the build's hours since local midnight (0, 3, ..., 21)
  fallback   no usable radar this build: the candidate's chance is the reference's

Every rain input is one production has already read (its site-day frame and hourly rain), so the shadow costs no rain
request. Nothing here changes a forecast: it returns new arrays, never alters its inputs, and is called only inside
guards that log and carry on if it fails. No page, alert, level or published score reads the table. Off unless
DIPCAST_RADAR_SHADOW=1 (config.RADAR_SHADOW) and every frozen file is present at its stated hash.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config, radar_live
from dipcast.model import live_status
from dipcast.model.features import ALL_FEATURES, daily_rain_features

log = logging.getLogger(__name__)

RULE = "radar-v1"
TABLE = "shadow_radar_v1"
MODEL_DIR = config.PROCESSED / "radar_shadow"
HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
SHA256 = {
    "R0S_00": "74d47d0e8e5fb6975f5774848d488cec929892df590dfb076cbcb62065b5473a",
    "R0S_03": "3dd17a6999eb55f97d12e95e080b1dcfdd727a9e4da2db395b41e8b76f4dd5dc",
    "R0S_06": "5cb09f3f73b6aa0f517f1a493b6088524aeda8927b393752210b6a83cb23ab7e",
    "R0S_09": "152d835b3e66884bdc872eed869d0e26afe9e3d951a7ddbc0fb93014f3748789",
    "R0S_12": "df2f94d1220a903b2e8bb832992e4bedbe3934e247f46bc53f8b3de32d05c71a",
    "R0S_15": "c627bf428eb83edef8b283a7585f5f83be4890c76439bab2d3d0135d18409d9e",
    "R0S_18": "1156963e6d0d24cf0b48ef164a66219adbf6e9e84cd3a62dd911981e89f3ad5d",
    "R0S_21": "67e3018f4be081f11596c851c946a55b4516f7adf53d70eff729672f40adbbae",
    "PS_00": "dac992dd33db1c1248b18dee64dac660dcca8cd17cf3becf42034a6b91ac7bf3",
    "PS_03": "d866420024a4cec9f2932eb979a577c05de1593d41852eaaaf91c45941bd5abb",
    "PS_06": "c7bd7dfcaec090afc5a26e38fa552d1884172c76d85dea732f17fdbb498a1e85",
    "PS_09": "dd6dceef21d38ab34d62dbc13ab0e012e9fc556a44529115a42e0d8f4f08df49",
    "PS_12": "49a7dab9cb10333f10b5cb243937198e00bf8271dc9107b6fa719a1b83d2a8ca",
    "PS_15": "1220eb2b9ba46c385e3368d8be31c28bfafb732fa9693e83b0a751483210fb4d",
    "PS_18": "85814677c30888e20d36eb88922b6d54cb63c06a4a971f3c0777f86d26cd89e5",
    "PS_21": "befaf801c6758850cf1199268122d7f2f3437187577acbad5f927458ffecf512",
    "C": "d157a268220e28f4915a2ea39c4f2b89452ec708b16859aba84efb25ee598f8c",
    "P": "70b0898e3dd3c0b33bfac89100b6493863c381340b7655c584147e53998b093f",
}
# One stamp for the eighteen frozen files, on every row.
MODELS = hashlib.sha256("".join(SHA256[k] for k in sorted(SHA256)).encode()).hexdigest()[:16]
STATUS = live_status.STATUS
# #694's seven short-range features: the ones radar changes. The longer ones stay as the frame has them.
SHORT = ["rain_d", "max1h_d", "max3h_d", "max6h_d", "rain_d1", "rain_d2", "rain_3d"]
PARTIAL_GRACE = pd.Timedelta(minutes=15)   # an hour labelled this long before the listing should be published
NINE = live_status.ENGLISH_NINE
LAST_ISSUE_DAY = date(2027, 8, 31)          # the stop rule
COLUMNS = ("issued_at", "issue_day", "target_day", "build_at", "site_id", "company", "issue_hour", "p_candidate",
           "p_reference", "pair", "p_r0s", "p_ps", "p_c", "p_p", "radar_state", "radar_hours", "forecast_hours",
           "radar_newest_scan", "radar_newest_modified", "status_known", "spilling_at_issue", "spill_hours_24h",
           "spill_days_7d", "rain_issued_at", "p_raw", "p_cal", "p_shown", "rule", "models", "version")

# This build's radar (prefetch sets it once) and the overflows already logged in it.
_build: dict = {"radar": None, "logged": set(), "events": None}


# ------------------------------------------------------------------ the frozen files
def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def models() -> dict | None:
    """{"R0S": {H: model}, "PS": {H: model}, "C": model, "P": model}, or None (the shadow is off) when any file is
    missing or is not the frozen one."""
    from dipcast.model.spill_model import SpillModel
    out: dict = {"R0S": {}, "PS": {}}
    for name, want in SHA256.items():
        p = MODEL_DIR / f"{name}.pkl"
        if not p.exists():
            log.info("radar shadow off: %s missing", p.name)
            return None
        got = _sha(p)
        if got != want:
            log.warning("radar shadow off: %s is %s, not %s", p.name, got[:12], want[:12])
            return None
        m = SpillModel.load(p)
        status = name[:3] in ("R0S", "PS_")
        if list(m.features) != [*ALL_FEATURES, *(STATUS if status else [])]:
            log.warning("radar shadow off: %s has inputs %s", p.name, m.features)
            return None
        if "_" in name:
            arm, hh = name.split("_")
            out[arm][int(hh)] = m
        else:
            out[name] = m
    return out


def enabled() -> bool:
    return config.RADAR_SHADOW


def clear_cache() -> None:
    models.cache_clear()
    _build.update(radar=None, logged=set(), events=None)


# ------------------------------------------------------------------ once per build
def prefetch(cells: list[tuple[float, float]]) -> radar_live.RadarHours | None:
    """The build's radar step, run once after the rain prefetch. Sets this build's radar for every spot's forecast.
    None (nothing fetched, nothing logged) with the shadow off."""
    _build.update(radar=None, logged=set(), events=None)
    if not enabled() or models() is None:
        return None
    r = radar_live.update(cells)
    _build["radar"] = r
    log.info("radar shadow: %s; %d cells, %d listings, %d composites, %.1f MB, %.0f s%s", r.state,
             r.stats.get("cells", 0), r.stats.get("listings", 0), r.stats.get("files", 0),
             r.stats.get("bytes", 0) / 1e6, r.stats.get("seconds", 0.0), f" ({r.reason})" if r.reason else "")
    return r


def build_radar() -> radar_live.RadarHours | None:
    return _build["radar"]


# ------------------------------------------------------------------ the pieces
def issue_hour(now: pd.Timestamp, day_start: pd.Timestamp) -> int:
    """The issue hour nearest the hours since the target day's local midnight: 0, 3, ..., 21 (a half rounds up)."""
    h = (now - day_start).total_seconds() / 3600.0
    return int(min(21, max(0, 3 * np.floor(h / 3 + 0.5))))


def mixed_rain(rain: pd.DataFrame, radar: radar_live.RadarHours) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The build's hourly forecast rain (fetch_forecast's frame: cell_lat, cell_lon, time UTC, precip_mm) with radar
    put in for every hour from 00:00 local two days before to the listing time whose cell coverage is at least
    radar_live.MIN_COVERAGE. Returns the mixed rain and, per cell, the window's hours that took radar and that kept the
    forecast, and whether an hour old enough to be published kept the forecast (`partial`)."""
    r = rain.copy()
    r["time"] = pd.to_datetime(r["time"], utc=True)
    t_list = radar.listed_at
    first = radar_live.window_start(t_list)
    h = radar.hours.copy()
    h["time"] = pd.to_datetime(h["time"], utc=True)
    h = h[(h["time"] >= first) & (h["time"] <= t_list)]
    good = h[(h["coverage"] >= radar_live.MIN_COVERAGE) & h["radar_mm"].notna()]
    key = ["cell_lat", "cell_lon", "time"]
    for c in ("cell_lat", "cell_lon"):
        r[c] = r[c].astype(float).round(3)
        good = good.assign(**{c: good[c].astype(float).round(3)})
    r = r.merge(good[key + ["radar_mm"]], on=key, how="left")
    win = (r["time"] >= first) & (r["time"] <= t_list)
    took = win & r["radar_mm"].notna()
    r["precip_mm"] = np.where(took, r["radar_mm"], r["precip_mm"])
    old = r["time"] <= t_list - PARTIAL_GRACE
    counts = (r.assign(radar=took, forecast=win & ~took, late=win & ~took & old)
              .groupby(["cell_lat", "cell_lon"])[["radar", "forecast", "late"]].sum())
    return r.drop(columns="radar_mm"), counts


def short_features(rain: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """The seven short features of local `day`, per cell, from hourly rain, as spill_probabilities computes them
    (local-midnight days, features.daily_rain_features)."""
    r = rain.copy()
    r["time"] = pd.to_datetime(r["time"], utc=True).dt.tz_convert(live_status.LOCAL_TZ)
    # Only the days the seven read: today, the two before, and the one before them for the 3 and 6 hour maxima that
    # run over midnight. The same values as on the whole series, for a fraction of the work.
    r = r[(r["time"] >= day - pd.DateOffset(days=3)) & (r["time"] < day + pd.DateOffset(days=1))]
    d = daily_rain_features(r)
    d = d[d["day"] == day]
    d = d.assign(cell_lat=d["cell_lat"].astype(float).round(3), cell_lon=d["cell_lon"].astype(float).round(3))
    return d.set_index(["cell_lat", "cell_lon"])[SHORT]


def merged_poll_events() -> pd.DataFrame:
    """This build's poll intervals, merged (live_status.poll_events, _merge), read once per build."""
    if _build["events"] is None:
        hp = config.state_read("live_history.parquet")
        ev = live_status.poll_events(pd.read_parquet(hp)) if hp.exists() else pd.DataFrame(
            {"site_id": [], "start": [], "end": []})
        _build["events"] = live_status._merge(ev) if len(ev) else ev
    return _build["events"]


def hours_before(events: pd.DataFrame, now: pd.Timestamp) -> pd.Series:
    """Hours each overflow spilled in the 24 hours before `now`, from merged intervals; at most 24 (#697)."""
    if events is None or events.empty:
        return pd.Series(dtype=float)
    a = now.tz_convert("UTC") - pd.Timedelta(hours=24)
    b = now.tz_convert("UTC")
    s = pd.to_datetime(events["start"], utc=True)
    e = pd.to_datetime(events["end"], utc=True)
    lo, hi = s.where(s > a, a), e.where(e < b, b)
    hrs = ((hi - lo).dt.total_seconds() / 3600).clip(lower=0)
    return hrs.groupby(events["site_id"].astype(str).to_numpy()).sum().clip(upper=24.0)


def status_inputs(ov: pd.DataFrame, now: pd.Timestamp, table: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """The three inputs as at `now` and `status_known`, per row of ov: the live-status shadow's, with
    spill_hours_24h over the 24 hours before `now` (#697) in place of the local day before."""
    st = live_status.status_known(ov, now, table)
    h24 = hours_before(events, now).reindex(ov["site_id"].astype(str).to_numpy()).fillna(0.0).to_numpy()
    st["spill_hours_24h"] = np.where(st["status_known"].to_numpy(), h24, np.nan)
    return st


# ------------------------------------------------------------------ the shadow forecast
def shadow(sd: pd.DataFrame, ov: pd.DataFrame, days: pd.DatetimeIndex, today_idx: int, now: pd.Timestamp,
           rain: pd.DataFrame | None, radar: radar_live.RadarHours | None = None, frozen: dict | None = None,
           status_table: pd.DataFrame | None = None, events: pd.DataFrame | None = None) -> dict | None:
    """Lead 0's candidate and reference for each of ov's overflows, from production's site-day frame `sd` and the
    rain it was built from, or None with the shadow off or no build radar. Arrays are (n_overflows,):
      "candidate", "reference", "pair" ("status"/"no_status"), "r0s", "ps", "c", "p" (NaN where no rain)
      "state" (ok/partial/fallback/stopped), "radar_hours", "forecast_hours", "known", "inputs" (n, 3), "english",
      "issue_hour" (int)
    `radar`, `frozen`, `status_table` and `events` are for tests; a build uses prefetch's radar, the frozen files and
    the state folder's poll files."""
    frozen = frozen if frozen is not None else models()
    radar = radar if radar is not None else build_radar()
    if frozen is None or radar is None or sd is None or ov.empty or today_idx >= len(days):
        return None
    day = days[today_idx]
    H = issue_hour(now, day)
    n = len(ov)
    sid = ov["site_id"].astype(str).to_numpy()
    english = ov["company"].isin(NINE).to_numpy() if "company" in ov else np.zeros(n, bool)

    table = status_table if status_table is not None else live_status._status_for(now.tz_convert(live_status.LOCAL_TZ).date())
    ev = events if events is not None else merged_poll_events()
    st = status_inputs(ov, now, table, ev)
    known = st["status_known"].to_numpy(dtype=bool)

    f = sd[sd["day"] == day].drop_duplicates("site_id").set_index("site_id")
    f = f.reindex(pd.Index(sid, name="site_id"))
    ok = f["ok"].fillna(False).to_numpy(dtype=bool)
    ref = f.reset_index().fillna({c: 0.0 for c in ALL_FEATURES})
    ref[STATUS] = st[STATUS].to_numpy()

    radar_hours = np.zeros(n)
    forecast_hours = np.zeros(n)
    use_radar = radar.usable() and rain is not None and len(rain)
    state = np.full(n, radar.state if radar.state in ("fallback", "stopped") else "fallback", dtype=object)
    cand = ref.copy()
    if use_radar:
        mixed, counts = mixed_rain(rain, radar)
        sf = short_features(mixed, day)
        cl = ref["cell_lat"].astype(float).round(3).to_numpy()
        cn = ref["cell_lon"].astype(float).round(3).to_numpy()
        keys = pd.MultiIndex.from_arrays([cl, cn])
        new = sf.reindex(keys)
        have = new.notna().all(axis=1).to_numpy()
        for c in SHORT:
            cand[c] = np.where(have, new[c].to_numpy(dtype=float), cand[c].to_numpy(dtype=float))
        cc = counts.reindex(keys)
        radar_hours = cc["radar"].fillna(0).to_numpy(dtype=float)
        forecast_hours = cc["forecast"].fillna(0).to_numpy(dtype=float)
        state = np.where(cc["late"].fillna(0).to_numpy() > 0, "partial", "ok").astype(object)
        state[~have | (radar_hours == 0)] = "fallback"   # a cell with no radar hour at all takes the reference

    def pred(m, x):
        return np.where(ok, np.asarray(m.predict(x), dtype=float), np.nan)
    p_ps = pred(frozen["PS"][H], ref)
    p_p = pred(frozen["P"], ref)
    if use_radar:
        p_r0s = pred(frozen["R0S"][H], cand)
        p_c = pred(frozen["C"], cand)
        fb = state == "fallback"
        p_r0s = np.where(fb, p_ps, p_r0s)
        p_c = np.where(fb, p_p, p_c)
    else:
        p_r0s, p_c = p_ps.copy(), p_p.copy()
    candidate = np.where(known, p_r0s, p_c)
    reference = np.where(known, p_ps, p_p)
    return {"candidate": candidate, "reference": reference, "pair": np.where(known, "status", "no_status"),
            "r0s": p_r0s, "ps": p_ps, "c": p_c, "p": p_p, "state": state, "radar_hours": radar_hours,
            "forecast_hours": forecast_hours, "known": known, "inputs": st[STATUS].to_numpy(dtype=float),
            "english": english, "issue_hour": H, "radar": radar}


# ------------------------------------------------------------------ the log
def logs(issued_at: pd.Timestamp) -> bool:
    """Whether a forecast issued at `issued_at` is logged: inside the stop rule."""
    return issued_at.tz_convert(live_status.LOCAL_TZ).date() <= LAST_ISSUE_DAY


def log_shadow(issued_at: pd.Timestamp, ov: pd.DataFrame, target: pd.Timestamp, p_raw: np.ndarray,
               p_cal: np.ndarray, p_shown: np.ndarray, sh: dict, rain_at: np.ndarray, version: str | None,
               path=None) -> int:
    """Append one spot's lead-0 rows to TABLE: overflows of the nine, each once per build. `p_raw`, `p_cal` and
    `p_shown` are production's lead-0 column for ov. Returns the rows written."""
    from dipcast.forecast_log import _LOCK, _conn, append_rows
    if not logs(issued_at):
        return 0
    issue_day = issued_at.tz_convert(live_status.LOCAL_TZ).date()
    r = sh["radar"]

    def _f(x):
        return None if x is None or np.isnan(x) else float(x)

    def _t(x):
        return None if x is None or pd.isna(x) else pd.Timestamp(x)
    rows = []
    comps = ov["company"].to_numpy()
    for i, s in enumerate(ov["site_id"].astype(str).to_numpy()):
        if not sh["english"][i] or s in _build["logged"]:
            continue
        _build["logged"].add(s)
        rows.append((issued_at, issue_day, target.date(), _t(r.listed_at), s, str(comps[i]), int(sh["issue_hour"]),
                     _f(sh["candidate"][i]), _f(sh["reference"][i]), str(sh["pair"][i]), _f(sh["r0s"][i]),
                     _f(sh["ps"][i]), _f(sh["c"][i]), _f(sh["p"][i]), str(sh["state"][i]),
                     int(sh["radar_hours"][i]), int(sh["forecast_hours"][i]), _t(r.newest_scan),
                     _t(r.newest_modified), bool(sh["known"][i]), *(_f(v) for v in sh["inputs"][i]), _t(rain_at[i]),
                     _f(p_raw[i]), _f(p_cal[i]), _f(p_shown[i]), RULE, MODELS, version))
    if not rows:
        return 0
    with _LOCK:
        con = _conn(path)
        try:
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    issued_at TIMESTAMPTZ, issue_day DATE, target_day DATE, build_at TIMESTAMPTZ, site_id VARCHAR,
                    company VARCHAR, issue_hour INTEGER, p_candidate DOUBLE, p_reference DOUBLE, pair VARCHAR,
                    p_r0s DOUBLE, p_ps DOUBLE, p_c DOUBLE, p_p DOUBLE, radar_state VARCHAR, radar_hours INTEGER,
                    forecast_hours INTEGER, radar_newest_scan TIMESTAMPTZ, radar_newest_modified TIMESTAMPTZ,
                    status_known BOOLEAN, spilling_at_issue DOUBLE, spill_hours_24h DOUBLE, spill_days_7d DOUBLE,
                    rain_issued_at TIMESTAMPTZ, p_raw DOUBLE, p_cal DOUBLE, p_shown DOUBLE, rule VARCHAR,
                    models VARCHAR, version VARCHAR)""")
            append_rows(con, TABLE, COLUMNS, rows)
        finally:
            con.close()
    return len(rows)
