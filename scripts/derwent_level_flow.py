"""Derwent Water: do low lake level or low outflow track its high dry-weather E. coli results? The check planned in
docs/DERWENT-WATER-DIAGNOSIS-2026-11.md ("Lake level and outflow", protocol f1bcde59, pushed before any fetch).

    uv run python scripts/derwent_level_flow.py fetch    # EA Hydrology API, at most 10 requests, ledgered
    uv run python scripts/derwent_level_flow.py run      # scores from the committed daily file

The daily series (OGL v3, Environment Agency) are committed as docs/DERWENT-WATER-DIAGNOSIS-2026-11-levelflow-daily.csv,
so `run` needs no request. Descriptive, on seen samples.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from derwent_diagnosis import rho_ci  # noqa: E402

ATLAS = ROOT / "docs" / "CONCENTRATION-STUDY-2026-11-atlas-rows.csv"
DOC = ROOT / "docs" / "DERWENT-WATER-DIAGNOSIS-2026-11"
DAILY = Path(f"{DOC}-levelflow-daily.csv")
LEDGER = Path(f"{DOC}-levelflow-ledger.json")
BASE = "https://environment.data.gov.uk/hydrology/id/measures"
MEASURES = {"level_min_m": "1d596dfe-0499-4063-bbab-8d7f97ee04c4-level-min-86400-m-qualified",   # Lodore
            "flow_m3s": "7663b8bf-5756-4c71-a6a2-727e4c7448a3-flow-m-86400-m3s-qualified"}       # Portinscale
START, END = "2024-01-01", "2026-09-30"
CAP = 10
DERWENT = "ukd1101-45800"
DRY_OVER_900 = ("2025-06-30", "2025-07-09", "2025-08-14", "2025-08-22", "2026-07-14", "2026-07-23")


def stage_fetch() -> None:
    import httpx
    led, frames = [], {}
    with httpx.Client(timeout=120, headers={"User-Agent": "swimsignal-research"}) as c:
        for name, m in MEASURES.items():
            url, params, rows = f"{BASE}/{m}/readings.json", {"mineq-date": START, "max-date": END, "_limit": 2000}, []
            offset = 0
            while True:
                if len(led) >= CAP:
                    raise SystemExit("EA request cap reached")
                r = c.get(url, params={**params, "_offset": offset})
                led.append({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "measure": m, "offset": offset,
                            "status": r.status_code})
                LEDGER.write_text(json.dumps(led, indent=1) + "\n")
                if r.status_code != 200:
                    raise SystemExit(f"stopped: HTTP {r.status_code}")
                items = r.json().get("items", [])
                rows += [{"date": i["date"], name: i.get("value"), f"{name}_quality": i.get("quality")} for i in items]
                if len(items) < params["_limit"]:
                    break
                offset += params["_limit"]
                time.sleep(1.0)
            frames[name] = pd.DataFrame(rows).drop_duplicates("date").set_index("date")
            time.sleep(1.0)
    d = frames["level_min_m"].join(frames["flow_m3s"], how="outer").sort_index()
    d.to_csv(DAILY)
    print(len(d), "days;", len(led), "requests")


def stage_run() -> None:
    daily = pd.read_csv(DAILY, parse_dates=["date"]).set_index("date")
    a = pd.read_csv(ATLAS)
    s = a[a["bw_id"] == DERWENT].copy()
    s["t"] = pd.to_datetime(s["sample_time"], utc=True).dt.tz_convert("Europe/London")
    s["day"] = pd.to_datetime(s["t"].dt.strftime("%Y-%m-%d"))
    s["y"] = np.log10(s["ecoli"].clip(lower=1))
    s["month"], s["year"] = s["day"].dt.month, s["day"].dt.year
    s["block"] = s["day"].dt.strftime("%Y-%m")
    s["level"] = s["day"].map(daily["level_min_m"])
    s["flow7"] = [daily["flow_m3s"].loc[d - pd.Timedelta(days=7):d - pd.Timedelta(days=1)].mean() for d in s["day"]]
    assert len(s) == 59
    res = {"plan": "docs/DERWENT-WATER-DIAGNOSIS-2026-11.md (Lake level and outflow)", "protocol_commit": "f1bcde59",
           "samples": int(len(s)), "missing_level": int(s["level"].isna().sum()), "missing_flow7": int(s["flow7"].isna().sum()),
           "days_in_file": int(len(daily))}
    # each measure on the samples that have it (level and flow do not cover the same days)
    res["L1"], res["L2"] = {}, {}
    for c in ("level", "flow7"):
        ok = s.dropna(subset=[c])
        res["L1"][c] = rho_ci(ok[c], ok["y"], ok["block"]) if len(ok) >= 10 else None
        adj = ok.assign(**{k: ok[k] - ok.groupby("month")[k].transform("median") for k in (c, "y")})
        res["L2"][c] = rho_ci(adj[c], adj["y"], adj["block"]) if len(ok) >= 10 else None
    ok = s
    season = daily[daily.index.month.isin([5, 6, 7, 8, 9])]
    ja = daily[daily.index.month.isin([7, 8])]
    res["L3"] = {"jul_aug_median_level": {str(y): round(float(g["level_min_m"].median()), 3) for y, g in ja.groupby(ja.index.year)},
                 "jul_aug_median_flow": {str(y): round(float(g["flow_m3s"].median()), 3) for y, g in ja.groupby(ja.index.year)},
                 "flow_q25_may_sep": round(float(season["flow_m3s"].quantile(0.25)), 3)}
    dry = s[s["day"].dt.strftime("%Y-%m-%d").isin(DRY_OVER_900)]
    assert len(dry) == 6
    res["L3"]["dry_over_900"] = [{"day": d.strftime("%Y-%m-%d"), "ecoli": int(e), "flow7": round(float(f), 3),
                                  "level": None if pd.isna(lv) else round(float(lv), 3)}
                                 for d, e, f, lv in zip(dry["day"], dry["ecoli"], dry["flow7"], dry["level"], strict=True)]
    res["L3"]["dry_over_900_below_q25"] = int((dry["flow7"] < res["L3"]["flow_q25_may_sep"]).sum())
    jl, jf = res["L3"]["jul_aug_median_level"], res["L3"]["jul_aug_median_flow"]
    l1 = any(res["L1"][k] and res["L1"][k]["rho"] <= -0.3 and res["L1"][k]["ci95"][1] < 0 for k in ("level", "flow7"))
    l2 = any(res["L2"][k] and res["L2"][k]["rho"] <= -0.2 and res["L2"][k]["ci95"][1] < 0 for k in ("level", "flow7"))
    flow_ok = all(np.isfinite(jf.get(y, np.nan)) for y in ("2024", "2025"))
    l3 = bool(flow_ok and jl["2025"] < jl["2024"] and jf["2025"] < jf["2024"] and res["L3"]["dry_over_900_below_q25"] >= 4)
    res["L3"]["computable"] = bool(flow_ok)
    res["checks"] = {"L1": bool(l1), "L2": bool(l2), "L3": bool(l3)}
    res["answer"] = ("dated input found" if l1 and l2 and l3 else "moves with the season only" if l1 and not l2
                     else "does not track" if not l1 else "mixed")
    res["by_year"] = {str(y): {"samples": int(len(g)), "over_900": int((g["ecoli"] > 900).sum()),
                               "with_level": int(g["level"].notna().sum()), "with_flow7": int(g["flow7"].notna().sum()),
                               "median_level": round(float(g["level"].median()), 3),
                               "rho_level": (round(float(spearmanr(g["level"], g["y"], nan_policy="omit").statistic), 3)
                                             if g["level"].notna().sum() >= 10 else None)}
                      for y, g in ok.groupby("year")}
    Path(f"{DOC}-levelflow.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    {"fetch": stage_fetch, "run": stage_run}[sys.argv[1]]()
