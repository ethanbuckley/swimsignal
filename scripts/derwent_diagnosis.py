"""Derwent Water's high E. coli results: the diagnosis planned in docs/DERWENT-WATER-DIAGNOSIS-2026-11.md (plan committed
in 4489eedc before any join). Descriptive, offline; reads committed files plus United Utilities' detailed EDM event
records (data/processed/edm_events.parquet, not in git) from a scratch copy:

    DIPCAST_ROOT=<scratch root holding data/processed/edm_events.parquet> uv run python scripts/derwent_diagnosis.py

Writes docs/DERWENT-WATER-DIAGNOSIS-2026-11.json.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
ATLAS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
EVID = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
TEMP = ROOT / "data" / "research" / "lake_temperature_obs.v1.json"
EDM = Path(os.environ.get("DIPCAST_ROOT", ROOT)) / "data" / "processed" / "edm_events.parquet"
OUT = ROOT / "docs" / "DERWENT-WATER-DIAGNOSIS-2026-11.json"
SEED, DRAWS = 20261106, 2000
WINDOWS_D = (1, 3, 7, 30, 60)
DERWENT = "ukd1101-45800"
# Monitored overflows upstream of each bathing water, from the pipeline's pin and transport (lake_range_hindcast._site_up)
# on 6 Nov 2026 with the cached overflow table (network key b5724303); the plan lists Derwent's.
UPSTREAM = {
    "ukd1101-45800": ["UUP00823", "UUP01690", "UUP01875"],
    "ukd1230-45725": ["UUP01954", "UUP00534"], "ukd1230-45750": ["UUP00534", "UUP01954"],
    "ukd1230-45775": ["UUP00534", "UUP01954"],
    "ukd1203-45625": ["UUP00804", "UUP01370", "UUP00919", "UUP00114", "UUP00702", "UUP00829"],
    "ukd1203-45650": ["UUP00804", "UUP00114", "UUP00702", "UUP00829"],
    "ukd1203-45675": ["UUP00804", "UUP00114", "UUP00702", "UUP00829"],
    "ukd1203-45700": ["UUP00804", "UUP01370", "UUP00919", "UUP00114", "UUP00702", "UUP00829"],
}
LAKE = {"ukd1101-45800": "Derwent Water", **{b: "Coniston Water" for b in ("ukd1230-45725", "ukd1230-45750", "ukd1230-45775")},
        **{b: "Windermere" for b in ("ukd1203-45625", "ukd1203-45650", "ukd1203-45675", "ukd1203-45700")}}
DRY_OVER_900 = ("2025-06-30", "2025-07-09", "2025-08-14", "2025-08-22")   # fixed in the plan


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def spill_hours(ev: pd.DataFrame, ids: list[str], t: pd.Timestamp, days: float) -> float:
    """Recorded spill hours at the overflows in [t - days, t), each event clipped to the window, summed over overflows."""
    e = ev[ev["site_id"].isin(ids)]
    lo = t - pd.Timedelta(days=days)
    s = e["event_start"].clip(lower=lo)
    f = e["event_end"].clip(upper=t)
    return float(((f - s).dt.total_seconds().clip(lower=0) / 3600).sum())


def days_since(ev: pd.DataFrame, ids: list[str], t: pd.Timestamp) -> float | None:
    e = ev[ev["site_id"].isin(ids) & (ev["event_start"] < t)]
    if not len(e):
        return None
    last = min(e["event_end"].max(), t)
    return round(float((t - last).total_seconds() / 86400), 2)


def rho_ci(x, y, block, seed=SEED) -> dict:
    x, y, block = np.asarray(x, float), np.asarray(y, float), np.asarray(block)
    r = float(spearmanr(x, y).statistic)
    codes = np.unique(block)
    idx = {c: np.flatnonzero(block == c) for c in codes}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(DRAWS):
        take = np.concatenate([idx[c] for c in rng.choice(codes, len(codes))])
        if np.unique(x[take]).size > 1 and np.unique(y[take]).size > 1:
            vals.append(spearmanr(x[take], y[take]).statistic)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"rho": round(r, 3), "ci95": [round(float(lo), 3), round(float(hi), 3)], "n": int(len(x)), "blocks": int(len(codes))}


def main() -> None:
    inputs = (ATLAS, EVID, TEMP, EDM)
    before = {p.name: sha(p) for p in inputs}
    a = pd.read_csv(ATLAS)
    a = a[a["bw_id"].isin(UPSTREAM)].copy()
    a["t"] = pd.to_datetime(a["sample_time"], utc=True)
    a["year"] = a["t"].dt.year
    a["y"] = np.log10(a["ecoli"].clip(lower=1))
    a["lake"] = a["bw_id"].map(LAKE)
    a["month_block"] = a["t"].dt.strftime("%Y-%m")
    ev = pd.read_parquet(EDM)
    ev = ev[ev["site_id"].isin({i for v in UPSTREAM.values() for i in v})].copy()
    res = {"plan": "docs/DERWENT-WATER-DIAGNOSIS-2026-11.md", "plan_commit": "4489eedc", "inputs_sha256": before,
           "edm_years": sorted(int(y) for y in ev["event_start"].dt.year.unique()), "upstream": UPSTREAM}
    sp = a[a["year"] <= 2025].copy()
    for d in WINDOWS_D:
        sp[f"spill_h_{d}d"] = [spill_hours(ev, UPSTREAM[b], t, d) for b, t in zip(sp["bw_id"], sp["t"], strict=True)]
    sp["days_since_spill"] = [days_since(ev, UPSTREAM[b], t) for b, t in zip(sp["bw_id"], sp["t"], strict=True)]

    # Q1, Q2 and Q3: rank correlation of recorded spill hours with log10 E. coli, by lake
    res["rho"] = {}
    for lake, g in sp.groupby("lake"):
        res["rho"][lake] = {f"{d}d": rho_ci(g[f"spill_h_{d}d"], g["y"], g["month_block"]) for d in WINDOWS_D}
        res["rho"][lake]["samples"], res["rho"][lake]["over_900"] = int(len(g)), int((g["ecoli"] > 900).sum())
    d = sp[sp["bw_id"] == DERWENT]
    dry = d[d["t"].dt.strftime("%Y-%m-%d").isin(DRY_OVER_900)]
    assert len(dry) == 4, len(dry)
    res["dry_day_over_900"] = [{"date": t.strftime("%Y-%m-%d"), "ecoli": int(e), "spill_h_7d": round(s7, 2),
                                "spill_h_30d": round(s30, 2), "days_since_spill": ds}
                               for t, e, s7, s30, ds in zip(dry["t"], dry["ecoli"], dry["spill_h_7d"], dry["spill_h_30d"],
                                                             dry["days_since_spill"], strict=True)]
    res["dry_day_over_900_with_spill_7d"] = int((dry["spill_h_7d"] > 0).sum())
    res["derwent_samples_2024_25"] = d.assign(t=d["t"].dt.strftime("%Y-%m-%d %H:%M"))[
        ["t", "ecoli", "rain_48h", "risk_lead0", *[f"spill_h_{w}d" for w in WINDOWS_D], "days_since_spill"]].round(3).to_dict("records")
    # each lake's recorded spill hours, May-September, by season (union of its overflows)
    season = {}
    for lake in ("Derwent Water", "Coniston Water", "Windermere"):
        ids = sorted({i for b, v in UPSTREAM.items() if LAKE[b] == lake for i in v})
        for y in (2024, 2025):
            t0, t1 = pd.Timestamp(f"{y}-05-01", tz="UTC"), pd.Timestamp(f"{y}-10-01", tz="UTC")
            season.setdefault(lake, {})[str(y)] = round(spill_hours(ev, ids, t1, (t1 - t0).days), 1)
        season[lake]["overflows"] = ids
    res["season_spill_hours_may_sep"] = season
    by_overflow = {}
    for i in UPSTREAM[DERWENT]:
        for y in (2024, 2025):
            t0, t1 = pd.Timestamp(f"{y}-05-01", tz="UTC"), pd.Timestamp(f"{y}-10-01", tz="UTC")
            by_overflow.setdefault(i, {})[str(y)] = round(spill_hours(ev, [i], t1, (t1 - t0).days), 1)
        by_overflow[i]["name"] = str(ev.loc[ev["site_id"] == i, "site_name"].iloc[0]) if (ev["site_id"] == i).any() else None
    res["derwent_overflows_may_sep"] = by_overflow

    # Q4: temperature, season and enterococci at Derwent, 2024-26
    tl = [x for x in json.loads(TEMP.read_text())["lakes"] if x["wb_id"] == "GB31228965"][0]
    pts = [p["point"] for p in tl["points"]]
    crow = pts.index("NW-88010777")
    temp = pd.DataFrame(tl["readings"])
    temp = temp[temp["point"] == crow].groupby("date")["temp"].mean()
    da = a[a["bw_id"] == DERWENT].copy()
    da["date"] = da["t"].dt.tz_convert("Europe/London").dt.strftime("%Y-%m-%d")
    da["temp"] = da["date"].map(temp)
    da["doy"] = da["t"].dt.dayofyear
    ok = da["temp"].notna()
    res["temperature"] = {"matched": int(ok.sum()), "of": int(len(da)),
                          "rho_temp": rho_ci(da.loc[ok, "temp"], da.loc[ok, "y"], da.loc[ok, "month_block"]),
                          "rho_day_of_season": rho_ci(da["doy"], da["y"], da["month_block"]),
                          "monthly_median_by_year": {str(y): g.groupby(g["t"].dt.month)["temp"].median().round(1).to_dict()
                                                     for y, g in da[ok].groupby("year")},
                          "median_temp_over_900_vs_rest": [round(float(da.loc[ok & (da.ecoli > 900), "temp"].median()), 1),
                                                           round(float(da.loc[ok & (da.ecoli <= 900), "temp"].median()), 1)]}
    evs = [s for s in json.loads(EVID.read_text())["sites"] if s["bw_id"] == DERWENT][0]["samples"]
    ie = {pd.Timestamp(x["t"]).tz_convert("UTC").strftime("%Y-%m-%d %H:%M"): (x["ie"], x["ie_q"]) for x in evs}
    hi = da[da["ecoli"] > 900]
    res["enterococci_over_900"] = [{"t": t.strftime("%Y-%m-%d"), "ecoli": int(e), "enterococci": ie.get(t.strftime("%Y-%m-%d %H:%M"), (None,))[0]}
                                   for t, e in zip(hi["t"], hi["ecoli"], strict=True)]
    lo = da[da["ecoli"] <= 900]
    vals = [ie.get(t.strftime("%Y-%m-%d %H:%M"), (None,))[0] for t in lo["t"]]
    vals = [v for v in vals if v is not None]
    res["enterococci_rest_median"] = float(np.median(vals)) if vals else None

    after = {p.name: sha(p) for p in inputs}
    assert before == after
    OUT.write_text(json.dumps(res, indent=1, default=str) + "\n")
    show = {k: res[k] for k in ("rho", "dry_day_over_900", "dry_day_over_900_with_spill_7d", "season_spill_hours_may_sep",
                                "derwent_overflows_may_sep", "temperature", "enterococci_over_900", "enterococci_rest_median")}
    print(json.dumps(show, indent=1, default=str))


if __name__ == "__main__":
    main()
