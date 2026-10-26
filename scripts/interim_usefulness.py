"""The interim usefulness read (docs/INTERIM-USEFULNESS-2026-10.md): the published scored live spill
forecasts against three simple references, on the same rows, with the 2027 pre-registration's
two-way bootstrap. The references and the promise rule are stated in the doc, before the run.

1. the long-run rate (the scored file's climatology column);
2. persistence: spilling at issue time, or in the RECENT_SPILL_HOURS before it, read from the poll
   files (live_history.parquet, live_coverage.parquet), one fitted chance for active and one for quiet;
3. the rain rule: forecast rain over the target day and the day before above 10 mm, or 5 mm
   (model.verify.rain_rule's form), from the forecast log's rain_mm, one fitted chance each side.

Off CI, by hand, from the state release (read only; no pipeline run, no Open-Meteo call):

    gh release download state -p dipcast.duckdb -p live_history.parquet -p live_coverage.parquet \\
        -p poll_log.parquet -D /tmp/s
    curl -sLO https://swimsignal.co.uk/data/verification_live.csv
    uv run python scripts/interim_usefulness.py --scored verification_live.csv --state /tmp/s \\
        --out docs/INTERIM-USEFULNESS-2026-10.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_2027 import Bootstrap, auc, read_published, sha256  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ, MAX_GAP_H, load_coverage  # noqa: E402
from dipcast.model.live_status import SLOT_H, _merge, poll_events  # noqa: E402

FIRST_DAY = date(2026, 9, 29)
BLOCK_DAYS = 7               # blocks from FIRST_DAY: 29 Sep-5 Oct, 6-12 Oct, ...
RESAMPLES = 2000
SEED = 20270501              # the pre-registration's seed (section 10)
RECENT_H = config.RECENT_SPILL_HOURS
RAIN_RULES = {"rain10": 10.0, "rain5": 5.0}
REFS = ["clim", "persistence", "rain10", "rain5"]
LEAD_GROUPS = {"0": (0,), "1-4": (1, 2, 3, 4), "1": (1,), "2": (2,), "3": (3,), "4": (4,)}

# Every logged overflow row in the window, for the day-before rain; the decision rows are picked from these.
SQL = f"""
    SELECT site_id, issue_day, target_day, lead, epoch_ms(issued_at) AS issued_ms, rain_mm, spilling_at_issue,
           has_live, coalesce(rain_available, TRUE) AS rain_ok,
           (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR) AS before_cutoff
    FROM forecast_overflows WHERE target_day BETWEEN ? AND ?
"""


def block_of(days: pd.Series) -> np.ndarray:
    return np.floor_divide((pd.to_datetime(days) - pd.Timestamp(FIRST_DAY)).dt.days.to_numpy(), BLOCK_DAYS)


def decision_rows(log: pd.DataFrame) -> pd.DataFrame:
    """forecast_log.select_decision_forecasts' pick: per overflow, issue day and target day, the latest
    issued by DECISION_HOUR, live-fed, rain present (only rows before the cutoff are scored)."""
    f = log[log["has_live"] & log["rain_ok"] & log["before_cutoff"]]
    f = f.sort_values(["site_id", "issue_day", "target_day", "issued_ms"], kind="mergesort")
    return f.drop_duplicates(["site_id", "issue_day", "target_day"], keep="last")


def rain_48h(rows: pd.DataFrame, log: pd.DataFrame) -> pd.Series:
    """rain_mm for the target day plus rain_mm for the day before: from the same issue for leads 1-4,
    and for lead 0 from the latest logged forecast of that overflow for the day before issued before it."""
    prev = rows["target_day"] - pd.Timedelta(days=1)
    same = log.dropna(subset=["rain_mm"]).drop_duplicates(["site_id", "issued_ms", "target_day"])
    key = same.set_index(["site_id", "issued_ms", "target_day"])["rain_mm"]
    d1 = pd.Series(key.reindex(pd.MultiIndex.from_arrays([rows["site_id"], rows["issued_ms"], prev])).to_numpy(),
                   index=rows.index)
    z = rows["lead"] == 0
    if z.any():
        q = pd.DataFrame({"site_id": rows.loc[z, "site_id"], "target_day": prev[z],
                          "issued_ms": rows.loc[z, "issued_ms"] - 1, "_i": rows.index[z]}).sort_values("issued_ms")
        ref = same[["site_id", "target_day", "issued_ms", "rain_mm"]].sort_values("issued_ms")
        m = pd.merge_asof(q, ref, on="issued_ms", by=["site_id", "target_day"], direction="backward")
        d1.loc[m["_i"].to_numpy()] = m["rain_mm"].to_numpy()
    return rows["rain_mm"] + d1


def poll_readings(cov: pd.DataFrame, polls: pd.DataFrame, company: pd.Series, first: date, last: date) -> pd.DataFrame:
    """(site_id, t): each poll of the overflow's company (poll_log.parquet's fetched_at) whose half-hour slot
    in live_coverage.parquet holds a current reading of the overflow. The poll's own time, not the slot's
    middle (live_status.reading_times), so the poll a build makes minutes before it issues is not placed
    after the issue."""
    t = pd.to_datetime(polls["fetched_at"], utc=True)
    wall = t.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    p = pd.DataFrame({"company": polls["company"].to_numpy(), "t": t, "day": wall.dt.date,
                      "slot": ((wall - wall.dt.floor("D")).dt.total_seconds() // (SLOT_H * 3600)).astype(int)})
    p = p[(p["day"] >= first) & (p["day"] <= last)].drop_duplicates(["company", "t"])
    c = cov[(cov["day"] >= first) & (cov["day"] <= last)][["site_id", "day", "slots"]].astype({"site_id": str})
    c = c.assign(company=c["site_id"].map(company)).dropna(subset=["company"])
    m = c.merge(p, on=["company", "day"])
    seen = (m["slots"].to_numpy(dtype=np.int64) >> m["slot"].to_numpy(dtype=np.int64)) & 1
    return m.loc[seen.astype(bool), ["site_id", "t"]]


def persistence_status(rows: pd.DataFrame, history: pd.DataFrame, cov: pd.DataFrame, polls: pd.DataFrame) -> pd.DataFrame:
    """Per row: known (readings over the RECENT_H before issue with no stretch over MAX_GAP_H, the stretch
    to the issue time included), active (a merged spill interval that had started by the last reading
    at or before issue and had not ended RECENT_H before it) and spilling_now (one still running at issue)."""
    T = pd.to_datetime(rows["issued_ms"], unit="ms", utc=True)
    first = (T.min() - pd.Timedelta(hours=RECENT_H)).tz_convert(LOCAL_TZ).date() - timedelta(days=1)
    h = history.assign(site_id=history["site_id"].astype(str))
    company = h.drop_duplicates("site_id", keep="last").set_index("site_id")["company"]
    rt = poll_readings(cov, polls, company, first, T.max().tz_convert(LOCAL_TZ).date())
    rd = {s: np.sort(g["t"].to_numpy(dtype="datetime64[ns]").astype(np.int64)) for s, g in rt.groupby("site_id")}
    ev = _merge(poll_events(history))
    ivs = {s: (g["start"].to_numpy(dtype="datetime64[ns]").astype(np.int64),
               g["end"].to_numpy(dtype="datetime64[ns]").astype(np.int64)) for s, g in ev.groupby("site_id")}
    t_ns = T.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    win, gap = int(RECENT_H * 3600e9), MAX_GAP_H * 3600e9
    known = np.zeros(len(rows), bool)
    active = np.zeros(len(rows), bool)
    now = np.zeros(len(rows), bool)
    for s, idx in rows.groupby("site_id").indices.items():
        r = rd.get(s)
        if r is None or not len(r):
            continue
        st, en = ivs.get(s, (np.zeros(0, np.int64), np.zeros(0, np.int64)))
        for i in idx:
            t = t_ns[i]
            hi = np.searchsorted(r, t, side="right")
            if hi == 0:
                continue
            lo = np.searchsorted(r, t - win, side="right") - 1
            pts = r[max(lo, 0):hi]
            if lo < 0:
                pts = np.concatenate([[t - win], pts])
            pts = np.concatenate([pts, [t]])
            known[i] = np.diff(pts).max() <= gap
            last = r[hi - 1]
            j = np.searchsorted(st, last, side="right") - 1
            if j >= 0:
                active[i] = en[j] >= t - win
                now[i] = en[j] >= t
    return pd.DataFrame({"known": known, "active": active, "spilling_now": now}, index=rows.index)


def fit_two_sided(y: np.ndarray, side: np.ndarray, lead: np.ndarray, ok: np.ndarray) -> tuple[np.ndarray, dict]:
    """Each side's observed spill rate, at each lead, over the rows where the reference exists."""
    p = np.full(len(y), np.nan)
    fitted = {}
    for k in np.unique(lead):
        for s in (True, False):
            m = ok & (lead == k) & (side == s)
            rate = float(y[m].mean()) if m.any() else float("nan")
            p[m] = rate
            fitted[f"lead{k}_{'on' if s else 'off'}"] = {"rows": int(m.sum()), "chance": rate}
    return p, fitted


class Cell:
    """One cell's rows with their per-row terms, so every draw is a few weighted sums."""

    def __init__(self, df: pd.DataFrame, rows: np.ndarray, refs: list[str]):
        g = df.iloc[rows]
        self.rows = rows
        self.y = g["y"].to_numpy(float)
        self.se = (g["p"].to_numpy(float) - self.y) ** 2
        self.se_ref = {k: (g[k].to_numpy(float) - self.y) ** 2 for k in refs}
        _, self.vidx = np.unique(g["p"].to_numpy(float), return_inverse=True)
        self.nv = int(self.vidx.max()) + 1 if len(rows) else 0

    def stats(self, w: np.ndarray) -> dict:
        sw = w.sum()
        if sw <= 0 or np.dot(w, self.y) <= 0:
            return {}
        b = np.dot(w, self.se) / sw
        refb = {k: np.dot(w, se) / sw for k, se in self.se_ref.items()}
        out = {f"skill_{k}": 1 - b / v if v > 0 else np.nan for k, v in refb.items()}
        if len(refb) > 1:
            best = min(refb, key=refb.get)
            out["skill_best"] = 1 - b / refb[best] if refb[best] > 0 else np.nan
            out["best_ref"] = best
        out["auc"] = auc(self.y.astype(bool), None, w, self.vidx, self.nv)
        return out


def describe(df: pd.DataFrame, rows: np.ndarray, refs: list[str], boot: Bootstrap) -> dict:
    g = df.iloc[rows]
    spill = g[g["y"] == 1]
    out = {"rows": len(g), "overflows": int(g["overflow_id"].nunique()), "spill_rows": len(spill),
           "spill_overflow_days": int(spill[["overflow_id", "day"]].drop_duplicates().shape[0]),
           "observed_rate": float(g["y"].mean()) if len(g) else None,
           "mean_forecast": float(g["p"].mean()) if len(g) else None}
    if not len(g) or not len(spill):
        return out
    c = Cell(df, rows, refs)
    point = c.stats(np.ones(len(rows)))
    out.update(point)
    out["brier"] = float(np.mean(c.se))
    out.update({f"brier_{k}": float(np.mean(se)) for k, se in c.se_ref.items()})
    out.update({f"auc_{k}": auc(c.y.astype(bool), g[k].to_numpy(float)) for k in refs})
    keys = [k for k in point if k != "best_ref"]
    reps = {k: [] for k in keys}
    for r in range(len(boot.draws)):
        st = c.stats(boot.weights(r, rows))
        for k in keys:
            reps[k].append(st.get(k, np.nan))
    ci = {}
    for k, v in reps.items():
        a = np.asarray(v, float)
        ok = a[~np.isnan(a)]
        ci[k] = {"lo": float(np.percentile(ok, 2.5)) if len(ok) else None,
                 "hi": float(np.percentile(ok, 97.5)) if len(ok) else None, "undefined_draws": int(len(a) - len(ok))}
    out["ci"] = ci
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path, help="folder with dipcast.duckdb and the three poll files")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--resamples", type=int, default=RESAMPLES)
    a = ap.parse_args()

    sc = read_published(a.scored)
    sc = sc[sc["day"] >= str(FIRST_DAY)].reset_index(drop=True)
    first, last = sc["day"].min(), sc["day"].max()
    con = duckdb.connect(str(a.state / "dipcast.duckdb"), read_only=True)
    try:
        log = con.execute(SQL, [str(date.fromisoformat(first) - timedelta(days=1)), last]).df()
    finally:
        con.close()
    log["site_id"] = log["site_id"].astype(str)
    log["target_day"] = pd.to_datetime(log["target_day"])
    dec = decision_rows(log)
    dec = dec.assign(day=dec["target_day"].dt.strftime("%Y-%m-%d"))
    df = sc.merge(dec[["site_id", "day", "lead", "issued_ms", "target_day", "rain_mm", "spilling_at_issue"]],
                  left_on=["overflow_id", "day", "lead"], right_on=["site_id", "day", "lead"], how="left")
    issued_min = pd.to_datetime(df["issued_ms"], unit="ms", utc=True).dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%dT%H:%M%:z")
    joined = df["issued_ms"].notna()
    match = joined & (issued_min == df["issued_at"])
    df["y"], df["p"], df["clim"] = df["observed"].astype(float), df["forecast_calibrated"], df["climatology"]
    lead = df["lead"].to_numpy()
    y = df["y"].to_numpy()

    # Rain rule.
    j = df[match].copy()
    j = j.assign(site_id=j["site_id"].astype(str), issued_ms=j["issued_ms"].astype(np.int64))
    df["rain48"] = np.nan
    df.loc[match, "rain48"] = rain_48h(j, log).to_numpy()
    rain_ok = df["rain48"].notna().to_numpy()
    fitted = {}
    for name, mm in RAIN_RULES.items():
        df[name], fitted[name] = fit_two_sided(y, df["rain48"].to_numpy() > mm, lead, rain_ok)

    # Persistence.
    hist = pd.read_parquet(a.state / "live_history.parquet")
    cov = load_coverage(a.state / "live_coverage.parquet")
    polls = pd.read_parquet(a.state / "poll_log.parquet")
    ps = persistence_status(j, hist, cov, polls)
    for c in ps:
        df[c] = False
        df.loc[ps.index, c] = ps[c].to_numpy()
    known = df["known"].to_numpy(bool)
    df["persistence"], fitted["persistence"] = fit_two_sided(y, df["active"].to_numpy(bool), lead, known)

    common = known & rain_ok
    boot = Bootstrap(df["overflow_id"].to_numpy(), block_of(df["day"]), a.resamples, SEED)
    companies = ["All companies", *sorted(df["company"].dropna().unique())]
    results = []
    for comp in companies:
        cm = np.ones(len(df), bool) if comp == "All companies" else (df["company"] == comp).to_numpy()
        for lg, leads in LEAD_GROUPS.items():
            lm = np.isin(lead, leads)
            res = {"company": comp, "leads": lg,
                   "common": describe(df, np.flatnonzero(cm & lm & common), REFS, boot),
                   "all_rows_clim": describe(df, np.flatnonzero(cm & lm), ["clim"], boot)}
            if lg == "1-4":
                lo = res["common"].get("ci", {}).get("skill_best", {}).get("lo")
                res["promise"] = "warns in advance" if lo is not None and lo > 0 else "still being tested"
            results.append(res)
            print(comp, lg, res["common"].get("skill_best"), res["common"].get("ci", {}).get("skill_best"), flush=True)

    cov_rows = []
    for comp in companies:
        cm = np.ones(len(df), bool) if comp == "All companies" else (df["company"] == comp).to_numpy()
        cov_rows.append({"company": comp, "rows": int(cm.sum()), "joined_to_log": int((cm & match).sum()),
                         "status_known": int((cm & known).sum()), "rain_both_days": int((cm & rain_ok).sum()),
                         "common": int((cm & common).sum())})
    blocks = []
    b = block_of(df["day"])
    for k in np.unique(b):
        m = b == k
        g = df[m]
        blocks.append({"from": g["day"].min(), "to": g["day"].max(), "rows": int(m.sum()), "spill_rows": int(g["y"].sum()),
                       "spill_overflow_days": int(g[g["y"] == 1][["overflow_id", "day"]].drop_duplicates().shape[0])})
    # Cross-check of the rebuilt status against the shadow's own spilling_at_issue (logged from 20 Oct).
    # The shadow logs what the poll at issue said; the rebuild uses event times as the feeds later gave them.
    sh = df[df["spilling_at_issue"].notna() & df["known"]]
    on = sh["spilling_at_issue"] > 0
    check = {"rows": len(sh), "shadow_spilling": int(on.sum()), "of_which_rebuilt_active": int((on & sh["active"]).sum()),
             "of_which_rebuilt_spilling_now": int((on & sh["spilling_now"]).sum()),
             "rebuilt_spilling_now_shadow_not": int((~on & sh["spilling_now"]).sum()),
             "rebuilt_active": int(sh["active"].sum())}
    out = {"inputs": {"scored": {"file": a.scored.name, "sha256": sha256(a.scored), "rows": len(sc), "first_day": first,
                                 "last_day": last},
                      **{f: sha256(a.state / f) for f in ("dipcast.duckdb", "live_history.parquet", "live_coverage.parquet", "poll_log.parquet")}},
           "settings": {"resamples": a.resamples, "seed": SEED, "block_days": BLOCK_DAYS, "first_block_day": str(FIRST_DAY),
                        "recent_spill_hours": RECENT_H, "max_gap_h": MAX_GAP_H, "rain_rules_mm": RAIN_RULES},
           "join": {"rows": len(df), "joined": int(joined.sum()), "issue_time_matches": int(match.sum())},
           "coverage": cov_rows, "blocks": blocks, "fitted_chances": fitted, "status_check_vs_shadow": check,
           "bootstrap": {"overflows": len(boot.site_codes), "blocks": len(boot.block_codes)},
           "results": results}
    text = json.dumps(out, indent=1, default=float)
    if a.out:
        a.out.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
