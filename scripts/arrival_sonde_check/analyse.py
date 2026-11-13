"""docs/ARRIVAL-TIME-SONDE-CHECK-2026-11.md, sections 4 to 7: join the EA spill starts to the sonde readings.

    analyse.py <stations.csv> <readings dir> <out dir> [stated|amended]

"stated" (the default) is sections 4 to 6 as written. "amended" is amendment 2 (section 12): the same rules counted
in each sonde's own reading interval.

Offline. For each fetched sonde: the quiet-rule events (core.find_events), their tier, the rise outcome under the
three rules (core.detect), the implied speed, the dry reference and the per-sonde summary. Writes events.csv (one
row per event: times, distances, lags; no raw series), per_sonde.csv and summary.json. Run with a scratch
DIPCAST_ROOT that links the main checkout's inputs.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "src"), str(HERE), str(REPO / "scripts" / "sonde_signal_eval")]
assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from core import (D_MIN_BY_CADENCE, MODEL_MS, QUIET_H, detect, detect_c, find_events, horizon_h,  # noqa: E402
                  implied_speed, median_ci, model_window, others_in_window, to_grid, valid_readings)
from relate import load_events, upstream_tables  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.network.rivers import RiverNetwork  # noqa: E402

DRAWS, SEED = 2000, 0
PSEUDO_STEP_MIN = 360          # pseudo-starts at 00, 06, 12 and 18 UTC
PSEUDO_AFTER_H = 72.0          # no spill upstream from 48 h before to 72 h after
MIN_RISES = 5                  # a median and its interval need this many rises
POOL_MIN_SONDES, POOL_MIN_RIVERS = 3, 2


def read_series(path: Path, mode: str = "stated"):
    """(det, first, last, rows, valid) from a readings CSV: det(t0, h_h, rule) is the outcome at a reference minute
    under the stated rules (15-minute slots) or the amended ones (the sonde's own interval); first and last are the
    series' ends in minutes. An empty file is a sonde with no readings in the period: det is None."""
    if not path.exists() or path.stat().st_size == 0:
        return None, 0, 0, 0, 0
    d = pd.read_csv(path, usecols=["dateTime", "value", "quality"])
    minutes = (pd.to_datetime(d["dateTime"], utc=True).astype("datetime64[s, UTC]").astype("int64") // 60).to_numpy()
    values = pd.to_numeric(d["value"], errors="coerce").to_numpy()
    if mode == "amended":
        tm, v = valid_readings(minutes, values, d["quality"].to_numpy())
        if len(tm) == 0:
            return None, 0, 0, len(d), 0
        return (lambda t0, h, rule="main": detect_c(tm, v, t0, h, rule)), tm[0], tm[-1], len(d), len(tm)
    g0, x = to_grid(minutes, values, d["quality"].to_numpy())
    return ((lambda t0, h, rule="main": detect(g0, x, t0, h, rule)), g0, g0 + (len(x) - 1) * 15, len(d),
            int(np.isfinite(x).sum()))


def iso(minute: float) -> str:
    return pd.Timestamp(int(minute) * 60, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%MZ")


def week(minute: float) -> str:
    c = pd.Timestamp(int(minute) * 60, unit="s", tz="UTC").isocalendar()
    return f"{c.year}-W{c.week:02d}"


def spill_free(sp: pd.DataFrame, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Whether no spill overlaps each [lo, hi] (minutes)."""
    start = np.sort(sp["start"].to_numpy(dtype=float))
    order = np.argsort(sp["start"].to_numpy(dtype=float))
    cummax_end = np.maximum.accumulate(sp["end"].to_numpy(dtype=float)[order])
    k = np.searchsorted(start, hi, side="right")          # spills that start at or before hi
    latest_end = np.where(k > 0, cummax_end[np.maximum(k - 1, 0)], -np.inf)
    return latest_end < lo


def events_for(sp: pd.DataFrame, timing: pd.DataFrame, lake_sites: set, det, quiet_h: float,
               amended: bool = False) -> list[dict]:
    travel = dict(zip(timing["site_id"], timing["travel_h"], strict=True))
    out = []
    for e in find_events(sp, quiet_h).itertuples():
        if e.site_id not in travel:
            continue
        h = horizon_h(e.d_m)
        res = det(e.t0, h, "main")
        if res["status"] == "outside":
            continue
        if amended and "c" in res and e.d_m < D_MIN_BY_CADENCE[res["c"]]:
            continue          # amendment 2: too near for this sonde's reading interval
        oth = others_in_window(sp, e.t0, h, e.site_id)
        tier = "A" if oth.empty else ("B" if not (set(oth["site_id"]) & lake_sites) else "B-lake")
        row = {"t0": iso(e.t0), "week": week(e.t0), "site_id": e.site_id, "d_m": round(e.d_m),
               "travel_h": round(travel[e.site_id], 2), "spill_h": round((e.end - e.t0) / 60.0, 2), "h_h": round(h, 1),
               "tier": tier, "others": int(oth["site_id"].nunique()), "status": res["status"],
               "b": res.get("b"), "theta": res.get("theta"), "c": res.get("c", 15 if "b" in res else None), "lag_h": None, "peak_lag_h": None, "v_ms": None,
               "window": None}
        for rule in ("looser", "stricter"):
            d2 = det(e.t0, h, rule)
            row[f"status_{rule}"], row[f"lag_h_{rule}"] = d2["status"], d2.get("lag_h") if d2["status"] == "rise" else None
        if res["status"] in ("rise", "raised before"):
            row["lag_h"] = res["lag_h"]
        if res["status"] == "rise":
            row["peak_lag_h"] = res["peak_lag_h"]
            onset = e.t0 + res["lag_h"] * 60
            if tier == "A":
                # A rise in the same slot as the start has no measurable lag: speed is not defined.
                row["v_ms"] = e.d_m / (res["lag_h"] * 3600) if res["lag_h"] > 0 else None
                row["window"] = model_window(res["lag_h"], travel[e.site_id], (e.end - e.t0) / 60.0)
            elif tier == "B":
                v = implied_speed(np.r_[e.t0, oth["start"].to_numpy(dtype=float)],
                                  np.r_[e.d_m, oth["d_m"].to_numpy(dtype=float)], onset)
                row["v_ms"] = v if np.isfinite(v) else None
        out.append(row)
    return out


def dry_reference(sp: pd.DataFrame, det, first: float, last: float, horizons: list[float]) -> pd.DataFrame:
    """One row per pseudo-start and horizon: week, h_h, rise (True, False; other outcomes are dropped)."""
    cols = ["week", "h_h", "rise"]
    start = -(-(int(first) + 30 * 60) // PSEUDO_STEP_MIN) * PSEUDO_STEP_MIN
    t = np.arange(start, last - PSEUDO_AFTER_H * 60 + 1, PSEUDO_STEP_MIN, dtype=float)
    if len(t) == 0 or not horizons:
        return pd.DataFrame(columns=cols)
    t = t[spill_free(sp, t - QUIET_H * 60, t + PSEUDO_AFTER_H * 60)]
    rows = []
    for ti in t:
        for h in horizons:
            st = det(ti, h, "main")["status"]
            if st in ("rise", "no rise"):
                rows.append({"week": week(ti), "h_h": h, "rise": st == "rise"})
    return pd.DataFrame(rows, columns=cols)


def signal(ev_a: pd.DataFrame, dry: pd.DataFrame) -> dict:
    """Tier A rise share less the background share at the same horizons, with a 95% interval (ISO weeks)."""
    real = ev_a[ev_a["status"].isin(["rise", "no rise"])]
    n = len(real)
    if n == 0 or dry.empty:
        return {"n": n, "rise_share": None, "background_share": None, "diff": None, "lo": None, "hi": None,
                "pseudo_starts": 0 if dry.empty else int(dry.groupby("h_h").size().max()), "signal": False}
    hs = sorted(set(real["h_h"]))
    weeks = sorted(set(real["week"]) | set(dry["week"]))
    wi = {w: i for i, w in enumerate(weeks)}
    r_n, r_k = np.zeros((len(weeks), len(hs))), np.zeros((len(weeks), len(hs)))
    p_n, p_k = np.zeros((len(weeks), len(hs))), np.zeros((len(weeks), len(hs)))
    for j, h in enumerate(hs):
        a = real[real["h_h"] == h]
        np.add.at(r_n[:, j], [wi[w] for w in a["week"]], 1)
        np.add.at(r_k[:, j], [wi[w] for w in a["week"]], (a["status"] == "rise").to_numpy(dtype=float))
        d = dry[dry["h_h"] == h]
        np.add.at(p_n[:, j], [wi[w] for w in d["week"]], 1)
        np.add.at(p_k[:, j], [wi[w] for w in d["week"]], d["rise"].to_numpy(dtype=float))

    def shares(w: np.ndarray) -> tuple[float, float]:
        rn, rk, pn, pk = (w @ m for m in (r_n, r_k, p_n, p_k))
        if rn.sum() == 0 or (pn[rn > 0] == 0).any():
            return np.nan, np.nan
        p0 = np.divide(pk, pn, out=np.zeros_like(pk), where=pn > 0)
        return rk.sum() / rn.sum(), float((rn * p0).sum() / rn.sum())

    share, back = shares(np.ones(len(weeks)))
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(DRAWS):
        w = np.bincount(rng.integers(0, len(weeks), len(weeks)), minlength=len(weeks)).astype(float)
        s, b = shares(w)
        if np.isfinite(s):
            diffs.append(s - b)
    lo, hi = (np.quantile(diffs, [0.025, 0.975]) if len(diffs) >= DRAWS // 2 else (np.nan, np.nan))
    ok = bool(np.isfinite(lo) and lo > 0)
    f = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 3)  # noqa: E731
    return {"n": n, "rise_share": f(share), "background_share": f(back), "diff": f(share - back), "lo": f(lo),
            "hi": f(hi), "pseudo_starts": int(dry.groupby("h_h").size().max()), "signal": ok}


def stats(v) -> dict:
    v = [float(a) for a in v if a is not None and np.isfinite(a)]
    if not v:
        return {"n": 0}
    if len(v) < MIN_RISES:
        return {"n": len(v), "values": [round(a, 2) for a in sorted(v)]}
    med, lo, hi = median_ci(v, DRAWS, SEED)
    q1, q3 = np.quantile(v, [0.25, 0.75])
    return {"n": len(v), "median": round(med, 3), "lo": round(lo, 3), "hi": round(hi, 3), "q1": round(float(q1), 3),
            "q3": round(float(q3), 3)}


def site_key(station_id: str) -> str:
    """Two probes at one place (ids that differ in the last letter) are one sonde."""
    return station_id[:-1]


def pooled(ev: pd.DataFrame, keys: list[str]) -> dict:
    """Median implied speed and a Theil-Sen line of lag on distance over the Tier A rises of the sondes in `keys`,
    with 95% intervals from a bootstrap over sondes."""
    from scipy.stats import theilslopes
    r = ev[(ev["tier"] == "A") & (ev["status"] == "rise") & ev["station_id"].isin(keys) & ev["v_ms"].notna()]
    groups = [g for _, g in r.groupby("station_id")]
    rng = np.random.default_rng(SEED)
    v, slope, icpt = [], [], []
    for _ in range(DRAWS):
        b = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        v.append(b["v_ms"].median())
        if b["d_m"].nunique() > 1:
            s, i0, _, _ = theilslopes(b["lag_h"], b["d_m"] / 1000.0)
            slope.append(s); icpt.append(i0)
    s, i0, _, _ = theilslopes(r["lag_h"], r["d_m"] / 1000.0)
    q = lambda a: [round(float(z), 4) for z in np.quantile(a, [0.025, 0.975])]  # noqa: E731
    return {"sondes": len(groups), "rises": len(r), "median_v_ms": round(float(r["v_ms"].median()), 4), "v_ci": q(v),
            "excludes_model_speed": bool(not (q(v)[0] <= MODEL_MS <= q(v)[1])),
            "slope_h_per_km": round(float(s), 4), "slope_ci": q(slope), "intercept_h": round(float(i0), 3),
            "intercept_ci": q(icpt), "model_slope_h_per_km": round(1000 / MODEL_MS / 3600, 4)}


SPILL_BANDS = ((0.0, 1.0, "under 1 h"), (1.0, 6.0, "1 to 6 h"), (6.0, np.inf, "6 h or more"))


def by_spill_length(a: pd.DataFrame) -> list[dict]:
    """Amendment 2, description only: the Tier A rise share by the length of the anchor's spill, beside the
    background share at the same sondes and horizons, with a 95% interval for the difference (bootstrap over
    sondes)."""
    a = a[a["status"].isin(["rise", "no rise"]) & a["p0"].notna()]
    out = []
    for lo, hi, name in SPILL_BANDS:
        g = a[(a["spill_h"] >= lo) & (a["spill_h"] < hi)]
        row = {"band": name, "events": len(g), "sondes": int(g["station_id"].nunique()) if len(g) else 0}
        if len(g):
            rise = (g["status"] == "rise").to_numpy(dtype=float)
            row.update(rises=int(rise.sum()), rise_share=round(float(rise.mean()), 3),
                       background_share=round(float(g["p0"].mean()), 3))
            groups = [x for _, x in g.groupby("station_id")]
            rng = np.random.default_rng(SEED)
            diffs = []
            for _ in range(DRAWS):
                b = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
                diffs.append((b["status"] == "rise").mean() - b["p0"].mean())
            row["diff_ci"] = [round(float(z), 3) for z in np.quantile(diffs, [0.025, 0.975])]
        out.append(row)
    return out


def main(stations_csv: str, readings_dir: str, out_dir: str, mode: str = "stated") -> None:
    assert mode in ("stated", "amended"), mode
    amended = mode == "amended"
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stations = [r for r in csv.DictReader(open(stations_csv)) if r["fetch"] == "True"]
    net = RiverNetwork.load()
    overflows = pd.read_parquet(config.PROCESSED / "overflows.parquet")
    events = load_events()
    monitored = set(events["site_id"])
    events = events[events["site_id"].isin(set(overflows["site_id"]))]
    by_site = {k: g for k, g in events.groupby("site_id")}

    all_ev, per = [], []
    for s in stations:
        sid = s["station_id"]
        det, first, last, n_rows, n_valid = read_series(Path(readings_dir) / f"{s['measure']}.csv", mode)
        row = {"station_id": sid, "site": site_key(sid), "label": s["label"], "watercourse": s["watercourse"],
               "artificial_channel": s["artificial_channel"] == "True", "readings": n_rows,
               "valid_readings": n_valid, "first": iso(first) if det else "", "last": iso(last) if det else ""}
        if det is None:
            per.append({**row, "note": "no readings in 2024-25"}); continue
        up, timing, why, _ = upstream_tables(net, overflows, monitored, float(s["lon"]), float(s["lat"]), s["river"] or None)
        assert why is None, (sid, why)
        sp = pd.concat([by_site[k] for k in up["site_id"] if k in by_site], ignore_index=True)
        sp = sp.merge(up[["site_id", "d_m"]], on="site_id")
        lake_sites = set(up.loc[up["lake_distance_m"] > 0, "site_id"])
        ev = pd.DataFrame(events_for(sp, timing, lake_sites, det, QUIET_H, amended))
        ev24 = pd.DataFrame(events_for(sp, timing, lake_sites, det, 24.0, amended))
        for frame in (ev, ev24):     # all-None columns come out as object; the sums below need numbers
            for c in ("lag_h", "peak_lag_h", "v_ms", "lag_h_looser", "lag_h_stricter"):
                if c in frame:
                    frame[c] = pd.to_numeric(frame[c], errors="coerce")
        row.update(monitored_upstream=len(up), timing_overflows=len(timing), events=len(ev))
        if ev.empty:
            per.append({**row, "note": "no event inside the readings"}); continue
        ev.insert(0, "station_id", sid); ev.insert(1, "site", site_key(sid))
        a = ev[ev["tier"] == "A"]
        counts = {k: int((a["status"] == k).sum()) for k in ("rise", "no rise", "raised before", "gap", "no baseline")}
        dry = dry_reference(sp, det, first, last, sorted(set(a.loc[a["status"].isin(["rise", "no rise"]), "h_h"])))
        sig = signal(a, dry)
        p0 = dry.groupby("h_h")["rise"].mean().to_dict() if len(dry) else {}
        ev["p0"] = [p0.get(h) if tr == "A" else None for h, tr in zip(ev["h_h"], ev["tier"], strict=True)]
        cad = ev["c"].dropna()
        row["reading_interval_min"] = int(cad.median()) if len(cad) else None
        rises = a[a["status"] == "rise"]
        ratio = (rises["lag_h"] / rises["travel_h"]).tolist()
        win = rises["window"].value_counts().to_dict() if len(rises) else {}
        b = ev[ev["tier"] == "B"]
        a24 = ev24[ev24["tier"] == "A"] if not ev24.empty else ev24
        row.update(tier_a=len(a), **{f"a_{k.replace(' ', '_')}": v for k, v in counts.items()},
                   tier_b=len(b), tier_b_lake=int((ev["tier"] == "B-lake").sum()),
                   d_km=stats((rises["d_m"] / 1000).tolist()), model_travel_h=stats(rises["travel_h"].tolist()),
                   lag_h=stats(rises["lag_h"].tolist()), lag_over_model=stats(ratio),
                   v_ms=stats(rises["v_ms"].tolist()), peak_lag_h=stats(rises["peak_lag_h"].tolist()),
                   window={k: int(win.get(k, 0)) for k in ("before", "inside", "after")},
                   lag_h_looser=stats(a["lag_h_looser"].tolist()), lag_h_stricter=stats(a["lag_h_stricter"].tolist()),
                   tier_b_rises=int((b["status"] == "rise").sum()) if len(b) else 0,
                   tier_b_v_ms=stats(b["v_ms"].tolist()) if len(b) else {"n": 0},
                   quiet24_tier_a=len(a24),
                   quiet24_lag_h=stats(a24.loc[a24["status"] == "rise", "lag_h"].tolist()) if len(a24) else {"n": 0},
                   dry=sig)
        per.append(row)
        all_ev.append(ev)
        print(sid, s["label"][:36].ljust(36), "A", len(a), counts, "sig", sig["signal"], flush=True)

    ev = pd.concat(all_ev, ignore_index=True) if all_ev else pd.DataFrame()
    ev.to_csv(out / "events.csv", index=False, float_format="%.4g")
    fetched = len(stations)
    with_data = [p for p in per if p["readings"]]
    natural = [p for p in per if "tier_a" in p and not p["artificial_channel"]]
    sites = {}
    for p in sorted(natural, key=lambda p: p["station_id"]):   # two probes at one place count once: the first by id
        sites.setdefault(p["site"], p)
    sig5 = [p for p in sites.values() if p["dry"]["signal"] and p["a_rise"] >= MIN_RISES]
    sig10 = [p for p in sig5 if p["a_rise"] >= 10]
    a_all = ev[(ev["tier"] == "A")] if len(ev) else ev
    nat_ids = {p["station_id"] for p in sites.values()}
    a_nat = a_all[a_all["station_id"].isin(nat_ids)] if len(ev) else ev
    rise_nat = a_nat[a_nat["status"] == "rise"] if len(ev) else ev
    summary = {
        "mode": mode, "fetched": fetched, "with_readings": len(with_data), "with_an_event": len([p for p in per if "tier_a" in p]),
        "sondes_natural_one_per_place": len(sites),
        "artificial_channel_stations": len([p for p in per if "tier_a" in p and p["artificial_channel"]]),
        "tier_a_events_natural": {k: int((a_nat["status"] == k).sum()) for k in
                                  ("rise", "no rise", "raised before", "gap", "no baseline")} if len(ev) else {},
        "sondes_with_5_rises": len([p for p in sites.values() if p["a_rise"] >= MIN_RISES]),
        "sondes_with_10_rises": len([p for p in sites.values() if p["a_rise"] >= 10]),
        "sondes_with_signal": len([p for p in sites.values() if p["dry"]["signal"]]),
        "sondes_with_signal_and_5_rises": [p["station_id"] for p in sig5],
        "sondes_with_signal_and_10_rises": [p["station_id"] for p in sig10],
        "rivers_with_signal_and_5_rises": sorted({p["watercourse"] for p in sig5}),
        "descriptive_all_tier_a_rises_natural": {
            "note": "every Tier A rise at natural-channel sondes, signal or not: a description, not a travel time",
            "lag_h": stats(rise_nat["lag_h"].tolist()) if len(ev) else {},
            "lag_over_model": stats((rise_nat["lag_h"] / rise_nat["travel_h"]).tolist()) if len(ev) else {},
            "v_ms": stats(rise_nat["v_ms"].tolist()) if len(ev) else {},
            "window": rise_nat["window"].value_counts().to_dict() if len(ev) else {},
            "same_slot_as_start": int((rise_nat["lag_h"] == 0).sum()) if len(ev) else 0},
    }
    if len(sig5) >= POOL_MIN_SONDES and len({p["watercourse"] for p in sig5}) >= POOL_MIN_RIVERS:
        summary["pooled"] = pooled(ev, [p["station_id"] for p in sig5])
        summary["pooled_10_rises"] = (pooled(ev, [p["station_id"] for p in sig10])
                                      if len(sig10) >= POOL_MIN_SONDES and len({p["watercourse"] for p in sig10}) >= POOL_MIN_RIVERS
                                      else "under 3 sondes on 2 rivers with 10 rises and a signal")
    else:
        summary["pooled"] = "not computed: under 3 sondes on 2 rivers with a signal and 5 Tier A rises"
    if amended and len(ev):
        summary["tier_a_by_spill_length_natural"] = by_spill_length(a_nat)
        summary["tier_a_events_by_reading_interval_natural"] = {
            str(int(c)): g["status"].value_counts().to_dict() for c, g in a_nat.dropna(subset=["c"]).groupby("c")}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "per_sonde.json").write_text(json.dumps(per, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
