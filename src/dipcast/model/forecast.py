"""End-to-end: a point on the map -> risk now and for the coming days."""

from __future__ import annotations

import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config
from dipcast.ingest.flows import nearest_level_station, reading_fields
from dipcast.ingest.live import with_data_states
from dipcast.ingest import soil
from dipcast.ingest.rainfall import cells_for_sites, fetch_forecast, forecast_age
from dipcast.model import ecoli, live_status
from dipcast.model.features import (
    ALL_FEATURES,
    build_site_days,
    daily_rain_features,
    model_covariates,
)
from dipcast.model.spill_model import MODEL_PATH, SpillModel
from dipcast.model.transport import (
    ARRIVING_SAYS,
    COUNT_WEIGHT,
    clear_time,
    combine_daily,
    daily_effects,
    history_days,
    live_now_risk,
    locate_pin,
    missing_share,
    risk_label,
    risk_shares,
    river_velocity,
    running,
    spread_count,
    still_coming,
    upstream_overflows,
)
from dipcast.network.nations import traced_wales_share
from dipcast.network.rivers import RiverNetwork, bng_to_lonlat
from dipcast.overflow_names import water_name
from dipcast.overflows import load_overflows

log = logging.getLogger(__name__)

LOCAL_TZ = "Europe/London"   # swimmers think in local days, not UTC days
MAX_MISSING_SHARE = 0.1      # more transport weight than this from days without rain data: no figure
ECOLI_SEASON_MONTHS = range(5, 10)   # the EA samples the model was fitted on run May-September


_LOAD_LOCK = threading.RLock()  # one loader at a time: two concurrent unpickles of the
                                # 900 MB network would exceed a 2 GB machine


@lru_cache(maxsize=1)
def _net_uncached() -> RiverNetwork:
    return RiverNetwork.load()


def _net() -> RiverNetwork:
    with _LOAD_LOCK:
        return _net_uncached()


@lru_cache(maxsize=1)
def _overflows_uncached() -> pd.DataFrame:
    ov = load_overflows(_net())
    # For the page only: the model has used the names already (overflows.py, the position checks).
    ov["receiving_watercourse"] = ov["receiving_watercourse"].map(water_name)
    return ov


def _overflows() -> pd.DataFrame:
    with _LOAD_LOCK:
        return _overflows_uncached()


@lru_cache(maxsize=1)
def _lead_calibration() -> dict[int, dict]:
    """Per-lead calibration from scripts/verify_leads.py, if present: Platt (a, b) and,
    when fitted, an isotonic map as knots (iso_x -> iso_y). The isotonic map is used
    when present; it is the year-level correction for the top-end over-confidence."""
    import json
    p = config.PROCESSED / "lead_calibration.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text())
    return {int(k): v for k, v in d.get("leads", {}).items()}


def _apply(cal: dict, p: np.ndarray) -> np.ndarray:
    if "iso_x" in cal:
        return np.interp(p, np.asarray(cal["iso_x"], dtype=float), np.asarray(cal["iso_y"], dtype=float))
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return 1 / (1 + np.exp(-(cal["a"] + cal["b"] * np.log(q / (1 - q)))))


def calibrate_by_lead(p: np.ndarray, first_lead: int) -> np.ndarray:
    """p: (n_overflows, n_days); column j is lead first_lead + j. Leads beyond the
    fitted range use the last available parameters."""
    cal = _lead_calibration()
    if not cal or p.size == 0:
        return p
    out = p.copy()
    kmax = max(cal)
    for j in range(p.shape[1]):
        # Past days are analysis rain: the hindcast treats them as lead 0 (validate_ecoli.py).
        k = max(first_lead + j, 0)
        out[:, j] = _apply(cal[min(k, kmax)], out[:, j])
    return out


def calibrate_at_lead(p: np.ndarray, lead: int) -> np.ndarray:
    """Apply one lead's calibration to every column (hindcasts: every day is lead 0)."""
    cal = _lead_calibration()
    if not cal or p.size == 0:
        return p
    return _apply(cal[min(lead, max(cal))], p)


@lru_cache(maxsize=1)
def model_version() -> str:
    """Compact stamp of what produces a forecast: content hashes of the spill model,
    calibration map and E. coli model, the code version (git sha when available),
    and the weather source. Logged with every forecast so live scores can be split
    by version; a change to any of these starts a new row in the table."""
    import hashlib

    def h(p) -> str:
        return hashlib.md5(p.read_bytes()).hexdigest()[:8] if p.exists() else "none"

    def h_ecoli() -> str:
        """Today's E. coli model, and the river model with soil moisture when it exists: the MD5 of the two files'
        bytes one after the other (evaluate_2027.frozen_hashes computes the same), so either changing starts a
        new version. Without the river file, the MD5 of ecoli_model.json alone, as before."""
        if not ecoli.MODEL_PATH.exists():
            return "none"
        b = ecoli.MODEL_PATH.read_bytes() + (ecoli.SM_MODEL_PATH.read_bytes() if ecoli.SM_MODEL_PATH.exists() else b"")
        return hashlib.md5(b).hexdigest()[:8]

    from dipcast import __version__
    return (f"spill={h(MODEL_PATH)};cal={h(config.PROCESSED / 'lead_calibration.json')};"
            f"ecoli={h_ecoli()};code={__version__}+{code_commit()};rain=open-meteo-forecast")


@lru_cache(maxsize=1)
def code_commit() -> str:
    """The build's commit, seven characters: GitHub's GITHUB_SHA on a runner, else git, else "nogit".
    In model_version, so in every forecast logged, and in spots.json as `commit`, which the decision
    record and the sites view print in their issue id."""
    import os
    import subprocess

    sha = os.environ.get("GITHUB_SHA", "")[:7]
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True, check=False,
                                 cwd=config.ROOT, timeout=5).stdout.strip() or "nogit"
        except Exception:  # noqa: BLE001 - a missing git is not an error
            sha = "nogit"
    return sha


class MissingSpillModel(FileNotFoundError):
    """The trained spill model file is not there. Raised, never worked around: a forecast from
    climatology alone ignores the rain, and the page would show it as if it were the model's."""


@lru_cache(maxsize=1)
def _model() -> SpillModel:
    """The trained spill model. Code that means to forecast from climatology passes model=None to
    spill_probabilities itself; a missing file is an error, not a quiet switch to climatology."""
    if not MODEL_PATH.exists():
        raise MissingSpillModel(f"no trained spill model at {MODEL_PATH}")
    return SpillModel.load(MODEL_PATH)


def reload_caches() -> None:
    with _LOAD_LOCK:
        _overflows_uncached.cache_clear(); _model.cache_clear(); _lead_calibration.cache_clear(); ecoli.load.cache_clear()
        ecoli.load_sm.cache_clear()
        model_version.cache_clear(); code_commit.cache_clear(); live_status.clear_cache()
        # the network itself is immutable at runtime; keep it loaded


def _clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (np.floating, np.integer)):
        return _clean(v.item())
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if v is pd.NaT:
        return None
    return v


def to_minute(t: pd.Timestamp) -> str:
    """`t` to the nearest minute, as ISO text in its own zone. Rounded in UTC: pandas rounds the wall clock
    and will not guess at a clock change, so 01:25 on 25 Oct 2026 (an hour that happens twice) raised and
    failed Warleigh Weir's forecast on 21 Oct and Tellisford's on 22 Oct, and 00:59:40 GMT on 28 Mar 2027
    would round to 01:00, a time that never happens."""
    return t.tz_convert("UTC").round("min").tz_convert(t.tz).isoformat()


def spill_probabilities(ov: pd.DataFrame, days: pd.DatetimeIndex,
                        model: SpillModel | None, return_rain: bool = False,
                        rain: pd.DataFrame | None = None, return_frame: bool = False) -> tuple:
    """(n_overflows, n_days) probability each overflow spills on each day, and a
    bool mask of the same shape: True where that overflow's cell has rainfall data
    for the day. Where it has none the probability is NaN, never 0. With
    `return_rain`, also the day's rainfall (mm) at each overflow's cell that the
    probability was computed from, NaN where missing. `rain`, hourly rain as
    fetch_forecast returns it, is used instead of fetching (the click-anywhere data,
    scripts/build_any_point.py, rations its fetches); a cell missing from it has no data. With
    `return_frame`, also the site-day frame the model read (None where there was none), so the
    live-status shadow (live_status.shadow_forecast) runs on the same rain without fetching it again."""
    tail = (None,) if return_frame else ()
    if ov.empty:
        empty = (np.zeros((0, len(days))), np.zeros((0, len(days)), dtype=bool))
        return (*empty, np.zeros((0, len(days))), *tail) if return_rain else (*empty, *tail)
    cells = cells_for_sites(ov["lat"], ov["lon"])
    rain = fetch_forecast(cells) if rain is None else rain.copy()
    if rain.empty:   # Open-Meteo sent nothing and nothing cached is under a day old: every day unknown
        shape = (len(ov), len(days))
        none = (np.full(shape, np.nan), np.zeros(shape, dtype=bool))
        return (*none, np.full(shape, np.nan), *tail) if return_rain else (*none, *tail)
    rain["time"] = rain["time"].dt.tz_convert(LOCAL_TZ)   # local-midnight day boundaries
    daily = daily_rain_features(rain)
    # The covariates as filled once over the whole overflow table (features.fill_covariates), not
    # over this spot's upstream overflows alone.
    sites = pd.concat([ov[["site_id", "lat", "lon", "company"]], model_covariates(ov)], axis=1)
    # The pivots below need one row per site_id ("Index contains duplicate entries, cannot reshape"
    # failed four spots on 3 Oct 2026). A repeated id is computed once, from its first row; the
    # reindex on ov["site_id"] still gives each of ov's rows its own row of the result.
    repeated = sites["site_id"].duplicated()
    if repeated.any():
        log.warning("spill_probabilities: overflow id listed more than once, computed once: %s",
                    ", ".join(map(str, sites.loc[repeated, "site_id"].unique())))
        sites = sites[~repeated]
    sd = build_site_days(sites, daily, days)
    for f in ALL_FEATURES:
        sd[f] = sd[f].astype(np.float32)
    sd["ok"] = sd["rain_d"].notna()
    if model is None:
        # Climatology from the annual returns: spill-days per year.
        p = (sd["lta_spills"].to_numpy() if "lta_spills" in sd else np.full(len(sd), 20.0)) / 365.0
        sd["p"] = np.clip(np.nan_to_num(p, nan=0.05), 0.001, 0.95)
    else:
        sd["p"] = model.predict(sd.fillna({f: 0.0 for f in ALL_FEATURES}))
    sd.loc[~sd["ok"], "p"] = np.nan
    mat = sd.pivot(index="site_id", columns="day", values="p").reindex(index=ov["site_id"], columns=days)
    okm = sd.pivot(index="site_id", columns="day", values="ok").reindex(index=ov["site_id"], columns=days)
    out = (mat.to_numpy(dtype=float), okm.fillna(False).to_numpy(dtype=bool))
    if return_rain:
        rain_mm = sd.pivot(index="site_id", columns="day", values="rain_d").reindex(index=ov["site_id"], columns=days)
        out = (*out, rain_mm.to_numpy(dtype=float))
    return (*out, sd) if return_frame else out


def member_rain(rain: pd.DataFrame, ens: pd.DataFrame) -> list[pd.DataFrame]:
    """Each ensemble member's hourly rain per cell, in fetch_forecast's shape: the single forecast's rain
    before the hour that forecast was issued, and the member's from that hour on, so every member shares
    the 31 days of past rain. An hour the member does not reach (past its run, or a cell with no members)
    is NaN, and a day short of hours has no rain (features.daily_rain_features), never a dry one."""
    if rain.empty or ens.empty:
        return []
    utc = lambda s: pd.to_datetime(s, utc=True).astype("datetime64[ns, UTC]")
    base = rain[["cell_lat", "cell_lon", "time", "precip_mm"]].assign(time=lambda d: utc(d["time"]))
    issued = utc(rain["issued_at"]) if "issued_at" in rain else pd.Series(pd.NaT, index=rain.index, dtype="datetime64[ns, UTC]")
    issued = issued.fillna(pd.Timestamp.now(tz="UTC"))
    base["cut"] = issued.groupby([rain["cell_lat"], rain["cell_lon"]]).transform("max").dt.floor("h").to_numpy()
    ens = ens.assign(time=utc(ens["time"])).drop_duplicates(["cell_lat", "cell_lon", "time", "member"], keep="last")
    out = []
    for m in sorted(ens["member"].unique()):
        em = ens.loc[ens["member"] == m, ["cell_lat", "cell_lon", "time", "precip_mm"]].rename(columns={"precip_mm": "pm"})
        x = base.merge(em, on=["cell_lat", "cell_lon", "time"], how="left")
        x["precip_mm"] = np.where(x["time"] >= x["cut"], x["pm"], x["precip_mm"])
        out.append(x[["cell_lat", "cell_lon", "time", "precip_mm"]])
    return out


def ensemble_members(ov: pd.DataFrame, days: pd.DatetimeIndex, model: SpillModel | None, rain: pd.DataFrame,
                     hist: int, weights: np.ndarray, travel: np.ndarray) -> dict | None:
    """The ensemble members (docs/ENSEMBLE-RAIN-TEST-2026-11.md): the spill model and the lead calibration run
    once per member of the ensemble rain, exactly as for the single forecast. `p` and `rain` are
    (members, overflows, days): each overflow's calibrated chance and the day's rain at its cell, NaN where
    that member has no rain; `risk` is (members, days), the spot's risk per member, NaN where more than
    MAX_MISSING_SHARE of the weight has no rain, as for the headline. None without members. Display and
    the log only: the headline stays on the single forecast until the test says otherwise."""
    if ov.empty or rain is None or rain.empty:
        return None
    ens = fetch_forecast(cells_for_sites(ov["lat"], ov["lon"]), ensemble=True)
    members = member_rain(rain, ens)
    if not members:
        return None
    ps, rains, risks = [], [], []
    for mr in members:
        p_raw, avail, mm = spill_probabilities(ov, days, model, return_rain=True, rain=mr)
        p = calibrate_by_lead(p_raw, first_lead=-hist)
        r = combine_daily(p, weights, travel)
        risks.append(np.where(missing_share(avail, weights, travel) > MAX_MISSING_SHARE, np.nan, r))
        ps.append(np.where(avail, p, np.nan))
        rains.append(mm)
    return {"p": np.stack(ps), "rain": np.stack(rains), "risk": np.stack(risks), "members": len(members),
            "issued_at": pd.to_datetime(ens["issued_at"], utc=True).min()}


def _in_wales(net: RiverNetwork, pin, max_km: float) -> dict:
    """upstream_summary's `wales_share`, where the river the trace walks above the spot runs partly
    through Wales, whose overflows are not in the data (network/nations.py): the page says they are not
    counted, and how much of that river is in Wales. Nothing where none of it is."""
    try:
        share = traced_wales_share(net, pin.trace_node, max_km)
    except Exception as e:  # noqa: BLE001 - a label beside the forecast must never fail it
        log.warning("share of the river in Wales not worked out: %s", e)
        return {}
    return {"wales_share": share} if share else {}


def river_ecoli(mode: str, lat: float, lon: float, X: pd.DataFrame, p_today: np.ndarray,
                now: pd.Timestamp) -> tuple[np.ndarray, dict]:
    """The E. coli figures a spot shows, and which model gave them. A river spot uses the soil-moisture model
    (ecoli.load_sm) with its cell's value at 00:00 UTC of the issue day, held for every day shown. A lake, or a river
    spot with no model file or no usable soil moisture (soil.value), keeps `p_today`, today's model: never a guessed
    wetness. It reads the cache only: the build's prefetch is the one place soil moisture is fetched (soil.fetch), so
    a cell that failed there is not asked for again by each spot. `reason` says why, and build_health counts the river
    spots that fell back."""
    if mode != "river":
        return p_today, {"used": False, "reason": "lake: today's model"}
    em_sm = ecoli.load_sm()
    if em_sm is None:
        return p_today, {"used": False, "reason": "no river model file"}
    v, info = soil.value(soil.cell_of(lat, lon), now)
    if v is None:
        return p_today, {"used": False, **info}
    lo, hi = em_sm.meta["sm_range"]
    return em_sm.predict(ecoli.with_sm(X, v, em_sm)), {"used": True, "sm": round(v, 3), "held": not lo <= v <= hi, **info}


def ecoli_provenance(em: ecoli.EcoliModel, soil_state: dict) -> dict:
    """What a spot publishes about the E. coli model that gave its figures (assumptions.ecoli_model): the soil-moisture
    model's file, size, score, test and soil source when soil_state says it was used, with today's model under
    `baseline`; otherwise today's model, as before, and why soil moisture was not used."""
    today = {"file": ecoli.MODEL_PATH.name, "target": em.meta.get("target"), "fitted_on": em.meta.get("sites"),
             "n_samples": em.meta.get("n_samples"),
             "loyo_brier": em.meta.get("loyo", {}).get("rain + spill exposure + season (dipcast)", {}).get("brier")}
    if not soil_state.get("used"):
        return {**today, "soil": soil_state}
    sm = ecoli.load_sm()
    return {"file": ecoli.SM_MODEL_PATH.name, "target": sm.meta.get("target"), "fitted_on": sm.meta.get("fitted_on"),
            "n_samples": sm.meta.get("n_samples"), "loyo_brier": ecoli.SM_MODEL_LOYO_BRIER, "test": ecoli.SM_MODEL_TEST,
            "soil_source": sm.meta.get("sm_source"), "soil": soil_state, "baseline": today}


def forecast_point(lat: float, lon: float, days_ahead: int = 4, max_km: float = config.MAX_UPSTREAM_KM,
                   include_contributors: int = 25, log_to_store: bool = True, gauge: bool = True,
                   kind_hint: str | None = None, river_hint: str | None = None, name: str | None = None,
                   ensemble: bool = False) -> dict:
    """`ensemble`: also run the spill model on each member of the ensemble rain (ensemble_members) and give
    each day a `band`, the lowest and highest member's risk. The listed spots only (the build); the headline
    does not change."""
    net, ov_all, model = _net(), _overflows(), _model()
    now = pd.Timestamp.now(tz=LOCAL_TZ)
    # The EA gauge lookup is slow and optional: run it alongside everything else.
    pool = ThreadPoolExecutor(max_workers=1)
    state_future = pool.submit(nearest_level_station, lat, lon, 15, river_hint) if gauge else None
    pin = locate_pin(net, lon, lat, kind_hint=kind_hint, river_hint=river_hint, name=name)

    out: dict = {
        "query": {"lat": lat, "lon": lon, "issued_at": now.isoformat()},
        "location": {
            "mode": pin.mode, "watercourse": pin.watercourse,
            "snap_distance_m": None if pin.snap is None else round(pin.snap.dist_m),
            "form": None if pin.snap is None else pin.snap.form,
            "lake_area_km2": None if pin.lake_area_km2 is None else round(pin.lake_area_km2, 1),
            "lake_source": pin.lake_source,
            "adopted_main_channel": pin.adopted_main_channel,
            "placement": pin.placement,
        },
        "river_state": None,
        "assumptions": {
            "river_velocity_ms": config.RIVER_VELOCITY_MS, "lake_velocity_ms": config.LAKE_VELOCITY_MS,
            "t90_hours": config.T90_HOURS, "max_upstream_km": max_km,
            "recent_spill_hours": config.RECENT_SPILL_HOURS,
            "model": None if model is None else model.trained_on,
            "lead_calibration": bool(_lead_calibration()),
            "version": model_version(),
        },
    }
    if pin.mode in ("none", "isolated"):
        pool.shutdown(wait=False)
        out["error"] = ("No river or lake within 1.5 km of this point." if pin.mode == "none" else
                        "An isolated lake: the river network links no monitored storm overflow to it, so the forecast "
                        "has nothing to say about it. Risk from wildlife, runoff and bathers is not modelled.")
        out["now"] = {"risk": 0.0, "label": "unknown"}
        out["days"] = []
        out["contributors"] = []
        return out

    state = None
    if state_future is not None:
        try:
            state = state_future.result(timeout=12)
        except Exception as e:  # noqa: BLE001
            log.warning("river state unavailable: %s", e)
    pool.shutdown(wait=False)
    old_reading = state is not None and state.is_stale()
    # A days-old level says nothing about today's speed: the default velocity instead.
    v = river_velocity(state.index if state is not None and not old_reading else None)
    out["river_state"] = None if state is None else reading_fields(state)   # a stale one has no level_m
    out["assumptions"]["river_velocity_ms"] = round(v, 2)
    ov = with_data_states(upstream_overflows(net, pin, ov_all, velocity_ms=v, max_km=max_km))
    now_risk, now_contrib = live_now_risk(ov, now)
    here = weighted_here(ov)
    counts = live_counts(ov[here], now_contrib[here])
    on_change = feeds_on_change(ov)
    if on_change:
        counts["feeds_on_change"] = on_change   # for the page's own ageing of quiet readings (index.html, ageReadings)

    weights = ov["weight"].to_numpy(dtype=float) if not ov.empty else np.zeros(0)
    travel = ov["travel_h"].to_numpy(dtype=float) if not ov.empty else np.zeros(0)
    # The grid starts far enough back for the longest travel time (same rule as the
    # hindcast), so today's risk includes spills that left distant overflows days ago.
    hist = history_days(travel)
    days = pd.date_range(now.floor("D") - pd.Timedelta(days=hist), periods=hist + days_ahead + 1, freq="D")
    today_idx = hist
    # The rain is fetched here (from the cache the build's prefetch filled), not in spill_probabilities, so
    # the ensemble's members can share its past and the spot can say how old it is (forecast_age).
    rain = fetch_forecast(cells_for_sites(ov["lat"], ov["lon"])) if not ov.empty else None
    p_raw, avail, rain_mm, frame = spill_probabilities(ov, days, model, return_rain=True, rain=rain, return_frame=True)
    p = calibrate_by_lead(p_raw, first_lead=-hist)   # column `hist` is today (lead 0)
    # The live-status shadow (docs/LIVE-STATUS-SHADOW-TEST-2026-10.md): for the forecast log only, from the
    # same site-day frame, so it costs no rain request. Nothing below reads it but log_forecast.
    shadow = None
    if log_to_store and frame is not None:
        try:
            shadow = live_status.shadow_forecast(frame, ov, days, today_idx, now, p)
        except Exception as e:  # noqa: BLE001 - a shadow must never fail the forecast
            log.warning("live-status shadow skipped: %s", e)
    risk = combine_daily(p, weights, travel)
    # Which overflows each day's risk comes from (the page's "where the risk comes from"), and the
    # part of it from spills on the days after today alone: new spills, not ones under way or over,
    # which the live status already counts. Computed here because both need every upstream overflow
    # and the days before today; the page gets only the KEEP_CONTRIBUTORS with the most reach.
    shares = risk_shares(daily_effects(p, weights, travel)) if len(weights) else np.zeros((0, len(days)))
    later = np.where(np.arange(len(days)) > today_idx, p, 0.0) if len(weights) else p
    risk_later = combine_daily(later, weights, travel)
    # Share of today's transport weight that comes from days with no rainfall data.
    missing = missing_share(avail, weights, travel)
    risk = np.where(missing > MAX_MISSING_SHARE, np.nan, risk)
    # Expected number of spilling upstream overflows per day (unweighted), for context: of those that
    # carry weight here (weighted_here), as the counts are.
    exp_spills = np.nansum(p[here], axis=0) if len(p) else np.zeros(len(days))
    members = None
    if ensemble:
        try:
            members = ensemble_members(ov, days, model, rain, hist, weights, travel)
        except Exception as e:  # noqa: BLE001 - a band beside the forecast must never fail it
            log.warning("ensemble rain skipped: %s", e)
        if members is not None:
            out["assumptions"]["rain_ensemble"] = {"model": config.ENSEMBLE_MODEL, "members": members["members"],
                                                   "issued_at": _clean(members["issued_at"].round("min"))}

    def _band(j: int) -> dict:
        """The lowest and highest member's risk for day j, where every member has one."""
        if members is None or not np.isfinite(members["risk"][:, j]).all():
            return {}
        r = members["risk"][:, j]
        return {"band": {"low": round(float(r.min()), 3), "high": round(float(r.max()), 3)}}

    def _status(j: int) -> str:
        if missing[j] > MAX_MISSING_SHARE:
            return "rain unavailable"
        return "partial" if missing[j] > 0 else "ok"

    day_rows = []
    for j, d in enumerate(days):
        if d < now.floor("D"):
            continue  # earlier days are only there to absorb travel-time shifts
        known = not np.isnan(risk[j])
        day_rows.append({
            "date": d.date().isoformat(), "risk": round(float(risk[j]), 3) if known else None,
            "label": risk_label(float(risk[j])) if known else "unknown",
            "expected_spilling_overflows": round(float(exp_spills[j]), 1) if known else None,
            "data_status": _status(j), "rain_missing_share": round(float(missing[j]), 3),
            "in_validated_season": d.month in ECOLI_SEASON_MONTHS,
            **({"risk_from_later_spills": round(float(risk_later[j]), 3)} if known else {}),
            **(_band(j) if known else {}),
            # Only where the page says it, moderate or worse, to keep spots.json small.
            **({"source": source_of(ov, shares[:, j])} if known and risk_label(float(risk[j])) != "low" else {}),
        })

    # E. coli exceedance: rain at the spot itself (not at the overflows) plus the day's exposure.
    em = ecoli.load()
    p_ec = r48 = spot_rain = None
    if em is not None:
        try:
            spot_rain = fetch_forecast(cells_for_sites(pd.Series([lat]), pd.Series([lon])))
            hourly = spot_rain.assign(time=spot_rain["time"].dt.tz_convert(LOCAL_TZ)).set_index("time")["precip_mm"].sort_index()
            ends = pd.DatetimeIndex([d + pd.Timedelta(hours=ecoli.SAMPLE_HOUR) for d in days])
            r48, r24, cov48, _ = ecoli.rain_windows(hourly, ends, return_coverage=True)
            X = ecoli.features(r48, r24, risk, np.full(len(days), 1.0 if pin.mode == "lake" else 0.0), days)
            p_ec = em.predict(X)
            p_ec, soil_state = river_ecoli(pin.mode, lat, lon, X, p_ec, now)
            for row in day_rows:
                j = days.get_loc(pd.Timestamp(row["date"], tz=LOCAL_TZ))
                ok = not (np.isnan(r48[j]) or np.isnan(p_ec[j]))
                row["rain_48h_mm"] = None if np.isnan(r48[j]) else round(float(r48[j]), 1)
                row["rain_48h_coverage"] = round(float(cov48[j]), 3)   # finite share of the window's 48 hours
                row["p_ecoli_gt900"] = round(float(p_ec[j]), 3) if ok else None
                if not ok and row["data_status"] == "ok":
                    row["data_status"] = "rain unavailable"
            out["assumptions"]["ecoli_model"] = ecoli_provenance(em, soil_state)
            # Where the E. coli figure has been checked: rivers, in the May-September sampling
            # season, at designated bathing waters. Lakes showed no ranking skill.
            out["ecoli_scope"] = {
                "water_body_validated": pin.mode == "river",
                "season_validated_months": [int(m) for m in ECOLI_SEASON_MONTHS],
                # 641 lake samples in the fitting data, 2024-26 (ecoli_model.json: 1,548 x the lake share 0.414),
                # 16 of them over 900.
                "note": ("Not validated on lakes: no ranking skill in the fitting data (16 exceedances in 641 lake samples, 2024 to 2026)."
                         if pin.mode == "lake" else
                         "Validated on Environment Agency river bathing waters, May-September; other sites and months are extrapolation."),
            }
        except Exception as e:  # noqa: BLE001 - an optional layer must not fail the forecast
            log.warning("E. coli model skipped: %s", e)
    # How old the rain behind this spot is, from its oldest cell: a cell not fetched afresh (Open-Meteo did
    # not answer, or the day's limit held the request back) is served from the cache up to a day old, and
    # only the build's warnings said so.
    age = forecast_age([rain, spot_rain], now)
    if age:
        out["assumptions"].update(age, rain_issued_at=to_minute(age["rain_issued_at"].tz_convert(LOCAL_TZ)))

    # When right now's risk should be back to low if the spills stop now, allowing for the water still
    # on its way (transport.clear_time), and which overflows it comes from: written where the page says
    # them, moderate or worse, or while an overflow upstream is discharging.
    clears_at, clears_by, last_water = clear_time(ov, now)
    spilling = bool(len(ov)) and bool(running(ov).any())
    said = risk_label(now_risk) != "low" or (spilling and now_risk > 0)
    arriving = arriving_of(ov, now, now_contrib) if said else None
    clearing = {"clears_at": None if clears_at is None else to_minute(clears_at), "clears_by": clears_by,
                # The overflow whose travel time holds the risk up most as it clears, when travel does ('travel').
                **({"clears_after": {k: _clean(ov.loc[last_water].get(k)) for k in ("site_id", "site_name")}
                    | {"travel_h": round(float(ov.loc[last_water, "travel_h"]), 1)}} if clears_by == "travel" else {}),
                **({"source": source_of(ov, risk_shares(now_contrib.to_numpy(dtype=float)))} if said else {}),
                # The spill whose water is still on its way, when such spills hold at least half the risk.
                **({"arriving": arriving} if arriving else {})}
    out["now"] = {"risk": round(now_risk, 3), "label": risk_label(now_risk), **clearing,
                  **{k: counts[k] for k in NOW_KEYS if k in counts}}
    out["days"] = day_rows
    out["upstream_summary"] = {
        "overflows": int(here.sum()), "with_live_feed": counts["monitored_upstream"],
        "without_live_feed": int(here.sum() - counts["monitored_upstream"]),
        **too_far(ov, here),
        "sum_weight": round(float(weights.sum()), 3),
        "history_days": int(hist), "max_travel_h": round(float(travel.max()), 1) if len(travel) else 0.0,
        **_in_wales(net, pin, max_km),
    }
    contrib = []
    if not ov.empty:
        ov = ov.copy()
        p0 = np.nan_to_num(p, nan=0.0)
        ov["p_today"] = p0[:, today_idx] if p0.shape[1] > today_idx else 0.0
        ov["p_tomorrow"] = p0[:, today_idx + 1] if p0.shape[1] > today_idx + 1 else 0.0
        # Every day shown, so a spot's page can say which overflows drive a day three days out, and
        # rank them over all of those days. NaN (no rain data at the overflow's cell) goes out as
        # None: 0 would read as "will not spill".
        p_ahead = p[:, today_idx:today_idx + len(day_rows)]
        ov["now_contribution"] = now_contrib
        ov["impact_today"] = ov["weight"] * ov["p_today"]
        ov["relevance"] = np.maximum.reduce([
            ov["now_contribution"].to_numpy(dtype=float),
            ov["weight"].to_numpy(dtype=float) * np.nan_to_num(p_ahead, nan=0.0).max(axis=1, initial=0.0),
            0.1 * ov["weight"].to_numpy(dtype=float),   # keep close, quiet overflows visible
        ])
        ov["p_days"] = [[None if np.isnan(v) else round(float(v), 3) for v in row] for row in p_ahead]
        top = ov.sort_values("relevance", ascending=False).head(include_contributors)
        for _, r in top.iterrows():
            contrib.append({k: _clean(r.get(k)) for k in [
                "site_id", "company", "site_name", "receiving_watercourse", "lat", "lon", "status",
                "has_live", "data_state", "feed_updated_at", "latest_event_start", "latest_event_end", "lta_spills",
                "spill_hours", "snap_confidence", "position_source", "on_named",
            ]} | {
                "snap_m": None if pd.isna(r.get("snap_dist_m")) else round(float(r["snap_dist_m"])),
                "distance_km": round(float(r["distance_m"]) / 1000, 1),
                "lake_distance_km": round(float(r["lake_distance_m"]) / 1000, 1),
                "travel_h": round(float(r["travel_h"]), 1),
                "weight": round(float(r["weight"]), 3),
                "p_spill_today": round(float(r["p_today"]), 3),
                "p_spill_tomorrow": round(float(r["p_tomorrow"]), 3),
                "p_spill_days": r["p_days"],   # one per entry in "days", None where unknown
                "now_contribution": round(float(r["now_contribution"]), 3),
            } | carried_fields(r))
    out["contributors"] = contrib
    if pin.snap is not None:
        slon, slat = bng_to_lonlat(pin.snap.x, pin.snap.y)
        out["location"]["snapped"] = {"lat": round(slat, 5), "lon": round(slon, 5)}
    if log_to_store:
        try:
            from dipcast.forecast_log import log_forecast
            log_forecast(now, lat, lon, pin.mode, pin.watercourse, now_risk, days, risk, ov,
                         np.nan_to_num(p_raw, nan=0.0), np.nan_to_num(p, nan=0.0), p_ecoli=p_ec, rain_48h=r48,
                         available=avail, rain_mm=rain_mm, version=model_version(), members=members, shadow=shadow)
        except Exception as e:  # noqa: BLE001 - logging must never fail a forecast
            log.warning("forecast log failed: %s", e)
    return out


def source_of(ov: pd.DataFrame, share: np.ndarray) -> dict | None:
    """The overflow with the largest share of a risk (transport.risk_shares, one per row of `ov`):
    which it is, where, its share, and how many overflows make up nine tenths of the risk
    (spread_count). The page names it alone when its share is at least half, and otherwise says the
    risk is spread over that many. None when the risk is 0."""
    share = np.asarray(share, dtype=float)
    if not len(share) or share.max() <= 0:
        return None
    r = ov.iloc[int(np.argmax(share))]
    return {k: _clean(r.get(k)) for k in ["site_id", "site_name", "receiving_watercourse", "status"]} | {
        "distance_km": round(float(r["distance_m"]) / 1000, 1),
        "lake_distance_km": round(float(r["lake_distance_m"]) / 1000, 1),
        "travel_h": round(float(r["travel_h"]), 1),
        "share": round(float(share.max()), 3), "spread_over": spread_count(share),
    } | carried_fields(r)


def weighted_here(ov: pd.DataFrame) -> np.ndarray:
    """Which upstream overflows the counts count: those whose weight here, rounded to the 3 dp spots.json
    gives, is transport.COUNT_WEIGHT or more. Under it the page shows "0% reach", so counting one would
    contradict the page. At Windermere, Waterhead, Grasmere WwTW's weight is 0.00045 (its water crosses two
    lakes); counted, its spill chance made the page say "About 2 of the 4 overflows upstream are expected to
    spill today". Where none carries that much, all count: what to say there is not settled."""
    if ov.empty or "weight" not in ov:
        return np.ones(len(ov), dtype=bool)
    w = pd.to_numeric(ov["weight"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    here = np.round(w, 3) >= COUNT_WEIGHT
    return here if here.any() else np.ones(len(ov), dtype=bool)


def too_far(ov: pd.DataFrame, here: np.ndarray) -> dict:
    """upstream_summary's `too_far`, how many overflows upstream weighted_here leaves out, and with one,
    `too_far_overflow`, which, so the page can name it."""
    n = int((~here).sum())
    if not n:
        return {}
    one = ov[~here].iloc[0]
    return {"too_far": n, **({"too_far_overflow": {k: _clean(one.get(k)) for k in ("site_id", "site_name", "company")}} if n == 1 else {})}


def carried_fields(r: pd.Series) -> dict:
    """For an overflow carried through its company's feed outage (status FEED_DOWN): the status the
    last poll that read it saw (`last_status`, 1 for a spill running then) and when that poll was
    (`feed_down_since`), so the page can say "discharging when the feed last answered". Nothing for
    any other overflow, to keep spots.json small."""
    from dipcast.ingest.live import FEED_DOWN
    if r.get("status") != FEED_DOWN:
        return {}
    last = pd.to_numeric(r.get("last_status"), errors="coerce")
    return {"last_status": None if pd.isna(last) else int(last), "feed_down_since": _clean(r.get("feed_down_since"))}


def arriving_of(ov: pd.DataFrame, now: pd.Timestamp, now_contrib: pd.Series) -> dict | None:
    """The spill right now's risk counts whose water has not reached the spot yet (transport.still_coming),
    when such spills hold at least ARRIVING_SAYS of the risk: the one with the largest share, where it
    is, and when its water arrives. The level already counts it (live_now_risk); the page says when it
    gets here. None otherwise."""
    contrib = now_contrib.to_numpy(dtype=float)
    left = still_coming(ov, now, contrib)
    coming = ~np.isnan(left)
    share = risk_shares(contrib)
    if not coming.any() or share[coming].sum() < ARRIVING_SAYS:
        return None
    k = int(np.argmax(np.where(coming, share, -1.0)))
    r = ov.iloc[k]
    return {key: _clean(r.get(key)) for key in ["site_id", "site_name", "receiving_watercourse", "status"]} | {
        "distance_km": round(float(r["distance_m"]) / 1000, 1),
        "lake_distance_km": round(float(r["lake_distance_m"]) / 1000, 1),
        "travel_h": round(float(r["travel_h"]), 1),
        "arrives_at": to_minute(now + pd.Timedelta(hours=float(left[k]))),
        "share": round(float(share[coming].sum()), 3),
    } | carried_fields(r)


# What forecast_point copies from live_counts (and feeds_on_change) into a spot's `now`. One list, so a key
# the pages read cannot be left out where it is copied: monitored_weight and upstream_weight (levels.js,
# nowWatched), feeds_on_change (index.html, ageReadings). tests/test_feed_freshness.py checks that every key
# live_counts gives is here.
NOW_KEYS = ("discharging_upstream", "recent_upstream", "monitored_upstream", "feed_down_upstream", "feed_down",
            "stale_upstream", "feed_stale", "no_feed_upstream", "quiet_by_feed", "monitored_weight", "upstream_weight",
            "feeds_on_change")


def live_counts(ov: pd.DataFrame, now_contrib: pd.Series) -> dict:
    """The "Right now" counts for the upstream overflows. An overflow whose company feed
    failed is carried with its last snapshot (ingest.live.carry_forward): it has a feed but
    no status in this update, so it is neither discharging, recently finished nor reporting;
    the page shows it as not reporting and names the feed. Its last-known finished event
    still counts in the risk itself (live_now_risk): that event happened.

    `monitored_upstream`, those that report live, is the discharging, the recently finished
    and the quiet: a "not discharging" from a current feed (data_state live). A "not
    discharging" that is not current is unknown, not quiet: the monitor is offline (-1), or the
    company's feed has not updated within ingest.live.FEED_CURRENT_H (stale). The stale ones
    are counted in `stale_upstream` and named by company in `feed_stale`, as a feed that is
    down is. A discharge counts whatever the state: it was the feed's last word. In
    live_now_risk an overflow it cannot see adds nothing.

    `no_feed_upstream` counts those not reporting because their company has no live feed SwimSignal reads
    (data_state no_feed), so the page can tell them from monitors that are offline: what is not
    reporting is then stale_upstream + no_feed_upstream + the rest, which are offline (feed_down_upstream
    among them).

    A spill running at the last poll before its company's feed failed (transport.running)
    counts as discharging, as a stale feed's discharge does, and not as feed down. A record that has
    stopped updating in a feed that has not (data_states' `record_stale`) is stale like a stale
    feed's, and named in `feed_stale` with "records": True and the newest of those records' own
    stamps. `quiet_by_feed` gives, per company, the quiet overflows counted as reporting and when
    their feed last updated, so the page can stop counting them once that is over
    ingest.live.FEED_CURRENT_H old where it is read (a page open hours after the build).

    `monitored_weight` and `upstream_weight`: the transport weight of the overflows that
    report live, and of all of them, so the page can tell how much of what matters here is watched
    (levels.js, nowUnknown). Sandy Lane, Chester: 1 of its 13 overflows reports live, and it carries
    0.3% of the weight. Each `quiet_by_feed` entry gives its overflows' weight, for the page's ageing."""
    from dipcast.ingest.live import FEED_DOWN, LIVE, NO_FEED, STALE
    if ov.empty:
        return {"discharging_upstream": 0, "recent_upstream": 0, "monitored_upstream": 0,
                "feed_down_upstream": 0, "feed_down": [], "stale_upstream": 0, "feed_stale": [],
                "no_feed_upstream": 0, "quiet_by_feed": [], "monitored_weight": 0.0, "upstream_weight": 0.0}
    ov = with_data_states(ov)
    status, state = ov["status"], ov["data_state"]
    contrib = pd.Series(np.asarray(now_contrib, dtype=float), index=ov.index)
    dis = pd.Series(running(ov), index=ov.index)
    down = (status == FEED_DOWN) & ~dis
    recent = contrib.gt(0) & ~dis & (status != FEED_DOWN)
    quiet = (state == LIVE) & (status == 0) & ~recent
    stale = (state == STALE) & ~dis & ~recent
    rec = ov["record_stale"].fillna(False).astype(bool) if "record_stale" in ov else pd.Series(False, index=ov.index)
    w = pd.to_numeric(ov["weight"], errors="coerce").fillna(0.0) if "weight" in ov else pd.Series(0.0, index=ov.index)
    quiet_w = w[quiet].groupby(ov.loc[quiet, "company"].fillna("unknown")).sum()
    return {"discharging_upstream": int(dis.sum()), "recent_upstream": int(recent.sum()),
            "monitored_upstream": int((dis | recent | quiet).sum()),
            "monitored_weight": round(float(w[dis | recent | quiet].sum()), 4), "upstream_weight": round(float(w.sum()), 4),
            "feed_down_upstream": int(down.sum()), "feed_down": feed_down_summary(ov[down]),
            "stale_upstream": int(stale.sum()),
            "feed_stale": feed_stale_summary(ov[stale & ~rec]) + feed_stale_summary(ov[stale & rec], records=True),
            "no_feed_upstream": int(((state == NO_FEED) & ~(dis | recent | quiet)).sum()),
            "quiet_by_feed": [{"company": f["company"], "overflows": f["overflows"], "updated_at": f["since"],
                               "weight": round(float(quiet_w.get(f["company"], 0.0)), 4)}
                              for f in feed_stale_summary(ov[quiet])]}


def feed_down_summary(ov: pd.DataFrame) -> list[dict]:
    """Per company whose live feed did not answer the last poll: how many of these
    overflows it covers and when its feed last answered."""
    from dipcast.ingest.live import FEED_DOWN
    if ov.empty or "status" not in ov:
        return []
    down = ov[ov["status"] == FEED_DOWN]
    if down.empty:
        return []
    since = pd.to_datetime(down["feed_down_since"], utc=True) if "feed_down_since" in down else pd.Series(pd.NaT, index=down.index)
    out = []
    for c, g in down.groupby(down["company"].fillna("unknown")):
        t = since.loc[g.index].min()
        out.append({"company": str(c), "overflows": len(g), "since": None if pd.isna(t) else t.isoformat()})
    return out


def feeds_on_change(ov: pd.DataFrame) -> list[str]:
    """The companies upstream whose feed stamps a record only when it changes (ingest.live.data_states,
    `feed_on_change`)."""
    if ov.empty or "feed_on_change" not in ov:
        return []
    return sorted(ov.loc[ov["feed_on_change"].fillna(False).astype(bool), "company"].dropna().astype(str).unique())


def feed_stale_summary(ov: pd.DataFrame, records: bool = False) -> list[dict]:
    """Per company, for overflows whose feed answered but is stale (ingest.live.data_states):
    how many of them there are and when the feed last updated (None: it gives no time). With
    `records`, for records that have stopped updating in a feed that has not: the newest of their
    own stamps, and "records": True. A feed that stamps a record only when it changes (data_states'
    `feed_on_change`) has "on_change": True: its time is its last change, which a quiet spell leaves old."""
    if ov.empty:
        return []
    t = pd.to_datetime(ov["feed_updated_at"], utc=True) if "feed_updated_at" in ov else pd.Series(pd.NaT, index=ov.index)
    out = []
    for c, g in ov.groupby(ov["company"].fillna("unknown")):
        u = t.loc[g.index].max()
        on_change = not records and "feed_on_change" in g and bool(g["feed_on_change"].fillna(False).astype(bool).all())
        out.append({"company": str(c), "overflows": len(g), "since": None if pd.isna(u) else u.isoformat(),
                    **({"records": True} if records else {}), **({"on_change": True} if on_change else {})})
    return out


def overflows_geojson(bbox: tuple[float, float, float, float] | None = None, limit: int = 5000) -> dict:
    """Overflow points for the map. bbox = (min_lon, min_lat, max_lon, max_lat)."""
    ov = _overflows()
    if bbox:
        ov = ov[(ov.lon >= bbox[0]) & (ov.lat >= bbox[1]) & (ov.lon <= bbox[2]) & (ov.lat <= bbox[3])]
    ov = ov.head(limit)
    feats = []
    for _, r in ov.iterrows():
        props = {k: _clean(r.get(k)) for k in [
            "site_id", "company", "site_name", "receiving_watercourse", "status", "has_live", "data_state",
            "latest_event_start", "latest_event_end", "lta_spills"]}
        if props["data_state"] == "stale":   # its feed's last update, on these alone: the file is 6 MB
            props["feed_updated_at"] = _clean(r.get("feed_updated_at"))
        props |= carried_fields(r)          # a feed-down overflow's last status, on those alone
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(r.lon), float(r.lat)]},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": feats}
