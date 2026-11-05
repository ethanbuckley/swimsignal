"""Spill duration: the frozen company x elapsed table (B1) against "stops now", on the live site's own polls
(docs/SPILL-DURATION-LIVE-CHECK-2026-11.md). An offline held-out check, not prospective evidence. Off CI, by hand:

    DIPCAST_ROOT=<checkout with data/processed> uv run python scripts/spill_duration_live_check.py freeze --poll-log <poll_log.parquet>
    uv run python scripts/spill_duration_live_check.py score --state <dir with live_history, live_coverage, poll_log> --out <dir>

`freeze` fits B1 on every 2024-25 row of the poll replay (scripts/spill_duration_replay.py, seed 0, the same rows its
out-of-fold run scored) and writes the table beside the write-up. It reads no 2026 outcome.

`score` reads the poller's files only and makes no request. It rebuilds, from live_history.parquet (an event log: one
row per overflow, status and status start, with the last poll that saw it) and live_coverage.parquet (the half-hours
each overflow had a known, current reading):

- Issue rows: for each overflow and whole UTC hour from WINDOW_FROM, the first poll in that hour at which the overflow
  had a current known reading and was discharging. Discharging at poll t: its latest history row starting at or before
  t has status 1 and was still seen at or after t. Elapsed time is t less that row's start (the feed's discharge start),
  under CAP_H.
- Poll-observed outcome at t + h: at the company's last poll at or before t + h, if that poll is after t, within
  FRESH_H of t + h, and the overflow had a current known reading in its half-hour: 1 if the same discharge (same start)
  was still running, else 0. Otherwise censored: no fresh poll, an unknown or stale reading, or past the data's end.
- Feed-reported end (reported, not the primary label): the start of the overflow's next history row, or the row's own
  event end. A discharge the feed never closed is censored at the last poll that saw it.

Each is scored where it is not censored. Neither is the EA's own record of when the spill ended.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spill_duration_replay as rp  # noqa: E402
import spill_duration_test as base  # noqa: E402
from dipcast.model.training import NINE  # noqa: E402

HORIZONS = base.HORIZONS
PRIMARY = (3, 6)
CAP_H = base.CAP_H
FRESH_H = 2.0
WINDOW_FROM = pd.Timestamp("2026-09-28 17:00", tz="UTC")   # the first full hour with feed ages in the poll log
LOCAL_TZ = "Europe/London"
DOCS = Path(__file__).resolve().parents[1] / "docs" / "SPILL-DURATION-LIVE-CHECK-2026-11"
TABLE = Path(f"{DOCS}-b1.csv")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ freeze (2024-25 only)
def freeze(poll_log: Path) -> None:
    import spill_duration_calibration_test as cal
    from dipcast import config
    from dipcast.model.training import load_events
    ev = load_events(NINE)
    ev = ev[ev["event_start"] < pd.Timestamp("2026-01-01", tz="UTC")]
    sp, raw = base.merge_spells(ev, base.GAP_H), base.merge_spells(ev, 0.0)
    real = rp.real_polls(pd.read_parquet(poll_log))
    lo_h, hi_h = rp.hours([rp.WINDOW[0]])[0] - CAP_H - 48, rp.hours([rp.WINDOW[1]])[0] + 48
    polls = rp.Polls(rp.lay_polls(real, lo_h, hi_h, 0), cal.RawIndex(raw))
    rows = rp.replay_rows(raw, sp, polls, *rp.WINDOW)
    sites = cal.site_table(pd.read_parquet(config.PROCESSED / "annual_returns.parquet"), ev, (2024, 2025))
    k = pd.MultiIndex.from_arrays([sp["site_id"].to_numpy()[rows["spell"].to_numpy()], rows["t"].dt.year.to_numpy()])
    rows = rows[k.isin(pd.MultiIndex.from_frame(sites[["site_id", "year"]]))].reset_index(drop=True)
    comp = sp["company"].to_numpy()[rows["spell"].to_numpy()]
    ebin = base.elapsed_bin(rows["elapsed_h"].to_numpy())
    y = base.labels(rows)
    df = pd.DataFrame(y, columns=[f"h{h}" for h in HORIZONS]).assign(company=comp, ebin=ebin)
    cell = df.groupby(["company", "ebin"]).agg(rows=("h1", "size"), **{f"h{h}": (f"h{h}", "mean") for h in HORIZONS})
    comp_all = df.drop(columns="ebin").groupby("company").agg(rows=("h1", "size"), **{f"h{h}": (f"h{h}", "mean") for h in HORIZONS})
    table = pd.concat([cell.reset_index(), comp_all.reset_index().assign(ebin=-1)], ignore_index=True)
    table["elapsed_from_h"] = table["ebin"].map(lambda b: base.ELAPSED_EDGES[b] if b >= 0 else None)
    table["elapsed_to_h"] = table["ebin"].map(lambda b: base.ELAPSED_EDGES[b + 1] if b >= 0 else None)
    table = table[["company", "ebin", "elapsed_from_h", "elapsed_to_h", "rows", *[f"h{h}" for h in HORIZONS]]]
    table[[f"h{h}" for h in HORIZONS]] = table[[f"h{h}" for h in HORIZONS]].round(6)
    table.to_csv(TABLE, index=False)
    print(f"{len(rows)} rows; wrote {TABLE} sha256 {sha256(TABLE)}")


def b1_predict(table: pd.DataFrame, company: np.ndarray, elapsed: np.ndarray) -> np.ndarray:
    """The frozen table, as spill_duration_test.predict_empirical reads it: (company, elapsed bin), else the company."""
    t = table.set_index(["company", "ebin"])[[f"h{h}" for h in HORIZONS]]
    ebin = base.elapsed_bin(elapsed)
    p = t.reindex(pd.MultiIndex.from_arrays([company, ebin])).to_numpy()
    miss = np.isnan(p).any(1)
    if miss.any():
        p[miss] = t.reindex(pd.MultiIndex.from_arrays([company[miss], np.full(miss.sum(), -1)])).to_numpy()
    return base.monotone(p)


# ------------------------------------------------------------------ score (2026 polls)
class Live:
    """Status, starts and current readings from the poller's files."""

    def __init__(self, hist: pd.DataFrame, cov: pd.DataFrame):
        h = hist.copy()
        fetched = pd.to_datetime(h["fetched_at"], utc=True)
        start = pd.to_datetime(h["status_start"], utc=True)
        start = start.fillna(pd.to_datetime(h["latest_event_start"], utc=True).where(h["status"] == 1))
        h = h.assign(start=start, fetched=fetched)[start.notna()]
        h = h.sort_values(["site_id", "start", "fetched"], kind="mergesort").reset_index(drop=True)
        self.h = h
        self.codes = pd.Index(np.unique(h["site_id"].astype(str)))
        self.c = self.codes.get_indexer(h["site_id"].astype(str))
        self.s = rp.hours(h["start"])
        self.f = rp.hours(h["fetched"])
        self.status = h["status"].to_numpy()
        self.ev_end = rp.hours(pd.to_datetime(h["latest_event_end"], utc=True))
        self.key = self.c * 1e7 + self.s
        # The next row's start, for the same overflow: when the feed says this status ended.
        nxt = np.r_[self.s[1:], np.nan]
        same = np.r_[self.c[1:] == self.c[:-1], False]
        self.next_start = np.where(same, nxt, np.nan)
        c = cov.copy()
        c["day"] = pd.to_datetime(c["day"]).dt.date.astype(str)
        self.slots = dict(zip(zip(c["site_id"].astype(str), c["day"]), c["slots"].astype(np.int64), strict=True))

    def row_at(self, code: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Index of each overflow's latest history row starting at or before t (-1 for none)."""
        j = np.searchsorted(self.key, code * 1e7 + t, side="right") - 1
        jj = np.clip(j, 0, None)
        return np.where((j >= 0) & (self.c[jj] == code), j, -1)

    def discharging(self, code, t) -> tuple[np.ndarray, np.ndarray]:
        j = self.row_at(code, t)
        jj = np.clip(j, 0, None)
        return (j >= 0) & (self.status[jj] == 1) & (self.f[jj] >= t - 1e-6), j

    def current(self, site: np.ndarray, t: np.ndarray) -> np.ndarray:
        """A known, current reading in t's local half-hour (live_coverage's slot bits)."""
        local = (rp.T0 + pd.to_timedelta(t, unit="h")).tz_convert(LOCAL_TZ)
        day = local.strftime("%Y-%m-%d")
        slot = (local.hour * 2 + local.minute // 30).to_numpy()
        bits = np.array([self.slots.get((s, d), 0) for s, d in zip(site, day, strict=True)], np.int64)
        return ((bits >> slot) & 1).astype(bool)


def issue_rows(live: Live, polls: pd.DataFrame) -> pd.DataFrame:
    """Per overflow and whole UTC hour, the first poll in it that saw the overflow discharging with a current reading."""
    out = []
    company_of = live.h.drop_duplicates("site_id").set_index("site_id")["company"].astype(str)
    for comp, g in polls.groupby("company"):
        sites = company_of.index[company_of.to_numpy() == comp].to_numpy()
        codes = live.codes.get_indexer(sites)
        for t in g["t"].to_numpy():
            run, j = live.discharging(codes, np.full(len(codes), t))
            if not run.any():
                continue
            out.append(pd.DataFrame({"site_id": sites[run], "code": codes[run], "company": comp, "t": t, "row": j[run]}))
    r = pd.concat(out, ignore_index=True)
    r["hour"] = np.floor(r["t"])
    r = r.sort_values(["site_id", "t"]).drop_duplicates(["site_id", "hour"], keep="first")
    r = r[live.current(r["site_id"].to_numpy(), r["t"].to_numpy())]
    r["elapsed_h"] = (r["t"] - live.s[r["row"].to_numpy()]).astype(np.float32)
    return r[(r["elapsed_h"] >= 0) & (r["elapsed_h"] < CAP_H)].reset_index(drop=True)


def outcomes(live: Live, rows: pd.DataFrame, polls: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """[rows, horizons] poll-observed outcome and feed-reported-end outcome, NaN where censored; censoring counts."""
    n = len(rows)
    seen = np.full((n, len(HORIZONS)), np.nan, np.float32)
    ended = np.full((n, len(HORIZONS)), np.nan, np.float32)
    why = {}
    row = rows["row"].to_numpy()
    start = live.s[row]
    end_rep = np.where(np.isfinite(live.next_start[row]), live.next_start[row],
                       np.where(live.ev_end[row] >= start, live.ev_end[row], np.nan))
    last_seen = live.f[row]
    t = rows["t"].to_numpy()
    for j, h in enumerate(HORIZONS):
        target = t + h
        pt = np.full(n, np.nan)
        for comp, g in polls.groupby("company"):
            m = rows["company"].to_numpy() == comp
            ts = np.sort(g["t"].to_numpy())
            k = np.searchsorted(ts, target[m], side="right") - 1
            pt[m] = np.where(k >= 0, ts[np.clip(k, 0, None)], np.nan)
        fresh = (pt > t + 1e-6) & (pt >= target - FRESH_H)
        cur = np.zeros(n, bool)
        cur[fresh] = live.current(rows["site_id"].to_numpy()[fresh], pt[fresh])
        ok = fresh & cur
        run, jj = live.discharging(rows["code"].to_numpy(), np.where(ok, pt, 0.0))
        same = run & (jj == row)
        seen[ok, j] = same[ok].astype(np.float32)
        why[f"{h}h"] = {"scored": int(ok.sum()), "no_fresh_poll": int((~fresh).sum()), "not_current": int((fresh & ~cur).sum())}
        # Feed-reported end: known when the feed gave one, or when the discharge was still seen after t + h.
        known_end = np.isfinite(end_rep)
        ended[known_end, j] = (end_rep[known_end] > target[known_end]).astype(np.float32)
        still = ~known_end & (last_seen >= target)
        ended[still, j] = 1.0
        why[f"{h}h"]["feed_end_censored"] = int((~known_end & ~still).sum())
    return seen, ended, why


def boot_days(d: np.ndarray, day: np.ndarray, n: int = 2000) -> tuple[float, float]:
    codes, inv = np.unique(day, return_inverse=True)
    W = len(codes)
    draws = np.random.default_rng(0).integers(0, W, size=(n, W))
    s = np.bincount(inv, weights=d, minlength=W)
    c = np.bincount(inv, minlength=W).astype(float)
    stat = s[draws].sum(1) / np.maximum(c[draws].sum(1), 1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def score(state: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    files = {n: state / n for n in ("live_history.parquet", "live_coverage.parquet", "poll_log.parquet")}
    before = {n: sha256(p) for n, p in files.items()} | {TABLE.name: sha256(TABLE)}
    table = pd.read_csv(TABLE)
    live = Live(pd.read_parquet(files["live_history.parquet"]), pd.read_parquet(files["live_coverage.parquet"]))
    pl = pd.read_parquet(files["poll_log.parquet"])
    pl = pl[(pl["n_rows"] > 0) & (pd.to_datetime(pl["fetched_at"], utc=True) >= WINDOW_FROM)]
    polls = pd.DataFrame({"company": pl["company"].astype(str), "t": rp.hours(pl["fetched_at"])})
    last_poll = polls["t"].max()
    rows = issue_rows(live, polls)
    rows = rows[rows["t"] <= last_poll].reset_index(drop=True)
    comp = rows["company"].to_numpy()
    preds = {"B1 company x elapsed (frozen 2024-25)": b1_predict(table, comp, rows["elapsed_h"].to_numpy()),
             "stops now (the site today)": np.zeros((len(rows), len(HORIZONS))),
             "keeps running": np.ones((len(rows), len(HORIZONS)))}
    seen, ended, why = outcomes(live, rows, polls)
    day = (rp.T0 + pd.to_timedelta(rows["t"].to_numpy(), unit="h")).tz_convert(LOCAL_TZ).strftime("%Y-%m-%d").to_numpy()
    res = []
    for label, Y in (("poll-observed", seen), ("feed-reported end", ended)):
        for c in [*NINE, "all nine"]:
            m = np.ones(len(rows), bool) if c == "all nine" else comp == c
            for j, h in enumerate(HORIZONS):
                ok = m & np.isfinite(Y[:, j])
                if not ok.any():
                    continue
                y = Y[ok, j]
                r = {"label": label, "company": c, "horizon_h": h, "issue_rows": int(m.sum()), "scored": int(ok.sum()),
                     "observed": float(y.mean())}
                for name, p in preds.items():
                    r[f"brier {name}"] = float(((p[ok, j] - y) ** 2).mean())
                pb = preds["B1 company x elapsed (frozen 2024-25)"][ok, j]
                r["B1 mean forecast"] = float(pb.mean())
                r["B1 ece"] = base.ece(pb, y)
                d = (pb - y) ** 2 - y ** 2
                r["B1 minus stops-now"] = float(d.mean())
                r["lo"], r["hi"] = boot_days(d, day[ok])
                res.append(r)
            # Primary: mean over 3 h and 6 h, on rows scored at both.
            jj = [HORIZONS.index(h) for h in PRIMARY]
            ok = m & np.isfinite(Y[:, jj]).all(1)
            if ok.any():
                pb = preds["B1 company x elapsed (frozen 2024-25)"][ok][:, jj]
                y = Y[ok][:, jj]
                d = ((pb - y) ** 2 - y ** 2).mean(1)
                lo, hi = boot_days(d, day[ok])
                res.append({"label": label, "company": c, "horizon_h": "3+6", "issue_rows": int(m.sum()), "scored": int(ok.sum()),
                            "observed": float(y.mean()), "brier B1 company x elapsed (frozen 2024-25)": float(((pb - y) ** 2).mean()),
                            "brier stops now (the site today)": float((y ** 2).mean()),
                            "brier keeps running": float(((1 - y) ** 2).mean()), "B1 mean forecast": float(pb.mean()),
                            "B1 minus stops-now": float(d.mean()), "lo": lo, "hi": hi})
    t = pd.DataFrame(res)
    t.to_csv(out / "scores.csv", index=False)
    after = {n: sha256(p) for n, p in files.items()} | {TABLE.name: sha256(TABLE)}
    summary = {"inputs": before, "inputs_unchanged": before == after, "window_from": str(WINDOW_FROM),
               "last_poll": str(rp.T0 + pd.Timedelta(hours=float(last_poll))), "issue_rows": len(rows),
               "overflows": int(rows["site_id"].nunique()), "discharges": int(rows["row"].nunique()),
               "issue_rows_by_company": rows["company"].value_counts().to_dict(), "censoring": why,
               "elapsed_median_h": float(rows["elapsed_h"].median())}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    p = t[(t["horizon_h"].astype(str) == "3+6")]
    print(p[["label", "company", "scored", "observed", "brier B1 company x elapsed (frozen 2024-25)",
             "brier stops now (the site today)", "B1 minus stops-now", "lo", "hi"]].to_string(index=False))
    print(json.dumps({k: summary[k] for k in ("issue_rows", "overflows", "discharges", "censoring", "inputs_unchanged")}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["freeze", "score"])
    ap.add_argument("--poll-log", type=Path)
    ap.add_argument("--state", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.step == "freeze":
        freeze(a.poll_log)
    else:
        score(a.state, a.out)


if __name__ == "__main__":
    main()
