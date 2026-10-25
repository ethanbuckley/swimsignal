"""Shadow forecasts and live scores for Scottish Water's overflows (docs/SCOTLAND-PLAN-2026-10.md).

Off unless DIPCAST_SCOTTISH_WATER=1 (config.SCOTTISH_WATER). When on, the site build calls run() after
everything it publishes is written. Each run:

1. Table. Every asset of the last stored answer of Scottish Water's API (ingest.scottish_water, which
   asks at most once an hour) is snapped to the river network as build_overflows snaps England's, with
   Scotland's marine rule (overflows.marine_scotland) in both passes, so an outfall on a sea loch, a
   firth or the open sea is not placed on a burn or a lochan beside it. Emergency overflows (EO, alone
   or in a mixed type) get no spill forecast: they "should only operate in the event of sewer system
   failure" (plan section 5.2); their live status stays in ingest.scottish_water's snapshot. Written
   to OVERFLOWS_FILE.
2. Rain. The Open-Meteo forecast for the cells of the overflows forecast, rationed as the
   click-anywhere data's is (scripts/build_any_point.py, any_point_rain): at most RAIN_CELLS_PER_BUILD
   of the oldest cells are asked for, and only cells whose cached forecast is RAIN_REFRESH_H old. The
   rest come from the shared rain cache if under RAIN_MAX_AGE_H old, and a cell with neither has no
   rain data (its forecast is logged with rain_available false and never scored, as in England).
   Builds ran 4 to 35 times a day over 1 to 10 Oct 2026, so the refresh floor, not the build count,
   sets the cost: each of the 320 cells at most 4 times a day, 1,280 Open-Meteo calls
   (forecast_calls) of the 10,000 a day. The
   requests are booked in the build's Open-Meteo ledger (rainfall.calls_today) as "scotland", and
   they come last in a build, so a spent ration holds them back before the spots'.
   Each row logs how old its rain forecast was (`rain_age_h`).
3. Forecast. forecast.spill_probabilities with the spill model as it stands (no refit) and the lead
   calibration, for today and DAYS_AHEAD more days, one row per overflow and day. Covariates: Scottish
   Water's own history by the rule of ingest/sw_covariates.py (return year before), where
   data/processed/sw_covariates.parquet is present and has the overflow; otherwise the pooled model's
   fallback (the median of the Scottish overflows passed, then 20 spills, 100 hours, 90%). Which one
   each row used is logged (`covariates`), and the version stamp names the file (cov=sw:<hash> or
   cov=default), so the two arms of plan section 6 are never mixed in one score.
4. Log. Into FORECASTS_DB, a forecast_overflows table like England's dipcast.duckdb, before any
   outcome is known: leads 0 to DAYS_AHEAD from the build's local day. To keep the file small, a
   build's forecasts are logged only if they could ever be the one scored: issued by the decision hour
   (forecast_log.DECISION_HOUR, 08:00 local), or the first of their issue day. verify_live scores the
   latest issued by 08:00, or, when there is none, the first of the day, so the rows left out are
   never selected (forecast_log.select_decision_forecasts).
5. Score. forecast_log.verify_live on a LiveStore of Scotland's files: ingest.scottish_water's history
   and coverage (England's coverage rules, each asset by its own transmit time) less every site-day an
   event flagged stuck touches (a monitor reading Overflowing for over a week may be frozen, so those
   days are neither spill nor no spill), and OVERFLOWS_FILE for the climatology baseline (lta_spills x
   spill-days per spill / 365, England's baseline, 20 a year where no Scottish count exists). Written
   to SCORES_JSON and SCORES_CSV with the Gate B summary (gate_b, below).

Nothing here is published. The files stay in the state directory (the actions cache in CI); site.yml's
state release lists its files by name and none of these is among them; no page or site file reads
them. The live feed's licence is unconfirmed (plan section 1, point 2), so this must stay so until
Scottish Water confirms it. The build log gets counts and costs only, no scores.

Gate B (plan section 6; the computation fixed here on 11 Oct 2026, before any Scottish forecast
was logged): over scored overflow-days at leads 1 to 3, Brier skill of
the calibrated forecast against the climatology baseline, 1 - Brier / Brier_clim. Its 95% interval is
the 2.5th and 97.5th percentiles of 2,000 resamples of target days (all overflows of a day together:
they share the day's rain), seed 0. It is computed per arm: the version stamp less the code version,
so a new spill model, calibration map or covariate file starts a new arm. "pass" needs at least
GATE_MIN_SPILL_DAYS distinct overflow-days with a spill and the interval's lower end above zero; under
that many it reads "too few spill-days". The plan asks for November 2026 to January 2027 at least;
whether that window is met is for whoever reads it, and the summary gives the first and last day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from datetime import timedelta

import numpy as np
import pandas as pd

from dipcast import config, forecast_log
from dipcast.ingest import scottish_water as sw

log = logging.getLogger(__name__)

OVERFLOWS_FILE = "scottish_water_overflows.parquet"
FORECASTS_DB = "scottish_water_forecasts.duckdb"
SCORED_COVERAGE_FILE = "scottish_water_coverage_scored.parquet"
SCORES_JSON = "scottish_water_verification.json"
SCORES_CSV = "scottish_water_verification.csv"
COVARIATES_NAME = "sw_covariates.parquet"
FILES = [OVERFLOWS_FILE, FORECASTS_DB, SCORED_COVERAGE_FILE, SCORES_JSON, SCORES_CSV]

DAYS_AHEAD = 4   # today and four more, as the spots
RAIN_CELLS_PER_BUILD = int(os.environ.get("DIPCAST_SCOTTISH_WATER_RAIN_CELLS", "150"))
RAIN_MAX_AGE_H = 24.0
RAIN_REFRESH_H = 6.0   # a cell is asked for at most every 6 hours, however many builds run
GATE_LEADS = (1, 2, 3)
GATE_MIN_SPILL_DAYS = 200
GATE_RESAMPLES = 2_000
GATE_SEED = 0
TABLE_COLS = ["site_id", "company", "site_name", "asset_type", "emergency", "status", "data_state", "lat", "lon",
              "receiving_watercourse", "link_id", "frac", "snap_dist_m", "form", "snap_confidence", "marine",
              "forecast", "abstain", "lta_spills", "spill_hours", "edm_operational_pct", "covariates"]


def _path(name: str):
    return config.STATE / name


# ------------------------------------------------------------------ 1. table
def covariates(year: int) -> tuple[pd.DataFrame | None, str]:
    """Scottish Water's covariates for a forecast in `year` (return year `year` - 1) and the arm's
    label: 'sw:<first 8 of the file's md5>', or 'default' without the file."""
    from dipcast.ingest.sw_covariates import covariates_for
    p = config.PROCESSED / COVARIATES_NAME
    if not p.exists():
        return None, "default"
    return covariates_for(pd.read_parquet(p), year), "sw:" + hashlib.md5(p.read_bytes()).hexdigest()[:8]


def overflow_table(net, snap: pd.DataFrame | None = None, year: int | None = None) -> tuple[pd.DataFrame, str]:
    """One row per asset of the stored answer (TABLE_COLS): where it snaps, whether it is forecast and
    if not why, and its covariates. Returns the table and the covariate arm's label."""
    from dipcast.overflows import _second_pass, marine_scotland
    if snap is None:
        snap = pd.read_parquet(config.state_read(sw.LATEST_FILE))
    df = snap.dropna(subset=["lat", "lon"]).drop_duplicates("site_id").reset_index(drop=True)
    df = df[[c for c in TABLE_COLS[:10] if c in df]].copy()
    s = net.snap_many(df["lon"].to_numpy(), df["lat"].to_numpy(), max_m=config.SNAP_MAX_M)
    df["link_id"] = s["link_id"].to_numpy()
    df["frac"] = s["frac"].to_numpy(dtype=float)
    df["snap_dist_m"] = s["dist_m"].to_numpy(dtype=float)
    df["form"] = s["form"].to_numpy()
    df["marine"] = marine_scotland(df["receiving_watercourse"], df["form"]).to_numpy()
    df.loc[df["marine"], ["link_id", "form"]] = None
    df.loc[df["marine"], ["frac", "snap_dist_m"]] = np.nan
    df["snap_confidence"] = np.where(df["link_id"].notna(), "high", None)
    df = _second_pass(net, df, is_marine=lambda rows: df.loc[rows.index, "marine"])
    snapped = df["link_id"].notna()
    emergency = df["emergency"].astype(bool)
    df["forecast"] = snapped & ~emergency
    df["abstain"] = np.select([emergency, df["snap_confidence"].eq("marine"), ~snapped],
                              ["emergency overflow", "marine", "not snapped"], None)
    year = year or pd.Timestamp.now(tz=forecast_log.LOCAL_TZ).year
    cov, label = covariates(year)
    if cov is not None and len(cov):
        df = df.merge(cov[["site_id", "lta_spills", "spill_hours", "edm_operational_pct"]], on="site_id", how="left")
    else:
        for c in ("lta_spills", "spill_hours", "edm_operational_pct"):
            df[c] = np.nan
    df["covariates"] = np.where(df["lta_spills"].notna(), f"sw{year - 1}", "filled")
    return df[TABLE_COLS], label


# ------------------------------------------------------------------ 2. rain
def forecast_calls(n_cells: int) -> float:
    """Open-Meteo's count for forecasts of n_cells cells (rainfall.forecast_weight): one variable over
    FORECAST_PAST_DAYS + FORECAST_DAYS + 1 days is 1 a location."""
    from dipcast.ingest import rainfall
    return rainfall.forecast_weight(n_cells)


def shadow_rain(sub: pd.DataFrame, budget: int = RAIN_CELLS_PER_BUILD, max_age_h: float = RAIN_MAX_AGE_H,
                fetch=None, refresh_h: float = RAIN_REFRESH_H) -> tuple[pd.DataFrame, dict]:
    """Hourly rain for the overflows' cells, rationed (module docstring, step 2): a cell is asked for
    again only once its cached forecast is `refresh_h` old, at most `budget` cells a build, oldest
    first. `fetch(cells)` is rainfall.fetch_forecast with one retry unless given. Never raises."""
    from dipcast.ingest import rainfall
    fetch = fetch or (lambda cells: rainfall.fetch_forecast(cells, attempts=2, what="scotland"))
    cells = rainfall.cells_for_sites(sub["lat"], sub["lon"])
    path = {c: rainfall.CACHE / f"forecast_{rainfall.cell_key(*c)}.parquet" for c in cells}

    def age(c) -> float:
        return time.time() - path[c].stat().st_mtime if path[c].exists() else math.inf

    due = sorted((c for c in cells if age(c) >= max(rainfall.FORECAST_TTL_S, refresh_h * 3600)), key=lambda c: -age(c))
    take = due[:max(0, budget)]
    error = None
    if take:
        try:
            fetch(take)
        except Exception as e:  # noqa: BLE001 - what was cached stays usable
            error = str(e) or type(e).__name__
    frames = []
    for c in cells:
        if age(c) <= max_age_h * 3600:
            try:
                frames.append(pd.read_parquet(path[c]))
            except Exception as e:  # noqa: BLE001 - a torn cache file counts as none
                log.warning("rain cache %s unreadable: %s", path[c].name, e)
    cols = ["cell_lat", "cell_lon", "time", "precip_mm", "issued_at"]
    rain = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    fetched = sum(1 for c in take if age(c) < rainfall.FORECAST_TTL_S)
    return rain, {"cells": len(cells), "due": len(due), "asked": len(take),
                  "requests": math.ceil(len(take) / rainfall.FORECAST_BATCH), "calls": round(forecast_calls(len(take)), 1),
                  "fetched": fetched, "usable": len(frames), **({"error": error} if error else {})}


# ------------------------------------------------------------------ 3. forecast
def forecast_rows(table: pd.DataFrame, now: pd.Timestamp, rain: pd.DataFrame, model, version: str) -> pd.DataFrame:
    """One row per forecast overflow and day, today to DAYS_AHEAD, in forecast_overflows' columns plus
    `covariates` and `rain_age_h`. p is 0 with rain_available false where the cell had no rain, as
    England logs it."""
    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.forecast import calibrate_by_lead, spill_probabilities
    sub = table[table["forecast"]].drop_duplicates("site_id").reset_index(drop=True)
    now = pd.Timestamp(now).tz_convert(forecast_log.LOCAL_TZ)
    days = pd.date_range(now.floor("D"), periods=DAYS_AHEAD + 1, freq="D")
    if sub.empty:
        return pd.DataFrame()
    shape = (len(sub), len(days))
    if len(rain):
        p_raw, ok, rain_mm = spill_probabilities(sub, days, model, return_rain=True, rain=rain)
    else:
        p_raw, ok, rain_mm = np.full(shape, np.nan), np.zeros(shape, dtype=bool), np.full(shape, np.nan)
    p_cal = calibrate_by_lead(p_raw, first_lead=0)
    age = pd.Series(np.nan, index=sub.index)
    if len(rain) and "issued_at" in rain:
        issued = rain.groupby(["cell_lat", "cell_lon"])["issued_at"].max()
        cl, cn = grid_cell(sub["lat"].to_numpy(), sub["lon"].to_numpy())
        t = pd.to_datetime(pd.Series([issued.get((float(a), float(b))) for a, b in zip(cl, cn, strict=True)]), utc=True)
        age = ((now.tz_convert("UTC") - t).dt.total_seconds() / 3600).round(2)
    n, k = shape
    rows = pd.DataFrame({
        "issued_at": now, "issue_day": now.date(),
        "lat": np.repeat(sub["lat"].to_numpy(dtype=float), k), "lon": np.repeat(sub["lon"].to_numpy(dtype=float), k),
        "site_id": np.repeat(sub["site_id"].astype(str).to_numpy(), k), "has_live": True,
        "target_day": np.tile(np.array([d.date() for d in days], dtype=object), n),
        "lead": np.tile(np.arange(k), n),
        "p_raw": np.nan_to_num(p_raw, nan=0.0).ravel(), "p_cal": np.nan_to_num(p_cal, nan=0.0).ravel(), "weight": 1.0,
        "rain_available": ok.ravel(), "version": version, "rain_mm": rain_mm.ravel(),
        "covariates": np.repeat(sub["covariates"].to_numpy(), k), "rain_age_h": np.repeat(age.to_numpy(dtype=float), k)})
    return rows


# ------------------------------------------------------------------ 4. log
def _db_conn():
    con = forecast_log._conn(_path(FORECASTS_DB))
    con.execute("ALTER TABLE forecast_overflows ADD COLUMN IF NOT EXISTS covariates VARCHAR")
    con.execute("ALTER TABLE forecast_overflows ADD COLUMN IF NOT EXISTS rain_age_h DOUBLE")
    return con


def could_be_scored(con, issued_at: pd.Timestamp) -> bool:
    """Whether forecasts issued now could ever be the scored ones (module docstring, step 4)."""
    local = pd.Timestamp(issued_at).tz_convert(forecast_log.LOCAL_TZ)
    cutoff = local.normalize().tz_localize(None) + pd.Timedelta(hours=forecast_log.DECISION_HOUR)
    if local.tz_localize(None) <= cutoff:
        return True
    n = con.execute("SELECT count(*) FROM forecast_overflows WHERE issue_day = ?", [local.date()]).fetchall()[0][0]
    return n == 0


def log_rows(rows: pd.DataFrame) -> int:
    """Append `rows` (forecast_rows) to FORECASTS_DB if they could be scored. Returns rows written."""
    if rows.empty:
        return 0
    with forecast_log._LOCK:
        con = _db_conn()
        try:
            if not could_be_scored(con, rows["issued_at"].iloc[0]):
                return 0
            con.register("new_rows", rows)
            # Fetch the insert's count row: duckdb 2 refuses unregister while a result is unread.
            con.execute("INSERT INTO forecast_overflows BY NAME SELECT * FROM new_rows").fetchall()
            con.unregister("new_rows")
        finally:
            con.close()
    return len(rows)


# ------------------------------------------------------------------ 5. score
def store() -> forecast_log.LiveStore:
    return forecast_log.LiveStore(db=_path(FORECASTS_DB), history=config.state_read(sw.HISTORY_FILE),
                                  coverage=_path(SCORED_COVERAGE_FILE), overflows=_path(OVERFLOWS_FILE),
                                  out_json=_path(SCORES_JSON), out_csv=_path(SCORES_CSV))


def scored_coverage(cov: pd.DataFrame, hist: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """The asset coverage less every (site_id, day) an event flagged stuck touches, and how many such
    site-days were removed."""
    stuck = hist[hist["stuck"].astype(bool)] if "stuck" in hist and len(hist) else hist.iloc[0:0]
    if stuck.empty or cov.empty:
        return cov, 0
    bad = forecast_log.observed_spill_days(stuck)
    bad["day"] = pd.to_datetime(bad["day"]).dt.date
    days = pd.to_datetime(cov["day"]).dt.date
    m = cov.assign(_d=days).merge(bad.rename(columns={"day": "_d"}).assign(_bad=True), on=["site_id", "_d"], how="left")
    drop = m["_bad"].eq(True).to_numpy()
    return cov[~drop].reset_index(drop=True), int(drop.sum())


def arm_of(version: pd.Series) -> pd.Series:
    """The version stamp less its code part: spill model, calibration, E. coli model, rain and covariates."""
    return version.fillna("unstamped").str.replace(r"code=[^;]*;?", "", regex=True)


def gate_b(rows: pd.DataFrame) -> dict:
    """Gate B's figures for scored rows (overflow_id, day, lead, forecast_calibrated, climatology,
    observed, arm), by arm (module docstring)."""
    out = {"leads": list(GATE_LEADS), "min_spill_days": GATE_MIN_SPILL_DAYS, "resamples": GATE_RESAMPLES,
           "seed": GATE_SEED, "unit": "overflow-day forecast, resampled by target day", "arms": []}
    g = rows[rows["lead"].isin(GATE_LEADS)] if len(rows) else rows
    for arm, a in (g.groupby("arm") if len(g) else []):
        y = a["observed"].to_numpy(dtype=float)
        se_f = (a["forecast_calibrated"].to_numpy(dtype=float) - y) ** 2
        se_c = (a["climatology"].to_numpy(dtype=float) - y) ** 2
        spill_days = int(a.loc[a["observed"] == 1, ["overflow_id", "day"]].drop_duplicates().shape[0])
        r = {"arm": arm, "n": len(a), "n_overflows": int(a["overflow_id"].nunique()), "n_days": int(a["day"].nunique()),
             "first_day": str(a["day"].min()), "last_day": str(a["day"].max()), "n_spill_days": spill_days,
             "brier": float(se_f.mean()), "climatology_brier": float(se_c.mean()),
             "skill": float(1 - se_f.sum() / se_c.sum()) if se_c.sum() > 0 else None, "interval_95": None}
        by_day = pd.DataFrame({"day": a["day"].to_numpy(), "f": se_f, "c": se_c}).groupby("day")[["f", "c"]].sum()
        if len(by_day) >= 2 and se_c.sum() > 0:
            rng = np.random.default_rng(GATE_SEED)
            idx = rng.integers(0, len(by_day), size=(GATE_RESAMPLES, len(by_day)))
            f, c = by_day["f"].to_numpy()[idx].sum(axis=1), by_day["c"].to_numpy()[idx].sum(axis=1)
            sk = 1 - f[c > 0] / c[c > 0]
            r["interval_95"] = [float(np.percentile(sk, 2.5)), float(np.percentile(sk, 97.5))]
        lower = (r["interval_95"] or [None])[0]
        r["status"] = ("too few spill-days" if spill_days < GATE_MIN_SPILL_DAYS
                       else "pass" if lower is not None and lower > 0 else "not passed")
        out["arms"].append(r)
    return out


def score(as_of=None) -> dict:
    """Score the logged Scottish forecasts (module docstring, step 5) and write SCORES_JSON and SCORES_CSV."""
    as_of = as_of or pd.Timestamp.now(tz=forecast_log.LOCAL_TZ).date()
    hp, cp = config.state_read(sw.HISTORY_FILE), config.state_read(sw.COVERAGE_FILE)
    hist = pd.read_parquet(hp) if hp.exists() else pd.DataFrame(columns=sw.HISTORY_COLS)
    cov = pd.read_parquet(cp) if cp.exists() else pd.DataFrame(columns=["site_id", "day", "n_known", "n_unknown", "n_stale", "slots"])
    cov, n_stuck = scored_coverage(cov, hist)
    cov.to_parquet(config.state_write(SCORED_COVERAGE_FILE), index=False)
    st = store()
    out = forecast_log.verify_live(as_of, store=st)
    out["rules"]["unstamped_feed"] = ("not used: each asset's data state comes from its own transmit times "
                                     "(ingest.scottish_water), so the coverage file marks a stale asset poll by poll")
    out["rules"]["baseline"] = ("lta_spills from Scottish Water's event history (ingest/sw_covariates.py, return year before) x "
                                "spill-days per spill / 365, as England's; 20 spills a year where an overflow has no count")
    out["rules"]["stuck"] = "site-days touched by an event flagged stuck (over 168 h Overflowing) are not scored"
    rows = pd.read_csv(st.out_csv) if st.out_csv.exists() else pd.DataFrame()
    if len(rows):
        with forecast_log._LOCK:
            con = _db_conn()
            try:
                dec = forecast_log.select_decision_forecasts(con, as_of - timedelta(days=1))
            finally:
                con.close()
        dec = dec.assign(day=dec["target_day"].astype(str), arm=arm_of(dec["version"]))
        rows = rows.merge(dec[["site_id", "day", "lead", "arm"]].rename(columns={"site_id": "overflow_id"}),
                          on=["overflow_id", "day", "lead"], how="left")
        rows["arm"] = rows["arm"].fillna("unknown")
    out["shadow"] = {"note": "Shadow scores for Scottish Water (Scotland plan, Stage B). Not shown or published: the live "
                             "feed's licence is unconfirmed.",
                     "n_stuck_site_days_left_out": n_stuck, "gate_b": gate_b(rows)}
    st.out_json.write_text(json.dumps(out, indent=1, default=str))
    return out


# ------------------------------------------------------------------ run
def run(net=None, now: pd.Timestamp | None = None, rain_fetch=None, model=None) -> dict:
    """Table, rain, forecast, log and score once (module docstring). Returns counts and costs only,
    for the build log. Never raises: the shadow must not stop the site."""
    t0 = time.time()
    summary: dict = {"ok": False}
    try:
        from dipcast.model import forecast as fc
        net = net or fc._net()
        model = model if model is not None else fc._model()
        now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
        table, arm = overflow_table(net, year=now.tz_convert(forecast_log.LOCAL_TZ).year)
        table.to_parquet(config.state_write(OVERFLOWS_FILE), index=False)
        summary["assets"] = len(table)
        summary["forecast"] = int(table["forecast"].sum())
        summary["abstain"] = {str(k): int(v) for k, v in table["abstain"].value_counts().items()}
        summary["covariates"] = arm
        t1 = time.time()
        rain, summary["rain"] = shadow_rain(table[table["forecast"]], fetch=rain_fetch)
        summary["rain"]["seconds"] = round(time.time() - t1, 1)
        version = f"{fc.model_version()};cov={arm};region=scotland-shadow"
        rows = forecast_rows(table, now, rain, model, version)
        summary["rows_logged"] = log_rows(rows)
        out = score()
        summary["n_scored"] = int(out.get("n_scored", 0))
        summary["ok"] = True
    except Exception as e:  # noqa: BLE001 - shadow only; the site is already written
        log.error("Scottish Water shadow forecasts failed: %s", e)
        summary["error"] = str(e)
    summary["seconds"] = round(time.time() - t0, 1)
    log.info("Scottish Water shadow (not shown or published): %s", summary)
    return summary
