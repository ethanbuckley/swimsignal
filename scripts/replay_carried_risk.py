"""Retrospective, pre-specified check: carry right now's spills onto later days (docs/CARRY-SPILL-WATER-CHECK-2026-11-05.md).

For each spot-day cell the Accuracy page scores (forecast_log.verify_spots) at leads 1-4, it replays the issuing
build's live state from live_history.parquet, recomputes right now's risk (transport.live_now_risk) to check the
replay against the logged now_risk, and scores the candidate max(logged forecast, transport.carried_risk at 12:00
Europe/London on the target day) against the logged forecast, on the observed index.

Reads only scratch copies of the state release. Run with DIPCAST_ROOT, DIPCAST_STATE and DIPCAST_CACHE set to scratch
directories; the script refuses to run when DIPCAST_STATE is unset, because verify_spots writes its CSV there and
forecast_log._conn adds columns to the DuckDB file it opens. No network calls.

    DIPCAST_ROOT=$PWD DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<scratch>/cache \
        PYTHONPATH=src python scripts/replay_carried_risk.py --as-of 2026-11-05 --out <scratch>/out
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

if not os.environ.get("DIPCAST_STATE") or not os.environ.get("DIPCAST_ROOT"):
    sys.exit("Set DIPCAST_ROOT and a scratch DIPCAST_STATE (and DIPCAST_CACHE) before running: this writes to state.")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from dipcast import config, forecast_log as fl  # noqa: E402
from dipcast.model import transport  # noqa: E402

LOCAL_TZ = fl.LOCAL_TZ
LEADS = (1, 2, 3, 4)
CARRY_HOUR = 12                 # local clock time on the target day the carry is read at
T90_SWITCH = "b84cc771"         # the commit that moved T90_HOURS from 30 to 72 (PR #248, 17 Oct 2026)
T90_OLD, T90_NEW = 30.0, 72.0
MSE_MARGIN = 0.05               # candidate MSE may be at most 5% (relative) worse than the baseline's
MIN_AFFECTED = 30
BOOT_DRAWS, BOOT_SEED = 2000, 20261105


def as_of_state(hist: pd.DataFrame) -> dict[str, tuple[np.ndarray, pd.DataFrame]]:
    """Per site, its history rows sorted by when each began: status_start, else the event's start (status 1) or end
    (status 0), else fetched_at. The state at T is the row with the largest begin <= T."""
    h = hist.copy()
    h["site_id"] = h["site_id"].astype(str)
    begin = h["status_start"]
    begin = begin.fillna(h["latest_event_start"].where(h["status"].eq(1)))
    begin = begin.fillna(h["latest_event_end"].where(h["status"].eq(0)))
    h["begin"] = begin.fillna(h["fetched_at"])
    h = h.sort_values(["site_id", "begin", "fetched_at"], kind="mergesort")
    out = {}
    for sid, g in h.groupby("site_id", sort=False):
        out[sid] = (g["begin"].to_numpy(dtype="datetime64[us]").astype("int64"),
                    g[["status", "latest_event_start", "latest_event_end"]].reset_index(drop=True))
    return out


def live_at(state: dict, site_ids: np.ndarray, t: pd.Timestamp) -> pd.DataFrame:
    """status, latest_event_start and latest_event_end for each site as of t (NaN/NaT where nothing was known)."""
    tt = np.int64(t.tz_convert("UTC").value // 1000)
    rows = []
    for sid in site_ids:
        s = state.get(str(sid))
        if s is None:
            rows.append((np.nan, pd.NaT, pd.NaT))
            continue
        i = int(np.searchsorted(s[0], tt, side="right")) - 1
        if i < 0:
            rows.append((np.nan, pd.NaT, pd.NaT))
            continue
        r = s[1].iloc[i]
        rows.append((float(r["status"]), r["latest_event_start"], r["latest_event_end"]))
    df = pd.DataFrame(rows, columns=["status", "latest_event_start", "latest_event_end"])
    for c in ("latest_event_start", "latest_event_end"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def t90_by_commit(versions: pd.Series) -> dict[str, float]:
    """The T90 in force at each logged code commit: 72 h from T90_SWITCH on, 30 h before. Unknown -> NaN."""
    out = {}
    for v in versions.dropna().unique():
        c = str(v).split("code=")[-1].split(";")[0].split("+")[-1] if "code=" in str(v) else ""
        if not c or c in out:
            out.setdefault(v, np.nan)
            continue
        r = subprocess.run(["git", "merge-base", "--is-ancestor", T90_SWITCH, c], cwd=config.ROOT,
                           capture_output=True)
        out[v] = T90_NEW if r.returncode == 0 else (T90_OLD if r.returncode == 1 else np.nan)
    return out


def guard(fc: np.ndarray, ob: np.ndarray) -> dict:
    f, o = fl.spot_levels(fc) >= fl.SPOT_HIGH, fl.spot_levels(ob) >= fl.SPOT_HIGH
    return {"n": int(len(f)), "hits": int((f & o).sum()), "misses": int((~f & o).sum()),
            "false_alarms": int((f & ~o).sum()), "quiet_correct": int((~f & ~o).sum())}


def primary(d: pd.DataFrame, cand: str, rng_seed: int = BOOT_SEED) -> dict:
    """MSE and exact level agreement for baseline and candidate on `d`, with a spot-cluster bootstrap of the
    MSE difference (candidate minus baseline)."""
    b, c, o = d["forecast"].to_numpy(), d[cand].to_numpy(), d["observed"].to_numpy()
    se_b, se_c = (b - o) ** 2, (c - o) ** 2
    lv_o = fl.spot_levels(o)
    agree_b, agree_c = fl.spot_levels(b) == lv_o, fl.spot_levels(c) == lv_o
    out = {"n_cells": int(len(d)), "n_spots": int(d["spot_id"].nunique()),
           "mse_baseline": float(se_b.mean()) if len(d) else None, "mse_candidate": float(se_c.mean()) if len(d) else None,
           "level_agree_baseline": int(agree_b.sum()), "level_agree_candidate": int(agree_c.sum())}
    if len(d):
        out["mse_diff"] = out["mse_candidate"] - out["mse_baseline"]
        out["mse_rel_change"] = out["mse_diff"] / out["mse_baseline"] if out["mse_baseline"] > 0 else None
        spots = d["spot_id"].to_numpy()
        ids, inv = np.unique(spots, return_inverse=True)
        sb = np.bincount(inv, weights=se_b, minlength=len(ids))
        sc = np.bincount(inv, weights=se_c, minlength=len(ids))
        n = np.bincount(inv, minlength=len(ids)).astype(float)
        rng = np.random.default_rng(rng_seed)
        diffs = np.empty(BOOT_DRAWS)
        for k in range(BOOT_DRAWS):
            pick = np.bincount(rng.integers(0, len(ids), len(ids)), minlength=len(ids))
            m = (pick * n).sum()
            diffs[k] = ((pick * sc).sum() - (pick * sb).sum()) / m
        out["mse_diff_ci95"] = [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]
    return out


def decide(p: dict, g_base: dict, g_cand: dict) -> str:
    if p["n_cells"] < MIN_AFFECTED:
        return "TOO FEW TO JUDGE"
    mse_ok = p["mse_candidate"] <= p["mse_baseline"] * (1 + MSE_MARGIN)
    agree_ok = p["level_agree_candidate"] >= p["level_agree_baseline"]
    fa_ok = (g_cand["false_alarms"] - g_base["false_alarms"]) <= (g_cand["hits"] - g_base["hits"])
    return "SUPPORTED" if (mse_ok and agree_ok and fa_ok) else "NOT SUPPORTED"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=str(date.today()))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    as_of = date.fromisoformat(a.as_of)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. The cells the Accuracy page scores, exactly as verify_spots makes them.
    summary = fl.verify_spots(as_of=as_of)
    rows = pd.read_csv(config.STATE / fl.SPOTS_CSV)
    scored = rows[rows["lead"].isin(LEADS) & rows["forecast"].notna() & rows["observed"].notna()].copy()
    scored["day"] = pd.to_datetime(scored["day"]).dt.date

    # 2. Each scored cell's issuing forecast: the same choice verify_spots makes (latest by 08:00 local).
    con = fl._conn()
    try:
        first = con.execute("SELECT min(issue_day) FROM forecast_overflows WHERE travel_h IS NOT NULL").fetchone()[0]
        pts = fl._decision_points(con, first, as_of)
        spots = fl.spot_list()
        key = pts["lat"].round(4).astype(str) + "," + pts["lon"].round(4).astype(str)
        sk = spots.assign(k=spots["lat"].round(4).astype(str) + "," + spots["lon"].round(4).astype(str))
        pts["spot_id"] = key.map(sk.drop_duplicates("k").set_index("k")["id"])
        pts = pts.dropna(subset=["spot_id"])
        chosen = (pts[pts["before_cutoff"]].sort_values("issued_ms", kind="mergesort")
                  .drop_duplicates(["spot_id", "target_day", "lead"], keep="last"))
        cells = scored.merge(chosen.rename(columns={"target_day": "day", "risk": "risk_logged", "version": "version_logged"}),
                             on=["spot_id", "day", "lead"], how="left", validate="one_to_one")
        issued = pd.to_datetime(cells["issued_ms"], unit="ms", utc=True).dt.tz_convert(LOCAL_TZ)
        same_issue = issued.dt.strftime("%Y-%m-%dT%H:%M%:z") == cells["issued_at"]
        assert same_issue.all(), f"{(~same_issue).sum()} cells' issue does not match verify_spots'"
        issues = cells[["issued_ms", "lat", "lon"]].drop_duplicates().reset_index(drop=True)
        con.register("issues", issues)
        now_logged = con.execute("""
            SELECT k.issued_ms, k.lat, k.lon, any_value(p.now_risk) AS now_risk_logged,
                   count(DISTINCT p.now_risk) AS n_now
            FROM issues k JOIN forecast_points p
              ON epoch_ms(p.issued_at) = k.issued_ms AND p.lat = k.lat AND p.lon = k.lon
            GROUP BY ALL""").df()
        # The issue's overflow list as the forecast held it: every row it logged for its smallest lead.
        ovs = con.execute("""
            WITH o AS (SELECT epoch_ms(o.issued_at) AS issued_ms, o.lat, o.lon, o.lead, o.site_id, o.weight,
                              o.travel_h, o.has_live
                       FROM forecast_overflows o JOIN issues k
                         ON epoch_ms(o.issued_at) = k.issued_ms AND o.lat = k.lat AND o.lon = k.lon)
            SELECT o.* FROM o JOIN (SELECT issued_ms, lat, lon, min(lead) AS lead FROM o GROUP BY ALL) m
              USING (issued_ms, lat, lon, lead)""").df()
        con.unregister("issues")
    finally:
        con.close()
    assert (now_logged["n_now"] == 1).all()
    cells = cells.merge(now_logged.drop(columns="n_now"), on=["issued_ms", "lat", "lon"], how="left")
    t90_of = t90_by_commit(cells["version_logged"])
    cells["t90_in_force"] = cells["version_logged"].map(t90_of)

    # 3. Replay each issue's live state and right now's risk; the carry at 12:00 local on each target day.
    hist = pd.read_parquet(config.state_read("live_history.parquet"))
    state = as_of_state(hist)
    by_issue = {k: g for k, g in ovs.groupby(["issued_ms", "lat", "lon"])}
    rep = []
    for (ims, lat, lon), g in cells.groupby(["issued_ms", "lat", "lon"]):
        now = pd.Timestamp(int(ims), unit="ms", tz="UTC")
        o = by_issue.get((ims, lat, lon))
        t90 = float(g["t90_in_force"].iloc[0])
        t90 = T90_NEW if np.isnan(t90) else t90
        if o is None or o.empty:
            ov = pd.DataFrame(columns=["site_id", "weight", "travel_h", "status", "latest_event_start", "latest_event_end"])
        else:
            o = o.reset_index(drop=True)
            ov = pd.concat([o[["site_id", "weight", "travel_h"]], live_at(state, o["site_id"].to_numpy(), now)], axis=1)
        now_rep = transport.live_now_risk(ov, now, t90_h=t90)[0] if len(ov) else 0.0
        now_rep72 = transport.live_now_risk(ov, now, t90_h=T90_NEW)[0] if len(ov) else 0.0
        at = [pd.Timestamp(d).tz_localize(LOCAL_TZ) + pd.Timedelta(hours=CARRY_HOUR) for d in g["day"]]
        c72 = transport.carried_risk(ov, now, at, t90_h=T90_NEW) if len(ov) else [0.0] * len(at)
        cin = transport.carried_risk(ov, now, at, t90_h=t90) if len(ov) else [0.0] * len(at)
        for idx, x72, xin in zip(g.index, c72, cin):
            rep.append((idx, now_rep, now_rep72, x72, xin, len(ov)))
    r = pd.DataFrame(rep, columns=["idx", "now_replay", "now_replay_t90_72", "carried", "carried_t90_in_force",
                                   "n_overflows"]).set_index("idx")
    cells = cells.join(r)

    # 4. The replay check: replayed right now against the logged one, per issue.
    iss = cells.drop_duplicates(["issued_ms", "lat", "lon"])
    lv_l, lv_r = fl.spot_levels(iss["now_risk_logged"]), fl.spot_levels(iss["now_replay"])
    diff = (iss["now_replay"] - iss["now_risk_logged"]).abs()
    replay = {"n_issues": int(len(iss)), "level_match": int((lv_l == lv_r).sum()),
              "level_match_rate": float((lv_l == lv_r).mean()),
              "within_0.001": int((diff <= 0.001).sum()), "within_0.001_rate": float((diff <= 0.001).mean()),
              "level_match_rate_t90_72": float((fl.spot_levels(iss["now_replay_t90_72"]) == lv_l).mean()),
              "issues_logged_at_or_above_cut": int((iss["now_risk_logged"] >= transport.CLEAR_CUT).sum()),
              "issues_replayed_at_or_above_cut": int((iss["now_replay"] >= transport.CLEAR_CUT).sum()),
              "issues_t90_30": int((iss["t90_in_force"] == T90_OLD).sum()),
              "issues_t90_unknown": int(iss["t90_in_force"].isna().sum())}
    hi = iss["now_risk_logged"] >= transport.CLEAR_CUT
    replay["level_match_rate_logged_at_or_above_cut"] = float((lv_l[hi.to_numpy()] == lv_r[hi.to_numpy()]).mean()) if hi.any() else None
    replay["confusion_logged_vs_replayed"] = pd.crosstab(pd.Series(lv_l, name="logged"),
                                                         pd.Series(lv_r, name="replayed")).to_dict()

    # 5. Score. Candidate values as the CSV would publish them (6 dp), like the baseline.
    cells["candidate"] = fl.as_published(np.maximum(cells["forecast"], cells["carried"]))
    cells["candidate_t90_in_force"] = fl.as_published(np.maximum(cells["forecast"], cells["carried_t90_in_force"]))
    cells["affected"] = cells["now_risk_logged"] >= transport.CLEAR_CUT
    aff = cells[cells["affected"]]
    res = {"as_of": str(as_of), "first_day": summary.get("first_day"), "last_day": summary.get("last_day"),
           "n_scored_lead1_4": int(len(cells)), "n_spots_lead1_4": int(cells["spot_id"].nunique()),
           "n_affected": int(len(aff)), "n_affected_spots": int(aff["spot_id"].nunique()),
           "n_affected_by_replayed_now": int((cells["now_replay"] >= transport.CLEAR_CUT).sum()),
           "n_changed": int((cells["candidate"] > cells["forecast"]).sum()),
           "n_level_changed": int((fl.spot_levels(cells["candidate"]) != fl.spot_levels(cells["forecast"])).sum()),
           "replay": replay,
           "primary": primary(aff, "candidate"),
           "guard_baseline": guard(cells["forecast"].to_numpy(), cells["observed"].to_numpy()),
           "guard_candidate": guard(cells["candidate"].to_numpy(), cells["observed"].to_numpy()),
           "sensitivity_t90_in_force": {
               "primary": primary(aff, "candidate_t90_in_force"),
               "guard_candidate": guard(cells["candidate_t90_in_force"].to_numpy(), cells["observed"].to_numpy())},
           "by_lead": {int(ld): {**primary(g, "candidate"),
                                 "guard_baseline": guard(g["forecast"].to_numpy(), g["observed"].to_numpy()),
                                 "guard_candidate": guard(g["candidate"].to_numpy(), g["observed"].to_numpy())}
                       for ld, g in aff.groupby("lead")}}
    res["decision"] = decide(res["primary"], res["guard_baseline"], res["guard_candidate"])
    res["sensitivity_t90_in_force"]["decision"] = decide(res["sensitivity_t90_in_force"]["primary"], res["guard_baseline"],
                                                         res["sensitivity_t90_in_force"]["guard_candidate"])
    # The published summary, for checking the reproduction of the scored cells.
    res["published_in_advance"] = {k: summary.get("in_advance", {}).get(k) for k in ("n", "hits", "misses", "false_alarms")}
    cells.drop(columns=["before_cutoff"], errors="ignore").to_csv(out_dir / "carry_cells.csv", index=False)
    (out_dir / "carry_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
