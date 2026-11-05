"""How much "right now" misses when a finished spill's record has no event end (docs/MISSING-EVENT-END-2026-10.md).

transport._counted counts a finished spill from latest_event_end alone, so a status-0 row with no end is never
counted. This replays the builds in the state's forecast_points with today's rule and with a candidate rule that
takes such a row's end to be its status_start. The rule lives here, as a wrapper that fills latest_event_end before
the unchanged transport.live_now_risk is called; nothing in the live model changes.

Run with DIPCAST_STATE set to a scratch folder holding the state release's live_latest.parquet,
live_history.parquet and dipcast.duckdb (build_overflows writes its table there):

    DIPCAST_STATE=/path/state uv run python scripts/measure_missing_event_end.py --out /path/out

One process, light: the river network, one trace of the listed spots, then small per-spot frames.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("measure_missing_event_end")

TIMES = ["status_start", "latest_event_start", "latest_event_end", "fetched_at"]
RULES = ("today", "A", "B")
# The last change to weights and travel times before the run: the transport fit (PR #248), merged at this time.
PRIMARY_FROM = pd.Timestamp("2026-10-17 09:35", tz="UTC")


def history_begin(h: pd.DataFrame) -> pd.Series:
    """When each history row's state began: its status_start, else its event start (status 1) or end (status 0),
    else the poll that saw it."""
    ev = h["latest_event_start"].where(h["status"].eq(1), h["latest_event_end"].where(h["status"].eq(0)))
    return h["status_start"].fillna(ev).fillna(h["fetched_at"])


def prepare_history(h: pd.DataFrame) -> pd.DataFrame:
    """The history with times parsed, `begin` (history_begin), sorted by site then begin, and `prev_status`:
    the status the site had before this one, NaN where the history does not show it."""
    h = h.copy()
    for c in TIMES:
        h[c] = pd.to_datetime(h[c], utc=True)
    h["begin"] = history_begin(h)
    h = h.sort_values(["site_id", "begin", "fetched_at"], kind="stable").reset_index(drop=True)
    # The status before this one: the last earlier row with another status. United Utilities lists one change
    # twice, with status starts a fraction of a second apart (UUP00418: 16:16:25.000 and 16:16:25.496 on
    # 16 Oct 2026), so the row just before can be the same status.
    before = h.groupby("site_id")["status"].shift(1)
    h["prev_status"] = before.where(h["status"].ne(before)).groupby(h["site_id"]).ffill()
    return h


def asof_state(h: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Each site's row with the largest begin at or before t (prepare_history's frame), indexed by site_id."""
    return h[h["begin"] <= t].drop_duplicates("site_id", keep="last").set_index("site_id")


def fill_missing_end(ov: pd.DataFrame, rule: str) -> pd.DataFrame:
    """`ov` with the candidate end filled in: a status-0 row with no latest_event_end takes its status_start.
    Rule 'A' fills every such row that has a status_start. Rule 'B' only those with evidence of a spill before
    it: a latest_event_start not after the status_start, or a previous status of 1 (`prev_status`).
    'today' returns `ov` as it is."""
    if rule == "today":
        return ov
    gap = pd.to_numeric(ov["status"], errors="coerce").eq(0) & ov["latest_event_end"].isna() & ov["status_start"].notna()
    if rule == "B":
        started = ov["latest_event_start"].notna() & (ov["latest_event_start"] <= ov["status_start"])
        was_on = pd.to_numeric(ov.get("prev_status", pd.Series(np.nan, index=ov.index)), errors="coerce").eq(1)
        gap &= started | was_on
    elif rule != "A":
        raise ValueError(f"unknown rule {rule!r}")
    return ov.assign(latest_event_end=ov["latest_event_end"].where(~gap, ov["status_start"]))


def group_builds(issued: pd.Series, gap_min: float = 10.0) -> pd.Series:
    """A build number for each issued_at: a new build starts after a gap of more than gap_min minutes."""
    s = pd.to_datetime(issued, utc=True).sort_values()
    new = s.diff().gt(pd.Timedelta(minutes=gap_min)).cumsum()
    return new.reindex(issued.index)


def trace(out: Path) -> pd.DataFrame:
    """site_id, weight, travel_h and distance per listed spot, with today's code, gauge off as the build. Cached."""
    cache = out / "trace.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_site
    from dipcast.model.transport import locate_pin, river_velocity, spot_hints, upstream_overflows
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import build_overflows

    net = RiverNetwork.load()
    ov_all = build_overflows(net)
    rows = []
    for r in build_site.load_spots().itertuples(index=False):
        kind, river = spot_hints(r.kind, r.river)
        pin = locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river, name=r.name)
        if pin.mode in ("none", "isolated"):
            continue
        up = upstream_overflows(net, pin, ov_all, velocity_ms=river_velocity(None))
        dist = up["distance_m"] if "distance_m" in up else np.nan
        rows.append(pd.DataFrame({"spot": r.id, "lat": float(r.lat), "lon": float(r.lon), "mode": pin.mode,
                                  "site_id": up["site_id"].astype(str), "weight": up["weight"].astype(float),
                                  "travel_h": up["travel_h"].astype(float), "distance_m": dist}))
    tr = pd.concat(rows, ignore_index=True)
    tr.to_parquet(cache, index=False)
    return tr


def spot_points(fp: pd.DataFrame, spots: pd.DataFrame, tol: float = 1e-3) -> pd.Series:
    """The spot id of each forecast_points row: the listed spot within `tol` degrees of it, else None."""
    sl, so = spots["lat"].to_numpy(), spots["lon"].to_numpy()
    keys = fp[["lat", "lon"]].drop_duplicates()
    hit = {}
    for la, lo in keys.itertuples(index=False):
        d = np.abs(sl - la) + np.abs(so - lo)
        i = int(np.argmin(d))
        hit[(la, lo)] = spots["spot"].iloc[i] if d[i] < tol else None
    return pd.Series([hit[(a, b)] for a, b in zip(fp["lat"], fp["lon"], strict=True)], index=fp.index)


def run(out: Path) -> dict:
    import duckdb

    from dipcast import config
    from dipcast.model.transport import live_now_risk, risk_label

    t0 = time.time()
    tr = trace(out)
    log.info("trace: %d spots, %d spot-overflow rows (%.0f s)", tr["spot"].nunique(), len(tr), time.time() - t0)
    h = prepare_history(pd.read_parquet(config.state_read("live_history.parquet")))
    con = duckdb.connect(str(config.state_read("dipcast.duckdb")), read_only=True)
    fp = con.sql("select issued_at, lat, lon, lead, now_risk, risk from forecast_points where lead in (0, 1)").df()
    con.close()
    fp["issued_at"] = pd.to_datetime(fp["issued_at"], utc=True)
    spots = tr[["spot", "lat", "lon"]].drop_duplicates("spot")
    fp["spot"] = spot_points(fp, spots)
    unmatched = int(fp["spot"].isna().sum())
    fp = fp.dropna(subset=["spot"])
    # One row per spot-build: lead 0 carries now_risk and today's risk; lead 1 tomorrow's.
    l0 = fp[fp["lead"].eq(0)].drop(columns="lead").rename(columns={"risk": "today_risk"})
    l1 = fp[fp["lead"].eq(1)][["issued_at", "spot", "risk"]].rename(columns={"risk": "tomorrow_risk"})
    sb = l0.merge(l1, on=["issued_at", "spot"], how="left").drop_duplicates(["issued_at", "spot"])
    sb["build"] = group_builds(sb["issued_at"])
    by_spot = {s: g.reset_index(drop=True) for s, g in tr.groupby("spot")}
    weighted = set(tr.loc[tr["weight"] > 0, "site_id"])

    res, recs = [], []
    for b, g in sb.groupby("build"):
        t = g["issued_at"].min()
        st = asof_state(h, t)
        # Records per build: status-0 rows with no end, by company.
        z = st[st["status"].eq(0) & st["latest_event_end"].isna()]
        age = (t - z["status_start"]).dt.total_seconds() / 3600
        started = z["latest_event_start"].notna() & (z["latest_event_start"] <= z["status_start"])
        evid = started | z["prev_status"].eq(1)
        stale = st[st["status"].eq(0) & st["latest_event_end"].notna() & st["latest_event_start"].notna()
                   & (st["latest_event_end"] < st["latest_event_start"])]
        for c, zc in z.groupby("company"):
            a = age.loc[zc.index]
            w = zc.index.isin(list(weighted))
            recs.append({"build": b, "t": t, "company": c, "no_end": len(zc), "with_start": int(zc["status_start"].notna().sum()),
                         "within_48h": int((a <= 48).sum()), "within_72h": int((a <= 72).sum()),
                         "within_48h_B": int(((a <= 48) & evid.loc[zc.index]).sum()),
                         "weighted_within_48h": int(((a <= 48) & w).sum()),
                         "weighted_within_48h_B": int(((a <= 48) & w & evid.loc[zc.index]).sum()),
                         "stale_end": int(stale["company"].eq(c).sum())})
        for r in g.itertuples(index=False):
            up = by_spot.get(r.spot)
            if up is None:
                continue
            s = st.reindex(up["site_id"].to_numpy())
            ov = up[["site_id", "weight", "travel_h"]].copy()
            for c in ["status", "status_start", "latest_event_start", "latest_event_end", "prev_status", "company"]:
                ov[c] = s[c].set_axis(ov.index)
            ov["status"] = pd.to_numeric(ov["status"], errors="coerce").fillna(-2)
            now = r.issued_at
            row = {"build": b, "issued_at": now, "spot": r.spot, "prod_now": r.now_risk,
                   "today_risk": r.today_risk, "tomorrow_risk": r.tomorrow_risk}
            for rule in RULES:
                o = fill_missing_end(ov, rule)
                risk, contrib = live_now_risk(o, now)
                row[f"now_{rule}"] = risk
                if rule != "today":
                    added = (contrib.to_numpy() > 0) & o["latest_event_end"].notna().to_numpy() & ov["latest_event_end"].isna().to_numpy()
                    row[f"added_{rule}"] = int(added.sum())
                    row[f"added_cos_{rule}"] = ",".join(sorted(set(o.loc[added, "company"].dropna())))
            res.append(row)
    df = pd.DataFrame(res)
    rec = pd.DataFrame(recs)
    df.to_parquet(out / "spot_builds.parquet", index=False)
    rec.to_csv(out / "records_per_build.csv", index=False)
    log.info("replayed %d spot-builds in %d builds (%.0f s); %d forecast_points rows matched no listed spot",
             len(df), df["build"].nunique(), time.time() - t0, unmatched)
    return summarise(df, rec, risk_label, unmatched)


def level_rank(labels: pd.Series) -> pd.Series:
    return labels.map({"low": 0, "moderate": 1, "high": 2, "very high": 3})


def summarise(df: pd.DataFrame, rec: pd.DataFrame, risk_label, unmatched: int) -> dict:
    out = {"unmatched_points": unmatched}
    lab = lambda s: level_rank(s.map(risk_label))  # noqa: E731
    df = df.copy()
    df["primary"] = df["issued_at"] >= PRIMARY_FROM
    df["lv_prod"] = lab(df["prod_now"].fillna(0))
    day = np.maximum(lab(df["today_risk"].fillna(0)), lab(df["tomorrow_risk"].fillna(0)))
    for rule in RULES:
        df[f"lv_{rule}"] = lab(df[f"now_{rule}"])
        df[f"head_{rule}"] = np.maximum(df[f"lv_{rule}"], day)
    for name, d in [("primary", df[df["primary"]]), ("all", df)]:
        s = {"spot_builds": len(d), "builds": int(d["build"].nunique()), "spots": int(d["spot"].nunique()),
             "from": str(d["issued_at"].min()), "to": str(d["issued_at"].max())}
        ok = d["prod_now"].notna()
        s["match_level"] = float((d.loc[ok, "lv_today"] == d.loc[ok, "lv_prod"]).mean())
        s["match_risk_0.005"] = float(((d.loc[ok, "now_today"] - d.loc[ok, "prod_now"]).abs() <= 0.005).mean())
        for rule in ("A", "B"):
            diff = d[f"now_{rule}"] - d["now_today"]
            ch = diff.abs() > 0.0005
            lvch = d[f"lv_{rule}"] != d["lv_today"]
            hdch = d[f"head_{rule}"] != d["head_today"]
            from_low = hdch & d["head_today"].eq(0)
            s[rule] = {
                "risk_changed": int(ch.sum()), "risk_changed_share": float(ch.mean()),
                "diff_p50_changed": float(diff[ch].median()) if ch.any() else 0.0,
                "diff_p90_changed": float(diff[ch].quantile(0.9)) if ch.any() else 0.0,
                "diff_max": float(diff.max()),
                "under_0.01_share": float((diff.abs() < 0.01).mean()),
                "level_changed": int(lvch.sum()), "level_changed_share": float(lvch.mean()),
                "level_changed_spots": sorted(d.loc[lvch, "spot"].unique().tolist()),
                "level_moves": {f"{a}->{b}": int(n) for (a, b), n in d.loc[lvch].groupby(["lv_today", f"lv_{rule}"]).size().items()},
                "headline_changed": int(hdch.sum()), "headline_raised_from_low": int(from_low.sum()),
                "headline_changed_spots": sorted(d.loc[hdch, "spot"].unique().tolist()),
                "companies_adding": d.loc[ch, f"added_cos_{rule}"].value_counts().to_dict(),
            }
        out[name] = s
    for name, r in [("primary", rec[rec["t"] >= PRIMARY_FROM]), ("all", rec)]:
        n = r["build"].nunique()
        per = r.groupby("company")[["no_end", "with_start", "within_48h", "within_72h", "within_48h_B",
                                    "weighted_within_48h", "weighted_within_48h_B", "stale_end"]].sum() / max(n, 1)
        out[f"records_per_build_{name}"] = per.round(2).to_dict(orient="index")
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    summary = run(a.out)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
