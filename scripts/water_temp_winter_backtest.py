"""The frozen-model backtest of docs/WATER-TEMP-WINTER-BACKTEST-2026-11.md: the October-April water-temperature
estimate (routes river_off_season / lake_off_season, and the same curve at clicked points) against EA spot samples
from past winters.

    uv run python -I scripts/water_temp_winter_backtest.py ea    --cache <dir> --winters 2023,2024,2025 [--fetch]
    uv run python -I scripts/water_temp_winter_backtest.py plan  --ea <dir> --points <p.parquet> [<p.parquet> ...] --out <dir>
    uv run python -I scripts/water_temp_winter_backtest.py air   --cache <dir> --plan <plan.json> --winters 2023,2024,2025 [--fetch]
    uv run python -I scripts/water_temp_winter_backtest.py score --ea <dir> --air <dir> --plan <plan.json> --points ... --out <dir>

A winter is named by the year it starts: winter 2023 is 1 October 2023 to 30 April 2024.

The caps are the record's ("Caps"), fixed before any request. EA: one in flight, 1.5 s apart, at most EA_CAP requests
and EA_MAX_BYTES in this cache's log; stop at the first 403, 429, 5xx or redirect. Open-Meteo: the Historical Forecast
API only (what the forecast API's past days are), hourly temperature_2m, the default model, batches of 25 cells, one
in flight 25 s apart, at most OM_CAP weighted calls in this cache's log, OM_HOUR_CAP in a rolling hour; any answer but
200 stops the run. Network errors (no answer) are tried again after 30, 120 and 300 s, as in the water-temperature
test's client, which this script reuses. Every answer is cached and never asked for again.

The model is read, never refitted: data/processed/water_temp_model.json and the curve in src/dipcast/model/water_temp.py,
at the hashes in the record. `score` refuses to run if either hash differs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parent
sys.path.insert(0, str(HERE / "water_temperature_model_eval"))
sys.path.insert(0, str(WORKTREE / "src"))

import wt_protocol as wp  # noqa: E402

# ---- frozen before any request (the record, "The frozen model") --------------------------------------------------
MODEL_SHA256 = "637674ae2b60631d0589a9eceec1ef4fd7fc9ed21d344c397dff7820e0e2087d"
CODE_SHA256 = "938060d0d6588c7bb0e73e5f0d815174c59d21ef6023c64808935717254a3f5a"
MODEL_FILE = WORKTREE / "data" / "processed" / "water_temp_model.json"
CODE_FILE = WORKTREE / "src" / "dipcast" / "model" / "water_temp.py"

WINTER_MONTHS = (10, 11, 12, 1, 2, 3, 4)
PRIMARY_WINTERS = (2023, 2024, 2025)
RESERVED_WINTERS = (2022,)
TYPES = ("river", "lake")

# ---- caps ----------------------------------------------------------------------------------------------------------
EA_CAP = 160                     # every EA request this backtest may make, primary and reserved winters together
EA_MAX_BYTES = 600 * 1024 * 1024
EA_MAX_PAGES = 12
OM_CAP = 1000.0                  # weighted Open-Meteo calls, primary and reserved winters together
OM_HOUR_CAP = 500.0
OM_PAUSE_S = 25.0
OM_TAG = "winter-backtest=2026-11"
CELLS_MAX = 149                  # cells asked for in each winter: 149 x 3 winters x 1.564 = 699 weighted calls
LAKE_CELLS_MAX = 75              # lakes first, by hash order, up to this; rivers fill the rest, by hash order
AIR_START = "09-23"              # UTC hours from 23 September: London days from 24 September, a7 from 30 September
AIR_END = "04-30"

# ---- scoring -------------------------------------------------------------------------------------------------------
GATE_WATERS, GATE_ROWS = 30, 300
N_BOOT, SEED = 2000, 20261106
PASS_RMSE, PASS_UPPER, FAIL_RMSE = 2.0, 2.5, 2.5
BIAS_MATERIAL = 0.5
A7_BANDS = (-math.inf, 3.0, 6.0, 9.0, math.inf)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_frozen() -> None:
    got = (sha256_file(MODEL_FILE), sha256_file(CODE_FILE))
    if got != (MODEL_SHA256, CODE_SHA256):
        raise SystemExit(f"frozen files changed: {got}")


def winter_months(winter: int) -> list[tuple[str, str]]:
    """(dateFrom, dateTo) for each month of a winter; dateTo is the first of the next month (exclusive)."""
    out = []
    for m in WINTER_MONTHS:
        y = winter if m >= 10 else winter + 1
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((f"{y}-{m:02d}-01", f"{ny}-{nm:02d}-01"))
    return out


def winter_of(date: pd.Series) -> pd.Series:
    d = pd.to_datetime(date)
    return pd.Series(np.where(d.dt.month >= 10, d.dt.year, d.dt.year - 1), index=date.index)


def cell_hash(cell: str) -> str:
    return hashlib.sha256(f"winter-backtest:{cell}".encode()).hexdigest()


# ================================================================== EA
def cmd_ea(cache: Path, winters: list[int], fetch: bool) -> None:
    import wt_fetch as wf
    c = wf.EAClient(cache, fetch, max_requests=EA_CAP, max_bytes=EA_MAX_BYTES)
    pages = rows = 0
    for w in winters:
        for date_from, date_to in winter_months(w):
            for k in range(EA_MAX_PAGES + 1):
                if k == EA_MAX_PAGES:
                    raise wf.Stop(f"{date_from}: more than {EA_MAX_PAGES} pages")
                n = wf.data_rows(c.page("fresh", date_from, date_to, k * wf.PAGE))
                pages, rows = pages + 1, rows + n
                if n < wf.PAGE:
                    break
    print(json.dumps({"pages": pages, "rows": rows, "requests_in_log": c.n, "bytes_in_log": c.bytes}), flush=True)


def read_ea(ea: Path, with_result: bool) -> pd.DataFrame:
    """The cached CSV pages. Without `with_result` the result column is never read (the plan uses only which point was
    sampled on which day)."""
    cols = ["id", "samplingPoint.notation", "phenomenonTime", "sampleMaterialType", "unit"]
    if with_result:
        cols.append("result")
    frames = []
    for f in sorted(Path(ea).glob("fresh_*.csv")):
        if f.stat().st_size == 0:
            continue
        d = pd.read_csv(f, dtype=str, usecols=lambda c: c in cols)
        if len(d):
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)


def load_points(paths: list[Path]) -> pd.DataFrame:
    """Point -> type, group, cell, sizes, from the water-temperature tests' point tables; the first table wins."""
    out = []
    for p in paths:
        d = pd.read_parquet(p)[["point", "type", "cell", "group", "upstream_km", "lake_area_km2", "how"]]
        out.append(d)
    pts = pd.concat(out, ignore_index=True).drop_duplicates("point", keep="first")
    return pts[pts["type"].isin(TYPES)].reset_index(drop=True)


def winter_rows(raw: pd.DataFrame, with_result: bool) -> tuple[pd.DataFrame, dict]:
    """One row per point and day, October to April, fresh water, Celsius, a numeric result in the live tile's range."""
    counts = {"raw": int(len(raw))}
    d = raw.drop_duplicates("id")
    counts["duplicate_id"] = int(len(raw) - len(d))
    d = d[d["sampleMaterialType"].map(wp.water_type).isin(TYPES)]
    d = d[d["unit"].astype(str).str.strip().str.upper().eq("CELSIUS")]
    if with_result:
        v = d["result"].map(wp.parse_result)
        d = d.assign(temp=v)[v.notna()]
        d = d[d["temp"].between(wp.VALUE_MIN, wp.VALUE_MAX)]
    t = pd.to_datetime(d["phenomenonTime"].astype(str).str.slice(0, 19), errors="coerce")
    d = d.assign(date=t.dt.normalize())[t.notna()]
    d = d[d["date"].dt.month.isin(WINTER_MONTHS)]
    agg = {"n_readings": ("id", "size")}
    if with_result:
        agg["temp"] = ("temp", "mean")
    out = d.groupby(["samplingPoint.notation", "date"]).agg(**agg).reset_index()
    out = out.rename(columns={"samplingPoint.notation": "point"})
    out["winter"] = winter_of(out["date"])
    counts["point_days"] = int(len(out))
    return out, counts


# ================================================================== plan
def choose_cells(rows: pd.DataFrame, pts: pd.DataFrame, winters: list[int]) -> dict:
    """The record's cell rule: cells with a primary-winter row at a known river or lake point; lake cells first in hash
    order up to LAKE_CELLS_MAX, then river cells in hash order up to CELLS_MAX in all. The same cells for every winter.
    A cell with both a lake and a river point counts as a lake cell."""
    r = rows[rows["winter"].isin(winters)].merge(pts[["point", "type", "cell"]], on="point")
    lake = sorted(r.loc[r["type"].eq("lake"), "cell"].unique(), key=cell_hash)
    river = sorted(set(r.loc[r["type"].eq("river"), "cell"].unique()) - set(lake), key=cell_hash)
    lake_pick = lake[:LAKE_CELLS_MAX]
    river_pick = river[:CELLS_MAX - len(lake_pick)]
    return {"lake_cells": lake_pick, "river_cells": river_pick, "cells": sorted(lake_pick + river_pick),
            "candidates": {"lake": len(lake), "river": len(river)}}


def air_days(winter: int) -> int:
    a = pd.Timestamp(f"{winter}-{AIR_START}")
    b = pd.Timestamp(f"{winter + 1}-{AIR_END}")
    return int((b - a).days) + 1


def cmd_plan(ea: Path, points: list[Path], out: Path) -> None:
    raw = read_ea(ea, with_result=False)
    rows, counts = winter_rows(raw, with_result=False)
    pts = load_points(points)
    plan = choose_cells(rows, pts, list(PRIMARY_WINTERS))
    days = air_days(PRIMARY_WINTERS[0])
    per_winter = sum(wp.om_weight(min(wp.OM_BATCH, len(plan["cells"]) - i), days=days)
                     for i in range(0, len(plan["cells"]), wp.OM_BATCH))
    plan.update({"counts": counts, "points_known": int(rows["point"].isin(pts["point"]).sum()),
                 "point_days_unknown_point": int((~rows["point"].isin(pts["point"])).sum()),
                 "weight_per_winter": per_winter, "weight_primary": per_winter * len(PRIMARY_WINTERS),
                 "weight_reserved": per_winter * len(RESERVED_WINTERS)})
    if plan["weight_primary"] + plan["weight_reserved"] > OM_CAP:
        raise SystemExit(f"plan over the cap: {plan['weight_primary'] + plan['weight_reserved']:.1f}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps({k: v for k, v in plan.items() if k not in ("cells", "lake_cells", "river_cells")}, indent=1))


# ================================================================== air
def cmd_air(cache: Path, plan_path: Path, winters: list[int], fetch: bool) -> None:
    import wt_fetch as wf
    plan = json.loads(plan_path.read_text())
    cells = plan["cells"]
    c = wf.OMClient(cache, fetch, total_cap=OM_CAP, day_cap=OM_CAP, hour_cap=OM_HOUR_CAP, pause_s=OM_PAUSE_S,
                    model=None)
    n = 0
    for w in winters:
        days = air_days(w)
        for i in range(0, len(cells), wp.OM_BATCH):
            batch = cells[i:i + wp.OM_BATCH]
            name = f"{w}_" + hashlib.sha1(",".join(batch).encode()).hexdigest()[:16]
            params = {"latitude": ",".join(x.split("_")[0] for x in batch),
                      "longitude": ",".join(x.split("_")[1] for x in batch),
                      "start_date": f"{w}-{AIR_START}", "end_date": f"{w + 1}-{AIR_END}",
                      "hourly": "temperature_2m", "timezone": "UTC"}
            ans = c.check_get(name, wf.HISTORICAL_FORECAST_URL, params, len(batch),
                              wp.om_weight(len(batch), days=days), OM_CAP, tag=OM_TAG)
            for a in ans:
                if "hourly" not in a or "temperature_2m" not in a["hourly"]:
                    raise wf.Stop("answer has no hourly temperature_2m: stopping")
            n += 1
    print(json.dumps({"batches": n, "spent": c.spent()}), flush=True)


def load_air(cache: Path, cells: list[str], winters: list[int]) -> dict[tuple[str, int], pd.Series]:
    """{(cell, winter): hourly UTC air series} from the cached answers."""
    out = {}
    for w in winters:
        for i in range(0, len(cells), wp.OM_BATCH):
            batch = cells[i:i + wp.OM_BATCH]
            name = f"{w}_" + hashlib.sha1(",".join(batch).encode()).hexdigest()[:16]
            f = Path(cache) / "check" / f"{name}.json"
            if not f.exists():
                continue
            for cell, a in zip(batch, json.loads(f.read_text())["answer"], strict=True):
                h = a["hourly"]
                s = pd.Series(pd.to_numeric(pd.Series(h["temperature_2m"]), errors="coerce").values,
                              index=pd.to_datetime(h["time"]).tz_localize("UTC"))
                out[(cell, w)] = s
    return out


# ================================================================== the frozen estimate
def a7_by_day(model, hourly: pd.Series) -> pd.Series:
    """The live estimate's 7-day air for every London day: water_temp.daily_air (a day counts only with all its hours),
    the model's bridge, then the mean of the 7 days to that day, all present."""
    from dipcast.model import water_temp as wt
    day = wt.daily_air(pd.DataFrame({"time": hourly.index, "air_c": hourly.values}))
    if day.empty:
        return day
    full = day.reindex(pd.date_range(day.index.min(), day.index.max(), freq="D"))
    c, d = model.bridge
    return (c + d * full).rolling(7, min_periods=7).mean()


def frozen_estimate(model, kind: str, a7: float) -> tuple[float, int]:
    """(unrounded, shown) by water_temp.estimate_any's off-season route: the type's curve in a7; shown is
    int(round(max(0, t)))."""
    from dipcast.model import water_temp as wt
    t = float(wt.mohseni(a7, *model.curves[kind]))
    return t, int(round(max(0.0, t)))


# ================================================================== scores
def two_way_boot(groups, blocks, err: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """RMSE and bias with 95% intervals from a two-way cluster bootstrap: water groups and year-months drawn with
    replacement independently; a row's weight is its group's count times its block's count."""
    gc, gu = pd.factorize(pd.Series(groups).astype(str))
    bc, bu = pd.factorize(pd.Series(blocks).astype(str))
    rng = np.random.default_rng(seed)
    e = np.asarray(err, float)
    rm, bi = np.empty(n_boot), np.empty(n_boot)
    for k in range(n_boot):
        wg = np.bincount(rng.integers(0, len(gu), len(gu)), minlength=len(gu)).astype(float)
        wb = np.bincount(rng.integers(0, len(bu), len(bu)), minlength=len(bu)).astype(float)
        w = wg[gc] * wb[bc]
        s = w.sum()
        if s == 0:
            rm[k] = bi[k] = np.nan
            continue
        rm[k] = math.sqrt(float((w * e * e).sum() / s))
        bi[k] = float((w * e).sum() / s)
    return {"rmse": float(np.sqrt(np.mean(e * e))), "rmse_lo": float(np.nanpercentile(rm, 2.5)),
            "rmse_hi": float(np.nanpercentile(rm, 97.5)), "bias": float(e.mean()),
            "bias_lo": float(np.nanpercentile(bi, 2.5)), "bias_hi": float(np.nanpercentile(bi, 97.5))}


def group_boot(groups, err: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    gc, gu = pd.factorize(pd.Series(groups).astype(str))
    e = np.asarray(err, float)
    cnt = np.bincount(gc, minlength=len(gu)).astype(float)
    sse = np.bincount(gc, weights=e * e, minlength=len(gu))
    se = np.bincount(gc, weights=e, minlength=len(gu))
    d = np.random.default_rng(seed).integers(0, len(gu), size=(n_boot, len(gu)))
    n = cnt[d].sum(1)
    rm = np.sqrt(sse[d].sum(1) / n)
    bi = se[d].sum(1) / n
    return {"rmse_lo": float(np.percentile(rm, 2.5)), "rmse_hi": float(np.percentile(rm, 97.5)),
            "bias_lo": float(np.percentile(bi, 2.5)), "bias_hi": float(np.percentile(bi, 97.5))}


def verdict(n_waters: int, n_rows: int, s: dict) -> dict:
    """The record's rule, per water type."""
    if n_waters < GATE_WATERS or n_rows < GATE_ROWS:
        v = "too few to judge"
    elif s["rmse"] <= PASS_RMSE and s["rmse_hi"] <= PASS_UPPER:
        v = "pass"
    elif s["rmse"] > FAIL_RMSE:
        v = "fail"
    else:
        v = "inconclusive"
    material = abs(s["bias"]) >= BIAS_MATERIAL and (s["bias_lo"] > 0 or s["bias_hi"] < 0)
    return {"verdict": v, "bias_material": bool(material),
            "within_c": int(math.ceil(s["rmse"])) if v == "pass" else None}


def describe(err: np.ndarray) -> dict:
    e = np.asarray(err, float)
    return {"n": int(len(e)), "rmse": float(np.sqrt(np.mean(e * e))) if len(e) else None,
            "bias": float(e.mean()) if len(e) else None, "mae": float(np.abs(e).mean()) if len(e) else None,
            "within_2": float((np.abs(e) <= 2).mean()) if len(e) else None,
            "within_3": float((np.abs(e) <= 3).mean()) if len(e) else None}


def build_rows(ea: Path, air: Path, plan: dict, points: list[Path], winters: list[int]) -> tuple[pd.DataFrame, dict]:
    from dipcast.model import water_temp as wt
    model = wt.load(MODEL_FILE)
    raw = read_ea(ea, with_result=True)
    rows, counts = winter_rows(raw, with_result=True)
    rows = rows[rows["winter"].isin(winters)]
    pts = load_points(points)
    rows = rows.merge(pts, on="point", how="inner")
    counts["point_days_known_point"] = int(len(rows))
    rows = rows[rows["cell"].isin(plan["cells"])].copy()
    counts["point_days_in_planned_cells"] = int(len(rows))
    series = load_air(air, plan["cells"], winters)
    a7s = {k: a7_by_day(model, s) for k, s in series.items()}
    a7 = []
    for cell, w, d in zip(rows["cell"], rows["winter"], rows["date"], strict=True):
        s = a7s.get((cell, int(w)))
        a7.append(float(s.get(pd.Timestamp(d), np.nan)) if s is not None else np.nan)
    rows["a7"] = a7
    counts["no_a7"] = int(rows["a7"].isna().sum())
    rows = rows[rows["a7"].notna()].copy()
    est = [frozen_estimate(model, k, a) for k, a in zip(rows["type"], rows["a7"], strict=True)]
    rows["est_raw"] = [e[0] for e in est]
    rows["est_shown"] = [e[1] for e in est]
    rows["ref_air"] = np.maximum(0.0, rows["a7"])
    rows["err"] = rows["est_shown"] - rows["temp"]
    rows["err_raw"] = rows["est_raw"] - rows["temp"]
    rows["err_air"] = rows["ref_air"] - rows["temp"]
    rows["block"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m")
    rows["month"] = pd.to_datetime(rows["date"]).dt.month
    rows["a7_band"] = pd.cut(rows["a7"], A7_BANDS, labels=["under 3", "3 to 6", "6 to 9", "9 and over"],
                             right=False).astype(str)
    rows["size_band"] = [wp.lake_band(t, a) if t == "lake" else wp.catchment_band(t, u)
                         for t, a, u in zip(rows["type"], rows["lake_area_km2"], rows["upstream_km"], strict=True)]
    counts["scored"] = int(len(rows))
    return rows, counts


def score(rows: pd.DataFrame) -> dict:
    out = {}
    for kind in TYPES:
        d = rows[rows["type"].eq(kind)]
        if d.empty:
            out[kind] = {"rows": 0, "waters": 0, "verdict": {"verdict": "too few to judge"}}
            continue
        s = two_way_boot(d["group"], d["block"], d["err"].to_numpy())
        g = group_boot(d["group"], d["err"].to_numpy())
        res = {"rows": int(len(d)), "waters": int(d["group"].nunique()), "points": int(d["point"].nunique()),
               "cells": int(d["cell"].nunique()), "months": int(d["block"].nunique()),
               "shown": {**s, **describe(d["err"])}, "shown_group_only": g,
               "unrounded": describe(d["err_raw"]), "reference_air": describe(d["err_air"]),
               "measured_mean": float(d["temp"].mean()), "estimate_mean": float(d["est_shown"].mean())}
        res["verdict"] = verdict(res["waters"], res["rows"], s)
        for col in ("winter", "month", "a7_band", "size_band"):
            res[f"by_{col}"] = {str(k): describe(v["err"]) for k, v in d.groupby(col)}
        out[kind] = res
    return out


def cmd_score(ea: Path, air: Path, plan_path: Path, points: list[Path], out: Path, winters: list[int]) -> None:
    check_frozen()
    plan = json.loads(plan_path.read_text())
    rows, counts = build_rows(ea, air, plan, points, winters)
    res = {"winters": winters, "counts": counts, "model_sha256": MODEL_SHA256, "code_sha256": CODE_SHA256,
           "scores": score(rows)}
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "rows.parquet")
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ea", "plan", "air", "score"])
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--ea", type=Path)
    ap.add_argument("--air", type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--points", type=Path, nargs="+")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--winters", default=",".join(map(str, PRIMARY_WINTERS)))
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args(argv)
    winters = [int(x) for x in a.winters.split(",")]
    if a.what == "ea":
        cmd_ea(a.cache, winters, a.fetch)
    elif a.what == "plan":
        cmd_plan(a.ea, a.points, a.out)
    elif a.what == "air":
        cmd_air(a.cache, a.plan, winters, a.fetch)
    else:
        cmd_score(a.ea, a.air, a.plan, a.points, a.out, winters)


if __name__ == "__main__":
    main()
