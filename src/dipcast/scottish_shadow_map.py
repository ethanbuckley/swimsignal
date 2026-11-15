"""Scotland's mapped forecast in shadow: arm `scotland-map-v1` (docs/SCOTLAND-MAP-SHADOW-ARM-2026-11.md, written
and pushed before this file).

The Scotland trial (scotland_trial.py) would show spill chances that have been through Scotland's calibration map.
The existing shadow (scottish_shadow.py, Gate B) scores the same raw chances through England's lead calibration.
This arm logs the mapped chance beside it, so the live check can score what the trial would show.

Log. scottish_shadow.run hands its rows here after it has written them. Where the existing shadow logged the
build, the same rows go into TABLE in DB, a file of this arm's own in the state directory: `p_raw` and `p_prod`
(England's calibration, the comparator) exactly as the existing shadow logged them, and `p_map`, the trial's own
scotland_trial.apply_map on `p_raw`. Nothing of the existing shadow is read back, altered or rewritten, and no rain
is asked for: the arm costs no Open-Meteo call.

Fallback. v1 is one map: the file of MAP_SHA256, fitted for one spill model. With the file missing, another file in
its place, or another spill model in use, the trial would be off, so rows are logged with `map_applied` false,
`p_map` empty and the reason in `fallback`. A row whose cell had no rain is logged the same way ("no rain") and is
never scored, as in the existing shadow.

Read (read, counts). Once, on or after READ_NOT_BEFORE, on target days to WINDOW_END, by Gate B's own scoring
(forecast_log.verify_live on a store of copies) and Gate B's own interval (scottish_shadow.gate_b). Before that
date only counts() runs: it joins no outcome. Nothing here is published: no page, release or site file reads DB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config, forecast_log, scotland_trial

log = logging.getLogger(__name__)

ARM = "scotland-map-v1"
TABLE = "shadow_scotland_map_v1"
DB = "scottish_water_map_v1.duckdb"
# data/processed/scotland_calibration.json as committed on 1 Nov 2026 (42efc002): a = 0.449, b = 0.750, fitted for
# spill model SPILL_STAMP. Another file is another arm: it needs its own table and statement.
MAP_SHA256 = "447a02a1556fd811719bc49776131ef1a2e386020ad5449030624755b172811d"
SPILL_STAMP = "808da63d"
COLUMNS = ("issued_at", "issue_day", "site_id", "target_day", "lead", "p_raw", "p_prod", "p_map", "map_applied",
           "fallback", "rain_available", "rain_mm", "rain_age_h", "covariates", "arm", "version")

# The read (statement, sections 5 and 6).
READ_NOT_BEFORE = date(2027, 2, 3)
WINDOW_END = date(2027, 1, 31)
DERIVED_FROM = date(2026, 11, 2)   # the first issue day after the map was committed
LEADS = (1, 2, 3)
MIN_SPILL_DAYS = 200
MIN_TARGET_DAYS = 30
LEVEL_BAND = (0.9, 1.1)
RESAMPLES = 2_000
SEED = 0
WET_MM = 10.0
OLD_RAIN_H = 12.0
TOLERANCE = 1e-9


# ------------------------------------------------------------------ the map
def map_state() -> tuple[bool, str | None, str]:
    """(whether v1's map can be applied, why not, the first 8 of the file's SHA-256 or "none")."""
    p = config.PROCESSED / scotland_trial.MAP_FILE
    if not p.exists():
        return False, "no map file", "none"
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    if sha != MAP_SHA256:
        return False, "map file is not v1's", sha[:8]
    if scotland_trial.calibration_map() is None:
        return False, "map fitted for another spill model", sha[:8]
    return True, None, sha[:8]


def pinned_map(path: Path | None = None) -> dict:
    """v1's map from its file, whatever spill model is in use now (the read's derived series). Raises if the file
    is not v1's."""
    p = path or config.PROCESSED / scotland_trial.MAP_FILE
    if hashlib.sha256(p.read_bytes()).hexdigest() != MAP_SHA256:
        raise ValueError(f"{p.name} is not {ARM}'s map")
    return json.loads(p.read_text())


def apply_pinned(p: np.ndarray, m: dict) -> np.ndarray:
    """scotland_trial.apply_map's formula with the map given, for rows logged under SPILL_STAMP."""
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return 1 / (1 + np.exp(-(m["a"] + m["b"] * np.log(q / (1 - q)))))


# ------------------------------------------------------------------ log
def _part(version: str, key: str) -> str:
    m = re.search(rf"(?:^|;){key}=([^;]*)", version or "")
    return m.group(1) if m else "none"


def mapped_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """The arm's rows (COLUMNS) from scottish_shadow.forecast_rows' rows, which are left as they are."""
    ok, why, sha8 = map_state()
    rain = rows["rain_available"].to_numpy(dtype=bool)
    p_raw = rows["p_raw"].to_numpy(dtype=float)
    applied = rain & ok
    p_map = np.full(len(rows), np.nan)
    if applied.any():
        p_map[applied] = scotland_trial.apply_map(p_raw[applied])
    version = str(rows["version"].iloc[0]) if len(rows) else ""
    return pd.DataFrame({
        "issued_at": rows["issued_at"], "issue_day": rows["issue_day"].to_numpy(),
        "site_id": rows["site_id"].astype(str).to_numpy(), "target_day": rows["target_day"].to_numpy(),
        "lead": rows["lead"].to_numpy(dtype=int), "p_raw": p_raw, "p_prod": rows["p_cal"].to_numpy(dtype=float),
        "p_map": p_map, "map_applied": applied,
        "fallback": np.where(applied, None, np.where(rain, why, "no rain")),
        "rain_available": rain, "rain_mm": rows["rain_mm"].to_numpy(dtype=float),
        "rain_age_h": rows["rain_age_h"].to_numpy(dtype=float), "covariates": rows["covariates"].to_numpy(),
        "arm": f"{ARM};spill={_part(version, 'spill')};cov={_part(version, 'cov')};map={sha8}",
        "version": rows["version"].to_numpy()}, index=rows.index)


def _conn(path: Path, read_only: bool = False):
    import duckdb
    if read_only:
        return duckdb.connect(str(path), read_only=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            issued_at TIMESTAMPTZ, issue_day DATE, site_id VARCHAR, target_day DATE, lead INTEGER,
            p_raw DOUBLE, p_prod DOUBLE, p_map DOUBLE, map_applied BOOLEAN, fallback VARCHAR,
            rain_available BOOLEAN, rain_mm DOUBLE, rain_age_h DOUBLE, covariates VARCHAR, arm VARCHAR,
            version VARCHAR)""")
    return con


def log_rows(rows: pd.DataFrame, existing_logged: int) -> dict:
    """Append the arm's rows for a build the existing shadow logged (`existing_logged` rows written there); nothing
    for a build it did not, so the two logs hold the same issues. A build already in the table is not written
    twice. Returns counts for the build log."""
    if rows is None or rows.empty or not existing_logged:
        return {"rows_logged": 0}
    out = mapped_rows(rows)
    with forecast_log._LOCK:
        con = _conn(config.state_write(DB))
        try:
            if con.execute(f"SELECT count(*) FROM {TABLE} WHERE issued_at = ?", [out["issued_at"].iloc[0]]).fetchall()[0][0]:
                return {"rows_logged": 0, "note": "this issue is already logged"}
            con.register("new_rows", out)
            # Fetch the insert's count row: duckdb 2 refuses unregister while a result is unread.
            con.execute(f"INSERT INTO {TABLE} BY NAME SELECT * FROM new_rows").fetchall()
            con.unregister("new_rows")
        finally:
            con.close()
    fallback = {str(k): int(v) for k, v in out["fallback"].value_counts().items()}
    return {"rows_logged": len(out), "map_applied": int(out["map_applied"].sum()), "arm": out["arm"].iloc[0],
            **({"fallback": fallback} if fallback else {})}


# ------------------------------------------------------------------ read: rows
def _ms(t: pd.Series) -> pd.Series:
    return (pd.to_datetime(t, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")


def _logged(state: Path) -> pd.DataFrame:
    p = state / DB
    if not p.exists():
        return pd.DataFrame(columns=list(COLUMNS))
    con = _conn(p, read_only=True)
    try:
        df = con.execute(f"SELECT * FROM {TABLE}").df()
    finally:
        con.close()
    for c in ("issue_day", "target_day"):
        df[c] = pd.to_datetime(df[c]).dt.date
    return df


def _existing(state: Path, first: date | None = None) -> pd.DataFrame:
    """The existing shadow's logged forecasts from issue day `first` on, read only."""
    from dipcast import scottish_shadow
    p = state / scottish_shadow.FORECASTS_DB
    cols = ["issued_at", "issue_day", "site_id", "target_day", "lead", "p_raw", "p_cal", "rain_available", "version",
            "rain_mm", "covariates", "rain_age_h"]
    if not p.exists():
        return pd.DataFrame(columns=cols)
    con = _conn(p, read_only=True)
    try:
        have = {r[0] for r in con.execute("DESCRIBE forecast_overflows").fetchall()}
        sel = ", ".join(c if c in have else f"NULL AS {c}" for c in cols)
        df = con.execute(f"SELECT {sel} FROM forecast_overflows WHERE issue_day >= ?", [first or date(2000, 1, 1)]).df()
    finally:
        con.close()
    for c in ("issue_day", "target_day"):
        df[c] = pd.to_datetime(df[c]).dt.date
    return df


def same_issues(logged: pd.DataFrame, existing: pd.DataFrame) -> dict:
    """Whether each logged row has the existing shadow's row for the same overflow, issue and target day, with the
    same raw and England-calibrated chance, and whether `p_map` is v1's map of that raw chance. Forecasts only."""
    if logged.empty:
        return {"compared": 0}
    a = logged.assign(_ms=_ms(logged["issued_at"]))
    b = existing.assign(_ms=_ms(existing["issued_at"]))[["site_id", "target_day", "_ms", "p_raw", "p_cal", "version"]]
    m = a.merge(b, on=["site_id", "target_day", "_ms"], how="left", suffixes=("", "_existing"))
    found = m["p_cal"].notna()
    out = {"compared": len(m), "not_in_existing_log": int((~found).sum()),
           "p_raw_differs": int((found & ((m["p_raw"] - m["p_raw_existing"]).abs() > TOLERANCE)).sum()),
           "p_prod_differs": int((found & ((m["p_prod"] - m["p_cal"]).abs() > TOLERANCE)).sum())}
    try:
        mp = pinned_map()
        on = found & m["map_applied"].astype(bool)
        d = np.abs(m.loc[on, "p_map"].to_numpy(dtype=float) - apply_pinned(m.loc[on, "p_raw_existing"].to_numpy(dtype=float), mp))
        out["p_map_is_not_the_map_of_p_raw"] = int((d > TOLERANCE).sum())
    except (OSError, ValueError) as e:
        out["p_map_check"] = f"not run: {e}"
    return out


def counts(state: Path | None = None) -> dict:
    """What the log holds, with no outcome joined: allowed on any day (statement, section 5)."""
    state = Path(state) if state else config.STATE
    df = _logged(state)
    out = {"arm": ARM, "rows": len(df), "outcomes_joined": False}
    if df.empty:
        return out
    scoreable = df["rain_available"].astype(bool)
    out.update({
        "first_issue_day": str(df["issue_day"].min()), "last_issue_day": str(df["issue_day"].max()),
        "issue_days": int(df["issue_day"].nunique()), "issues": int(df["issued_at"].nunique()),
        "overflows": int(df["site_id"].nunique()), "arms": {str(k): int(v) for k, v in df["arm"].value_counts().items()},
        "rain_available_share": round(float(scoreable.mean()), 4),
        "map_applied_share_of_rows_with_rain": round(float(df.loc[scoreable, "map_applied"].mean()), 4) if scoreable.any() else None,
        "fallback": {str(k): int(v) for k, v in df["fallback"].value_counts().items()},
        "covariates": {str(k): int(v) for k, v in df["covariates"].value_counts().items()},
        "median_rain_age_h": float(df["rain_age_h"].median()) if df["rain_age_h"].notna().any() else None,
        "same_issues_as_existing_shadow": same_issues(df, _existing(state, df["issue_day"].min()))})
    return out


# ------------------------------------------------------------------ read: scores
def _score(fc: pd.DataFrame, p_col: str, state: Path, work: Path, as_of: date, tag: str) -> pd.DataFrame:
    """Gate B's scored rows (forecast_log.SCORED_COLUMNS) for forecasts `fc` with fc[p_col] as the calibrated
    chance: verify_live on a store of copies in `work`, with Scotland's polls, the stuck-monitor rule and the
    Scottish overflow table. Nothing in `state` is written."""
    from dipcast import scottish_shadow
    from dipcast.ingest import scottish_water as sw
    work.mkdir(parents=True, exist_ok=True)
    db = work / f"{tag}.duckdb"
    db.unlink(missing_ok=True)
    rows = pd.DataFrame({
        "issued_at": fc["issued_at"], "issue_day": fc["issue_day"].to_numpy(), "lat": np.nan, "lon": np.nan,
        "site_id": fc["site_id"].astype(str).to_numpy(), "has_live": True, "target_day": fc["target_day"].to_numpy(),
        "lead": fc["lead"].to_numpy(dtype=int), "p_raw": fc["p_raw"].to_numpy(dtype=float),
        "p_cal": fc[p_col].to_numpy(dtype=float), "weight": 1.0, "rain_available": True, "version": tag,
        "rain_mm": fc["rain_mm"].to_numpy(dtype=float)}, index=fc.index)
    con = forecast_log._conn(db)
    try:
        con.register("new_rows", rows)
        con.execute("INSERT INTO forecast_overflows BY NAME SELECT * FROM new_rows").fetchall()
        con.unregister("new_rows")
    finally:
        con.close()
    hp, cp = state / sw.HISTORY_FILE, state / sw.COVERAGE_FILE
    hist = pd.read_parquet(hp) if hp.exists() else pd.DataFrame(columns=sw.HISTORY_COLS)
    cov = (pd.read_parquet(cp) if cp.exists()
           else pd.DataFrame(columns=["site_id", "day", "n_known", "n_unknown", "n_stale", "slots"]))
    cov, _ = scottish_shadow.scored_coverage(cov, hist)
    cov.to_parquet(work / f"{tag}_coverage.parquet", index=False)
    store = forecast_log.LiveStore(db=db, history=hp, coverage=work / f"{tag}_coverage.parquet",
                                   overflows=state / scottish_shadow.OVERFLOWS_FILE,
                                   out_json=work / f"{tag}.json", out_csv=work / f"{tag}.csv")
    forecast_log.verify_live(as_of, store=store)
    return pd.read_csv(store.out_csv) if store.out_csv.exists() else pd.DataFrame(columns=forecast_log.SCORED_COLUMNS)


def scored(fc: pd.DataFrame, state: Path, work: Path, as_of: date, tag: str) -> pd.DataFrame:
    """One row per scored overflow, target day and lead with both forecasts: `p_map`, `p_prod`, the climatology
    baseline, what happened, and the row's `covariates`, `rain_mm`, `rain_age_h`, `arm` and England calibration
    stamp. `fc` needs COLUMNS' forecast columns; only rows with the map applied and target days to WINDOW_END are
    scored."""
    cols = ["overflow_id", "day", "lead", "p_map", "p_prod", "climatology", "observed", "covariates", "rain_mm",
            "rain_age_h", "arm", "cal"]
    fc = fc[fc["map_applied"].astype(bool) & (fc["target_day"] <= WINDOW_END)].reset_index(drop=True)
    if fc.empty:
        return pd.DataFrame(columns=cols)
    a = _score(fc, "p_map", state, work, as_of, f"{tag}_map")
    b = _score(fc, "p_prod", state, work, as_of, f"{tag}_prod")
    if a.empty:
        return pd.DataFrame(columns=cols)
    key = ["overflow_id", "day", "lead"]
    m = a.rename(columns={"forecast_calibrated": "p_map"})[[*key, "p_map", "climatology", "observed"]].merge(
        b.rename(columns={"forecast_calibrated": "p_prod"})[[*key, "p_prod"]], on=key, how="inner", validate="1:1")
    # The scored forecast of an overflow, target day and lead is the one of issue day (target day - lead) that
    # verify_live selected: the latest by 08:00. Its attributes come from the same selection on the same rows.
    con = _conn(work / f"{tag}_map.duckdb", read_only=True)
    try:
        dec = forecast_log.select_decision_forecasts(con, as_of - timedelta(days=1))
    finally:
        con.close()
    dec = dec[dec["before_cutoff"]].assign(_ms=_ms(dec["issued_at"]))[["site_id", "target_day", "lead", "_ms"]]
    att = fc.assign(_ms=_ms(fc["issued_at"]), cal=fc["version"].map(lambda v: _part(v, "cal")))
    att = dec.merge(att[["site_id", "target_day", "_ms", "covariates", "rain_mm", "rain_age_h", "arm", "cal"]],
                    on=["site_id", "target_day", "_ms"], how="left")
    att = att.assign(overflow_id=att["site_id"].astype(str), day=att["target_day"].astype(str))
    return m.astype({"overflow_id": str}).merge(att[[*key, "covariates", "rain_mm", "rain_age_h", "arm", "cal"]],
                                                on=key, how="left", validate="1:1")[cols]


def _by_day(g: pd.DataFrame) -> pd.DataFrame:
    y = g["observed"].to_numpy(dtype=float)
    return pd.DataFrame({"day": g["day"].to_numpy(), "se_map": (g["p_map"].to_numpy(dtype=float) - y) ** 2,
                         "se_prod": (g["p_prod"].to_numpy(dtype=float) - y) ** 2,
                         "se_clim": (g["climatology"].to_numpy(dtype=float) - y) ** 2,
                         "p_map": g["p_map"].to_numpy(dtype=float), "p_prod": g["p_prod"].to_numpy(dtype=float),
                         "y": y}).groupby("day").sum()


def _interval(num: np.ndarray, den: np.ndarray, kind: str) -> list[float] | None:
    """Gate B's interval (scottish_shadow.gate_b): RESAMPLES draws of target days, seed SEED, 2.5th and 97.5th
    percentiles. `kind` "skill" is 1 - num / den, "ratio" is num / den, each on the days' sums."""
    if len(num) < 2 or den.sum() <= 0:
        return None
    idx = np.random.default_rng(SEED).integers(0, len(num), size=(RESAMPLES, len(num)))
    n, d = num[idx].sum(axis=1), den[idx].sum(axis=1)
    r = n[d > 0] / d[d > 0]
    v = 1 - r if kind == "skill" else r
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def _piece(g: pd.DataFrame) -> dict:
    """Point figures for a group of scored rows: counts, the three Brier scores, both levels, M1's and M3's value."""
    d = _by_day(g).sum()
    n = len(g)
    return {"n": n, "target_days": int(g["day"].nunique()),
            "spill_days": int(g.loc[g["observed"] == 1, ["overflow_id", "day"]].drop_duplicates().shape[0]),
            "brier_map": float(d["se_map"] / n), "brier_prod": float(d["se_prod"] / n), "brier_clim": float(d["se_clim"] / n),
            "skill_vs_climatology": float(1 - d["se_map"] / d["se_clim"]) if d["se_clim"] > 0 else None,
            "gain_over_production": float(1 - d["se_map"] / d["se_prod"]) if d["se_prod"] > 0 else None,
            "level_map": float(d["p_map"] / d["y"]) if d["y"] > 0 else None,
            "level_prod": float(d["p_prod"] / d["y"]) if d["y"] > 0 else None}


def measures(rows: pd.DataFrame) -> dict:
    """M1 to M3 at LEADS for scored rows of one arm (statement, section 5), with the pieces reported beside them."""
    from dipcast import scottish_shadow
    g = rows[rows["lead"].isin(LEADS)]
    out: dict = {"leads": list(LEADS), "resamples": RESAMPLES, "seed": SEED, "unit": "overflow-day forecast, resampled by target day"}
    if g.empty:
        return {**out, "status": "too few", "n": 0}
    days = _by_day(g)
    p = _piece(g)
    gate = scottish_shadow.gate_b(g.assign(forecast_calibrated=g["p_map"], arm="map"))["arms"][0]
    prod = scottish_shadow.gate_b(g.assign(forecast_calibrated=g["p_prod"], arm="production"))["arms"][0]
    m1 = {"skill": gate["skill"], "interval_95": gate["interval_95"]}
    m2 = {"level": p["level_map"], "interval_95": _interval(days["p_map"].to_numpy(), days["y"].to_numpy(), "ratio"),
          "band": list(LEVEL_BAND)}
    m3 = {"gain": p["gain_over_production"],
          "interval_95": _interval(days["se_map"].to_numpy(), days["se_prod"].to_numpy(), "skill")}
    enough = p["spill_days"] >= MIN_SPILL_DAYS and p["target_days"] >= MIN_TARGET_DAYS
    m1["holds"] = bool(enough and m1["interval_95"] and m1["interval_95"][0] > 0)
    m2["holds"] = bool(enough and m2["level"] is not None and LEVEL_BAND[0] <= m2["level"] <= LEVEL_BAND[1])
    m3["holds"] = bool(enough and m3["interval_95"] and m3["interval_95"][0] > 0)
    out.update({**p, "status": "read" if enough else "too few", "min_spill_days": MIN_SPILL_DAYS,
                "min_target_days": MIN_TARGET_DAYS, "first_day": str(g["day"].min()), "last_day": str(g["day"].max()),
                "M1_skill_vs_climatology": m1, "M2_level": m2, "M3_gain_over_production": m3,
                "production_on_the_same_rows": {"skill": prod["skill"], "interval_95": prod["interval_95"]}})
    # Reported beside them, not gated.
    month = pd.to_datetime(g["day"]).dt.strftime("%Y-%m")
    wet = np.where(g["rain_mm"].isna(), "rain not logged", np.where(g["rain_mm"] >= WET_MM, f"{WET_MM:g} mm or more", f"under {WET_MM:g} mm"))
    age = np.where(g["rain_age_h"].isna(), "age not logged", np.where(g["rain_age_h"] > OLD_RAIN_H, f"over {OLD_RAIN_H:g} h", f"up to {OLD_RAIN_H:g} h"))
    own = np.where(g["covariates"].astype(str).str.startswith("sw"), "own count", "filled")
    out["by_lead"] = {str(k): _piece(v) for k, v in rows.groupby("lead")}
    for name, by in (("by_month", month), ("by_covariates", own), ("by_target_day_rain", wet), ("by_rain_age", age),
                     ("by_england_calibration", g["cal"].fillna("unknown").to_numpy())):
        out[name] = {str(k): _piece(v) for k, v in g.groupby(np.asarray(by))}
    tenth = np.minimum((g["p_map"].to_numpy(dtype=float) * 10).astype(int), 9)
    out["reliability_by_tenths"] = [{"band": f"{k / 10:.1f}-{(k + 1) / 10:.1f}", "n": len(v), "forecast": float(v["p_map"].mean()),
                                     "observed": float(v["observed"].mean())} for k, v in g.groupby(tenth)]
    return out


def derived_forecasts(existing: pd.DataFrame) -> pd.DataFrame:
    """v1's map applied to the raw chances the existing shadow logged at issue time, for every issue day from
    DERIVED_FROM on (statement, section 6): rows of spill model SPILL_STAMP with rain. Derived, not logged; never
    written to DB."""
    e = existing[(existing["issue_day"] >= DERIVED_FROM) & existing["rain_available"].astype(bool)
                 & existing["version"].map(lambda v: _part(v, "spill") == SPILL_STAMP)].reset_index(drop=True)
    mp = pinned_map()
    return e.assign(p_prod=e["p_cal"], p_map=apply_pinned(e["p_raw"].to_numpy(dtype=float), mp), map_applied=True,
                    arm=f"{ARM};derived")


def read(state: Path | None = None, work: Path | None = None, today: date | None = None, counts_only: bool = False) -> dict:
    """The arm's read (statement, sections 5 to 8). Before READ_NOT_BEFORE, or with `counts_only`, counts alone: no
    outcome is joined. `state` is a copy of the build's state directory; `work` takes the scratch files."""
    state = Path(state) if state else config.STATE
    today = today or pd.Timestamp.now(tz=forecast_log.LOCAL_TZ).date()
    out = {"arm": ARM, "today": str(today), "read_not_before": str(READ_NOT_BEFORE), "window_end": str(WINDOW_END),
           "counts": counts(state)}
    if counts_only or today < READ_NOT_BEFORE:
        out["read"] = "not run: counts only" if counts_only else f"not run: the read is on or after {READ_NOT_BEFORE}"
        return out
    if work is None:
        raise ValueError("the read needs a scratch directory for its copies")
    work = Path(work)
    logged = _logged(state)
    rows = scored(logged, state, work, today, "logged")
    out["logged"] = {str(arm): measures(g) for arm, g in rows.groupby("arm")} if len(rows) else {}
    first = logged["issue_day"].min() if len(logged) else None
    existing = _existing(state, DERIVED_FROM)
    try:
        der = derived_forecasts(existing)
        check = same_issues(logged, existing)
        bad = check.get("p_map_is_not_the_map_of_p_raw", 0) or check.get("p_raw_differs", 0) or "p_map_check" in check
        if bad:
            out["derived"] = {"status": "dropped: the logged rows are not the map of the existing shadow's raw chance", "check": check}
        else:
            d = scored(der, state, work, today, "derived")
            out["derived"] = {"status": "derived, not logged: context only", "from_issue_day": str(DERIVED_FROM),
                              "first_logged_issue_day": str(first) if first else None, "check": check,
                              "full_window": measures(d) if len(d) else {"status": "too few", "n": 0}}
    except (OSError, ValueError) as e:
        out["derived"] = {"status": f"dropped: {e}"}
    return out
