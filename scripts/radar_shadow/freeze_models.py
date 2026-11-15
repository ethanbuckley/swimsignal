"""Rebuild the frozen status-plus-radar fits of #697 (docs/RADAR-PLUS-STATUS-TEST-2026-11.md) for the radar shadow
(docs/RADAR-SHADOW-2026-11.md), and check each against the SHA-256 that #697's score file recorded.

    freeze_models.py <cell radar dir> <radar_publish_times.csv> <out dir>

#697 fitted every arm on all of 2025 and kept only the hashes. This builds the same rows, rain arms and status inputs
with #697's own code (imported, not edited) and fits only the 16 arms the shadow uses: R0S@H (the candidate) and PS@H
(the reference) at the eight issue hours. Each is written as <out dir>/<arm>.pkl (pickle protocol 5, the bytes #694's
model_hash hashes) and compared with #697's frozen_model_sha256. No label beyond what #697's fit read, no fold, no
score. The run stops on the first hash that differs.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import live_status_test as ls
import radar_issue_hour_eval.score as r
import radar_plus_status_eval.score as s
from dipcast import config
from dipcast.ingest.rainfall import grid_cell
from dipcast.model.features import build_site_days, daily_rain_features, spill_days
from dipcast.model.training import NINE, RAIN_DIRS, load_events, load_rain, site_years

ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "docs" / "RADAR-PLUS-STATUS-TEST-2026-11-score.json"
ARMS = [(f"{a}@{h:02d}", "P" if a == "PS" else f"R0@{h:02d}", h) for h in s.HOURS for a in ("R0S", "PS")]


def main(radar_dir: str, pub_csv: str, out_dir: str) -> None:
    radar_dir, out = Path(radar_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    want = json.loads(SCORE.read_text())["frozen_model_sha256"]

    # #697's main, to the status inputs and the scored rows, line for line
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    sites, _ = site_years(ar, ev, NINE, 2025)
    radar_cells = set.intersection(*(r.cells_in([radar_dir], f"radar_*_{m}.parquet") for m in r.RADAR_MONTHS))
    lead25 = r.cells_in([config.CACHE / d for d in RAIN_DIRS], "leads_*_2025.parquet")
    use = radar_cells & lead25
    sc = list(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True))
    sites = sites[np.array([c in use for c in sc])].reset_index(drop=True)
    cells = sorted(set(zip(*grid_cell(sites["lat"].to_numpy(), sites["lon"].to_numpy()), strict=True)))
    cells = [(round(float(a), 3), round(float(b), 3)) for a, b in cells]
    s.log(f"{len(sites)} overflows in {len(cells)} cells")

    era = daily_rain_features(load_rain(set(cells), tags=("2024", "2025", "2026", "2026a"), start="2024-11-25"))
    h = r.Hourly(radar_dir, Path(pub_csv), cells)
    all_days = pd.date_range(r.Y0, r.F1, freq="D", tz="UTC")
    cr = daily_rain_features(h.as_long(h.radar))
    p0 = daily_rain_features(h.as_long(h.f0))
    arms, _ = r.build_arms(h, all_days, cr, p0)
    names = list(arms)
    del h

    days = pd.date_range(r.Y0, r.Y1, freq="D", tz="UTC")
    base = build_site_days(sites, era, days).reset_index(drop=True)
    covered = ls.covered_years(ar, ev, [2024, 2025])
    st = s.InstantStatus(ev, base["site_id"], s.known_2024_25(base["site_id"], covered))
    labels = spill_days(ev)
    labels = labels[(labels.day >= r.Y0) & (labels.day <= r.Y1)]
    base = base.merge(labels.assign(y=1), on=["site_id", "day"], how="left")
    base["y"] = base["y"].fillna(0).astype(np.int8)
    base = base.merge(sites[["site_id", "company"]], on="site_id", how="left").reset_index(drop=True)
    ok = base[["rain_7d", "rain_30d", "api"]].notna().all(axis=1).to_numpy().copy()
    ok &= base[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
    for k in names:
        ok &= r.attach(base, arms[k])[["rain_d", "rain_d1", "rain_d2"]].notna().all(axis=1).to_numpy()
    base = base[ok].reset_index(drop=True)
    stat = {f"{hr:02d}": st.features(base["site_id"], base["day"], hr) for hr in s.HOURS}
    s.log(f"rows: {len(base)}, spill days {int(base['y'].sum())}")

    got = {}
    for k, rain_arm, hr in ARMS:
        m = s.fit_s(s.frame(base, arms, rain_arm, stat[f"{hr:02d}"]))
        data = pickle.dumps(m, protocol=5)
        got[k] = r.model_hash(m)
        (out / f"{k.replace('@', '_')}.pkl").write_bytes(data)
        s.log(f"{k}: {got[k][:16]} ({'same as' if got[k] == want[k] else 'DIFFERS FROM'} #697's {want[k][:16]})")
        if got[k] != want[k]:
            sys.exit(f"{k} does not rebuild #697's frozen model")
    (out / "frozen.json").write_text(json.dumps({"rows": int(len(base)), "spill_days": int(base["y"].sum()),
                                                 "sha256": got}, indent=1))
    print("all 16 rebuilt byte-identically")


if __name__ == "__main__":
    main(*sys.argv[1:])
