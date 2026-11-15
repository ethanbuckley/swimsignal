"""docs/RADAR-PLUS-STATUS-TEST-2026-11.md: #694's radar-to-the-issue-hour test with the overflow's live spill status,
as it stood at the issue instant, added to both the radar arms and the forecast arms.

    score.py <cell radar dir> <radar_publish_times.csv> <out dir>

#694's code (scripts/radar_issue_hour_eval/score.py) is imported and not edited: the rows, the hourly rain, the arms,
the folds, the bootstrap and the verdict all come from it. #254's merged events and known-status rule come from
scripts/live_status_test.py. This file adds the three status inputs at an instant and the arms that take them.
Writes <out dir>/score.json (summary figures only). RADAR_PLUS_STATUS_PLUMBING=1 runs the harness on 300 overflows
with random labels and prints no score.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import live_status_test as ls
import radar_issue_hour_eval.score as r
from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model import spill_model as sm
from dipcast.model.features import ALL_FEATURES, MONOTONE, build_site_days, daily_rain_features, spill_days
from dipcast.model.spill_model import SpillModel
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years

STATUS = ["spilling_at_issue", "spill_hours_24h", "spill_days_7d"]
FEATS = list(ALL_FEATURES) + STATUS
HOURS = r.HOURS
DAY_S = 86_400
BIG = 4.0e9                 # seconds; |time from 2024-01-01| is under BIG / 2 for every event read
PLUMBING = os.environ.get("RADAR_PLUS_STATUS_PLUMBING") == "1"
T0 = time.time()

# More of each status input can only raise the risk, as in #254 (live_status_test.stage_run).
sm.MONOTONE = {**MONOTONE, **{f: 1 for f in STATUS}}


def log(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    print(f"[{time.time() - T0:7.1f} s, peak {rss:4.1f} GB] {msg}", flush=True)


# ------------------------------------------------------------------ status at an instant
class InstantStatus:
    """#254's three inputs at any instant, from merged events (live_status_test.merged_intervals, seconds from
    live_status_test.DAY0). `known(i, daynum)` says whether an overflow's status is known on a day (days from DAY0);
    None means always known."""

    def __init__(self, events: pd.DataFrame, sites, known=None):
        self.sites = pd.Index(sorted(set(sites)))
        ev = events[events["site_id"].isin(self.sites)]
        iv = ls.merged_intervals(ev, self.sites)
        i, s, e = iv["i"].to_numpy(), iv["s"].to_numpy(), iv["e"].to_numpy()
        e = np.maximum(e, s)                                             # an end before its start spills nothing
        key = i * BIG + s
        assert (np.abs(s) < BIG / 2).all() and (np.diff(key) > 0).all(), "intervals not sorted by overflow and start"
        dur = e - s
        cum = np.cumsum(dur)
        first = np.r_[True, i[1:] != i[:-1]]
        base = np.maximum.accumulate(np.where(first, cum - dur, 0.0))   # cum before each overflow's first interval
        self.i, self.s, self.e, self.key = i, s, e, key
        self.before = cum - dur - base                                   # spilled seconds before interval j, same overflow
        sd = spill_days(ev)
        si = self.sites.get_indexer(sd["site_id"])
        dn = ((sd["day"] - ls.DAY0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        self.sday = np.sort(si * 1_000_000 + dn + 500_000)
        self.known = known
        self.n_intervals = len(iv)

    def _last(self, i: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        j = np.searchsorted(self.key, i * BIG + x, side="right") - 1
        ok = (j >= 0) & (self.i[np.clip(j, 0, None)] == i)
        return np.clip(j, 0, None), ok

    def _spilled_before(self, i, x):
        j, ok = self._last(i, x)
        return np.where(ok, self.before[j] + np.clip(np.minimum(x, self.e[j]) - self.s[j], 0, None), 0.0)

    def _days(self, i, d0, d1):
        """spill-days of overflow i among days d0 .. d1 - 1 (days from DAY0)."""
        lo = np.searchsorted(self.sday, i * 1_000_000 + d0 + 500_000, side="left")
        hi = np.searchsorted(self.sday, i * 1_000_000 + d1 + 500_000, side="left")
        return (hi - lo).astype(float)

    def features(self, site_id: pd.Series, day: pd.Series, hour: int) -> pd.DataFrame:
        i = self.sites.get_indexer(site_id)
        assert (i >= 0).all(), "a row's overflow has no status"
        d = ((day - ls.DAY0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        t = d * float(DAY_S) + hour * 3600.0
        j, ok = self._last(i, t)
        now = (ok & (self.e[j] > t)).astype(float)
        h24 = np.minimum((self._spilled_before(i, t) - self._spilled_before(i, t - DAY_S)) / 3600.0, 24.0)
        d7 = self._days(i, d - 7, d)
        if self.known is not None:
            kd, kd1, kd7 = self.known(i, d), self.known(i, d - 1), self.known(i, d - 7)
            now = np.where(kd, now, np.nan)
            h24 = np.where(kd & kd1, h24, np.nan)
            d7 = np.where(kd7 & kd1, d7, np.nan)
        return pd.DataFrame({"spilling_at_issue": now, "spill_hours_24h": h24, "spill_days_7d": d7}).astype(np.float32)


def known_2024_25(sites, covered: dict) -> callable:
    idx = pd.Index(sorted(set(sites)))
    k24, k25 = idx.isin(covered.get(2024, set())), idx.isin(covered.get(2025, set()))

    def known(i, d):
        return (d >= 0) & (d < 731) & np.where(d < 366, k24[i], k25[i])
    return known


def check_against_254(st: InstantStatus, ev: pd.DataFrame, rows: pd.DataFrame, covered: dict) -> dict:
    """At H = 0 the inputs must equal #254's Status.features(..., k=0). Status only; no label is read."""
    ref = ls.Status(ev, rows["site_id"], covered).features(rows["site_id"], rows["day"], 0)
    mine = st.features(rows["site_id"], rows["day"], 0)
    out = {}
    for c in STATUS:
        a, b = mine[c].to_numpy(), ref[c].to_numpy()
        nan_mm = int((np.isnan(a) != np.isnan(b)).sum())
        both = np.isfinite(a) & np.isfinite(b)
        out[c] = {"rows": int(len(a)), "nan_mismatches": nan_mm,
                  "largest_abs_difference": float(np.abs(a[both] - b[both]).max()) if both.any() else 0.0}
        assert nan_mm == 0 and out[c]["largest_abs_difference"] < 1e-3, f"status differs from #254 on {c}: {out[c]}"
    return out


# ------------------------------------------------------------------ fits
def fit_s(df: pd.DataFrame) -> SpillModel:
    """#694's fit (r.fit) on the rain features plus the three status inputs."""
    m = SpillModel(features=list(FEATS))
    m.fit_pooled(df, seed=0)
    m.fit_site_offsets(df, prior_strength=15.0, recency=1.0)
    return m


def frame(base: pd.DataFrame, arms: dict, rain_arm: str, status: pd.DataFrame | None) -> pd.DataFrame:
    df = r.frame_for(base, r.attach(base, arms[rain_arm]))
    if status is not None:
        df[STATUS] = status[STATUS].to_numpy()
    return df


def arm_plan() -> list[tuple[str, str, int | None]]:
    """(arm, rain arm from #694, issue hour of the status inputs or None)."""
    plan = [("P", "P", None)]
    for h in HOURS:
        hh = f"{h:02d}"
        plan += [(f"F1@{hh}", f"F1@{hh}", None), (f"R0@{hh}", f"R0@{hh}", None), (f"R1@{hh}", f"R1@{hh}", None),
                 (f"PS@{hh}", "P", h), (f"F1S@{hh}", f"F1@{hh}", h), (f"R0S@{hh}", f"R0@{hh}", h),
                 (f"R1S@{hh}", f"R1@{hh}", h)]
    return plan


# ------------------------------------------------------------------ scoring
def pairs(p: dict, a: str, b: str) -> list:
    """(a@H, b@H) for every issue hour; 'P' has no hour."""
    g = lambda k, hh: p[k] if k == "P" else p[f"{k}@{hh}"]
    return [(g(a, f"{h:02d}"), g(b, f"{h:02d}")) for h in HOURS]


PAIRS = {"DS0_R0S_minus_PS": ("R0S", "PS"), "DS1_R1S_minus_F1S": ("R1S", "F1S"),
         "D0_R0_minus_P": ("R0", "P"), "D1_R1_minus_F1": ("R1", "F1"),
         "PS_minus_P": ("PS", "P"), "R0S_minus_R0": ("R0S", "R0")}


def comparisons(bt: r.Boot, y, p: dict, mask=None, by_hour=True) -> dict:
    out = {k: bt.pooled(y, pairs(p, a, b), mask) for k, (a, b) in PAIRS.items()}
    if by_hour and mask is None:
        out["by_hour"] = {f"{h:02d}": {k: bt.pooled(y, [pairs(p, a, b)[n]]) for k, (a, b) in PAIRS.items()}
                          for n, h in enumerate(HOURS)}
    return out


def split(y, site, week, dayn, p: dict, now: dict, seed) -> dict:
    """Rows spilling at the issue instant and the rest: by hour, and pooled over every (row, hour) pair."""
    bt = r.Boot(site, week, dayn, np.random.default_rng(seed))
    out = {"by_hour": {}}
    for n, h in enumerate(HOURS):
        hh = f"{h:02d}"
        sp = now[hh] == 1
        out["by_hour"][hh] = {"spilling_rows": int(sp.sum()), "spilling_spill_days": int(y[sp].sum())}
        for part, m in (("spilling", sp), ("rest", ~sp)):
            if y[m].sum() == 0:
                continue
            for k in ("DS0_R0S_minus_PS", "DS1_R1S_minus_F1S", "D0_R0_minus_P", "D1_R1_minus_F1"):
                a, b = PAIRS[k]
                out["by_hour"][hh][f"{part}:{k}"] = bt.pooled(y, [pairs(p, a, b)[n]], m)
    del bt
    nh = len(HOURS)
    st = r.Boot(np.tile(site, nh), np.tile(week, nh), np.tile(dayn, nh), np.random.default_rng(seed))
    ys = np.tile(y, nh)
    sp = np.concatenate([now[f"{h:02d}"] == 1 for h in HOURS])
    out["pooled_pairs"] = {"spilling_pairs": int(sp.sum()), "rest_pairs": int((~sp).sum())}
    for k in ("DS0_R0S_minus_PS", "DS1_R1S_minus_F1S", "D0_R0_minus_P", "D1_R1_minus_F1"):
        a, b = PAIRS[k]
        pa = np.concatenate([x for x, _ in pairs(p, a, b)])
        pb = np.concatenate([x for _, x in pairs(p, a, b)])
        for part, m in (("spilling", sp), ("rest", ~sp)):
            if ys[m].sum() > 0:
                out["pooled_pairs"][f"{part}:{k}"] = st.diff(ys, pa, pb, m)
    return out


def status_unknown(stat: dict) -> dict:
    return {hh: {c: int(np.isnan(s[c].to_numpy()).sum()) for c in STATUS} for hh, s in stat.items()}


# ------------------------------------------------------------------ main
def main(radar_dir: str, pub_csv: str, out_dir: str) -> None:
    radar_dir, out = Path(radar_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {"protocol": "docs/RADAR-PLUS-STATUS-TEST-2026-11.md", "seed": r.SEED, "draws": r.BOOT,
                 "issue_hours_utc": list(HOURS)}

    # rows: #694's, built by #694's steps
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sites, _ = site_years(ar, ev, NINE, 2025)
    radar_cells = set.intersection(*(r.cells_in([radar_dir], f"radar_*_{m}.parquet") for m in r.RADAR_MONTHS))
    lead25 = r.cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2025.parquet")
    use = radar_cells & lead25
    sc = list(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    sites = sites[np.array([c in use for c in sc])].reset_index(drop=True)
    if PLUMBING:
        sites = sites.sample(n=min(300, len(sites)), random_state=1).reset_index(drop=True)
        res["plumbing"] = True
    res["sites"] = {"used": int(len(sites)), "by_company": sites["company"].value_counts().to_dict()}
    cells = sorted(set(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)))
    cells = [(round(float(a), 3), round(float(b), 3)) for a, b in cells]
    res["cells"] = len(cells)
    log(f"{len(sites)} overflows in {len(cells)} cells")

    era = daily_rain_features(load_rain(set(cells), tags=("2024", "2025", "2026", "2026a"), start="2024-11-25"))
    h = r.Hourly(radar_dir, Path(pub_csv), cells)
    res["publish_times"] = h.pub_stats
    all_days = pd.date_range(r.Y0, r.F1, freq="D", tz="UTC")
    cr = daily_rain_features(h.as_long(h.radar))
    p0 = daily_rain_features(h.as_long(h.f0))
    arms, res["issue_hour_stats"] = r.build_arms(h, all_days, cr, p0)
    names = list(arms)
    del h
    log(f"{len(names)} rain arms built")

    # status, built and checked before any label is joined
    days = pd.date_range(r.Y0, r.Y1, freq="D", tz="UTC")
    base = build_site_days(sites, era, days).reset_index(drop=True)
    covered = ls.covered_years(ar, ev, [2024, 2025])
    st = InstantStatus(ev, base["site_id"], known_2024_25(base["site_id"], covered))
    res["status"] = {"merged_events": st.n_intervals,
                     "check_against_254_at_00": check_against_254(st, ev, base[["site_id", "day"]], covered)}
    log(f"status: {st.n_intervals} merged events; H=0 matches #254: {res['status']['check_against_254_at_00']}")

    labels = spill_days(ev)
    labels = labels[(labels.day >= r.Y0) & (labels.day <= r.Y1)]
    base = base.merge(labels.assign(y=1), on=["site_id", "day"], how="left")
    base["y"] = base["y"].fillna(0).astype(np.int8)
    base = base.merge(sites[["site_id", "company"]], on="site_id", how="left").reset_index(drop=True)
    ok = base[["rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy().copy()
    ok &= base[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
    for k in names:
        ok &= r.attach(base, arms[k])[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
    res["rows"] = {"before_mask": int(len(base)), "scored": int(ok.sum()), "spill_days": int(base["y"].to_numpy()[ok].sum())}
    if PLUMBING:
        base["y"] = (np.random.default_rng(1).random(len(base)) < base["y"].mean()).astype(np.int8)
    base = base[ok].reset_index(drop=True)
    stat = {f"{hr:02d}": st.features(base["site_id"], base["day"], hr) for hr in HOURS}
    res["status"]["unknown_rows_by_hour"] = status_unknown(stat)
    res["status"]["spilling_at_issue_rows_by_hour"] = {k: int((v["spilling_at_issue"] == 1).sum()) for k, v in stat.items()}
    log(f"rows: {len(base)}, spill days {res['rows']['spill_days']}")

    # folds, as #694
    block = (base["day"].dt.month.to_numpy() - 1) // 2
    in_a = np.isin(block, list(r.FOLD_A))
    dayn = (base["day"] - r.Y0).dt.days.to_numpy()
    test_days = {f: np.unique(dayn[in_a if f == "A" else ~in_a]) for f in ("A", "B")}

    def train_mask(f: str) -> np.ndarray:
        td = test_days[f]
        idx = np.searchsorted(td, dayn)
        near = np.minimum(np.abs(dayn - td[np.clip(idx, 0, len(td) - 1)]), np.abs(dayn - td[np.clip(idx - 1, 0, len(td) - 1)]))
        return (~(in_a if f == "A" else ~in_a)) & (near > r.EMBARGO)

    res["folds"] = {f: {"test_rows": int((in_a if f == "A" else ~in_a).sum()), "train_rows": int(train_mask(f).sum())}
                    for f in ("A", "B")}
    y = base["y"].to_numpy().astype(float)
    oof, hashes, frozen_hash, frozen = {}, {}, {}, {}
    for k, rain_arm, hr in arm_plan():
        df = frame(base, arms, rain_arm, None if hr is None else stat[f"{hr:02d}"])
        fitter = r.fit if hr is None else fit_s
        p = np.full(len(df), np.nan)
        for f in ("A", "B"):
            tr, te = train_mask(f), (in_a if f == "A" else ~in_a)
            m = fitter(df[tr])
            p[te] = m.predict(df[te])
            hashes[f"{k}/{f}"] = r.model_hash(m)
        oof[k] = p
        frozen[k] = fitter(df)
        frozen_hash[k] = r.model_hash(frozen[k])
        log(f"arm {k} fitted, predicted out of fold, and refitted on all of 2025")
        del df
    assert all(np.isfinite(v).all() for v in oof.values())
    res["fold_model_sha256"], res["frozen_model_sha256"] = hashes, frozen_hash

    week = base["day"].dt.strftime("%G-%V").to_numpy()
    site = base["site_id"].to_numpy()
    bt = r.Boot(site, week, dayn, np.random.default_rng(r.SEED))
    pc = comparisons(bt, y, oof)
    res["primary"] = {"by_arm": {k: r.summary(y, v) for k, v in oof.items()}, "comparisons": pc,
                      "verdict": r.verdict(pc["DS0_R0S_minus_PS"], pc["DS1_R1S_minus_F1S"]),
                      "share_of_radar_gain_kept": {"DS0/D0": pc["DS0_R0S_minus_PS"]["diff"] / pc["D0_R0_minus_P"]["diff"],
                                                   "DS1/D1": pc["DS1_R1S_minus_F1S"]["diff"] / pc["D1_R1_minus_F1"]["diff"]}}
    log("primary comparisons done")
    now = {k: v["spilling_at_issue"].to_numpy() for k, v in stat.items()}
    res["split_spilling_at_issue"] = split(y, site, week, dayn, oof, now, r.SEED)
    log("split done")

    sn = r.season(base["day"])
    groups = {**{f"company:{c}": (base["company"] == c).to_numpy() for c in sorted(base["company"].unique())},
              **{f"season:{s}": sn == s for s in ("DJF", "MAM", "JJA", "SON")}}
    res["breakdowns"] = {}
    for g, msk in groups.items():
        res["breakdowns"][g] = {"rows": int(msk.sum()), "spill_days": int(y[msk].sum())}
        if y[msk].sum() > 0:
            res["breakdowns"][g].update(comparisons(bt, y, oof, msk, by_hour=False))
    del bt
    log("breakdowns done")

    # the 2026 forward check: frozen fits on Thames, status from the same stream file as the labels
    api = pd.read_parquet(config.PROCESSED / "api_events_thames_water.parquet")
    api = api[api["event_start"] < r.F1 + pd.Timedelta(days=1)]          # nothing read after 31 August 2026
    lead26 = r.cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2026.parquet")
    th = sites[(sites["company"] == "Thames Water") & sites["site_id"].isin(set(api["site_id"]))]
    thc = list(zip(*grid_cell(th["lat"].to_numpy(), th["lon"].to_numpy()), strict=True))
    th = th[[(round(float(a), 3), round(float(b), 3)) in lead26 for a, b in thc]].reset_index(drop=True)
    fw = {"with_2026_leads": int(len(th))}
    if len(th):
        b26 = build_site_days(th, era, pd.date_range(r.F0, r.F1, freq="D", tz="UTC")).reset_index(drop=True)
        st26 = InstantStatus(api, b26["site_id"], None)
        lab26 = spill_days(api)
        lab26 = lab26[(lab26.day >= r.F0) & (lab26.day <= r.F1)]
        b26 = b26.merge(lab26.assign(y=1), on=["site_id", "day"], how="left")
        b26["y"] = b26["y"].fillna(0).astype(np.int8)
        ok26 = b26[["rain_d", "rain_d1", "rain_d2", "rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy().copy()
        for k in names:
            ok26 &= r.attach(b26, arms[k])[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
        b26 = b26[ok26].reset_index(drop=True)
        if PLUMBING:
            b26["y"] = (np.random.default_rng(2).random(len(b26)) < max(b26["y"].mean(), 0.01)).astype(np.int8)
        y26 = b26["y"].to_numpy().astype(float)
        s26 = {f"{hr:02d}": st26.features(b26["site_id"], b26["day"], hr) for hr in HOURS}
        p26 = {k: frozen[k].predict(frame(b26, arms, ra, None if hr is None else s26[f"{hr:02d}"]))
               for k, ra, hr in arm_plan()}
        w26 = b26["day"].dt.strftime("%G-%V").to_numpy()
        d26 = (b26["day"] - r.F0).dt.days.to_numpy()
        bt3 = r.Boot(b26["site_id"].to_numpy(), w26, d26, np.random.default_rng(r.SEED))
        c26 = comparisons(bt3, y26, p26)
        fw.update({"rows": int(len(b26)), "spill_days": int(y26.sum()), "overflows_scored": int(b26["site_id"].nunique()),
                   "merged_events": st26.n_intervals, "status_unknown_rows_by_hour": status_unknown(s26),
                   "by_arm": {k: r.summary(y26, v) for k, v in p26.items()}, "comparisons": c26,
                   "split_spilling_at_issue": split(y26, b26["site_id"].to_numpy(), w26, d26, p26,
                                                    {k: v["spilling_at_issue"].to_numpy() for k, v in s26.items()}, r.SEED)})
    res["forward_2026_thames"] = fw
    log("forward check done")

    res["seconds"] = round(time.time() - T0, 1)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    if PLUMBING:
        print("plumbing run: done; scores on random labels are not printed")
        return
    print(json.dumps({"verdict": res["primary"]["verdict"], "rows": res["rows"]["scored"],
                      "DS0": pc["DS0_R0S_minus_PS"], "DS1": pc["DS1_R1S_minus_F1S"]}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
