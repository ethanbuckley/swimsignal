"""The forecast-air check of docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md ("Forecast-air check", stated before its
requests): Open-Meteo's forecast-API air (as the site would ask for it) against ERA5-Land at the river spots' cells.

    python -I wt_air_check.py --cache <private>/water-temperature/open-meteo --spots spots.csv spots-osm.csv \
        --out <dir> [--fetch]

Three requests per batch of at most 25 cells, through wt_fetch.OMClient.check_get (the fetch's caps, pace, retries
and stop rules): forecast with precipitation and temperature, forecast with precipitation only, and the archive.
Pass: |mean a7 difference| <= 0.5 C and RMS a7 difference <= 1.0 C.

Amendment 3 (the in-season check on the 2025 season), with --historical 2025: the Historical Forecast API's air
(archived forecast-API air) against ERA5-Land at the same cells, London days 1 May to 30 September 2025 scored, the
same measures and pass rule, two requests per batch, its own cap of 150 under the log tag check=hist2025:

    python -I wt_air_check.py --cache <private>/water-temperature/open-meteo --spots spots.csv spots-osm.csv \
        --out <dir> --historical 2025 [--fetch]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wt_fetch as wf  # noqa: E402

CHECK_CAP = 250.0
PAST_DAYS, FORECAST_DAYS = 31, 6
BIAS_MAX, RMS_MAX = 0.5, 1.0
LONDON = "Europe/London"
# Amendment 3: the in-season check on archived forecasts.
HIST_CAP, HIST_TAG = 150.0, "check=hist2025"
HIST_FIRST_LEAD_DAYS = 6       # 25 April, for early May's a7; the hourly request starts a day earlier (BST)


def weight(n_cells: int, days: int, variables: int = 1) -> float:
    """Open-Meteo's weight for a request (wt_fetch's rule): max(1, V/10 x max(1, D/14)) per location."""
    return n_cells * max(1.0, variables / 10 * max(1.0, days / 14))


def hist_window(year: int) -> dict:
    """The dates of amendment 3's requests and its scored London days."""
    first = pd.Timestamp(f"{year}-05-01") - pd.Timedelta(days=HIST_FIRST_LEAD_DAYS)
    return {"forecast_start": (first - pd.Timedelta(days=1)).date().isoformat(), "archive_start": first.date().isoformat(),
            "end": f"{year}-09-30", "scored_from": pd.Timestamp(f"{year}-05-01"), "scored_to": pd.Timestamp(f"{year}-09-30")}


def scored_only(res_fc: dict[str, pd.Series], res_ar: dict[str, pd.Series], w: dict) -> dict:
    """measures(), with a7 built on the full series (so early May has its a7) and then the daily and a7 pairs cut to
    the scored days, scored_from..scored_to; plus the a7 difference by month, which decides nothing."""
    keep = lambda s: s[(s.index >= w["scored_from"]) & (s.index <= w["scored_to"])]   # noqa: E731
    daily, seven, per_cell = [], [], {}
    for cell, f in res_fc.items():
        a = res_ar.get(cell)
        if a is None or not len(a) or not len(f):
            continue
        both = pd.concat([f.rename("f"), a.rename("a")], axis=1, join="inner").dropna()
        j = pd.concat([a7(both["f"]).rename("f"), a7(both["a"]).rename("a")], axis=1, join="inner").dropna()
        both, j = keep(both), keep(j)
        if not len(both):
            continue
        daily.append((both["f"] - both["a"]).rename(cell))
        seven.append((j["f"] - j["a"]).rename(cell))
        per_cell[cell] = float((both["f"] - both["a"]).mean())
    d = pd.concat(daily) if daily else pd.Series(dtype=float)
    s7 = pd.concat(seven) if seven else pd.Series(dtype=float)
    pc = np.array(list(per_cell.values()))
    res = {"cells_compared": len(per_cell), "daily_pairs": int(len(d)), "a7_pairs": int(len(s7)),
           "daily_mean": float(d.mean()) if len(d) else None, "daily_rms": float(np.sqrt(np.mean(d ** 2))) if len(d) else None,
           "a7_mean": float(s7.mean()) if len(s7) else None, "a7_rms": float(np.sqrt(np.mean(s7 ** 2))) if len(s7) else None,
           "cell_mean_min": float(pc.min()) if len(pc) else None, "cell_mean_max": float(pc.max()) if len(pc) else None,
           "by_month": {f"{m:02d}": {"a7_mean": float(g.mean()), "a7_rms": float(np.sqrt(np.mean(g ** 2))), "a7_pairs": int(len(g))}
                        for m, g in s7.groupby(s7.index.month)} if len(s7) else {}}
    res["pass"] = bool(len(s7) and abs(res["a7_mean"]) <= BIAS_MAX and res["a7_rms"] <= RMS_MAX)
    return res


def historical(c, cells: list[str], year: int) -> dict:
    """Amendment 3's check: two requests a batch of at most 25 cells, through c.check_get (caps, pace, retries)."""
    w = hist_window(year)
    days_fc = (pd.Timestamp(w["end"]) - pd.Timestamp(w["forecast_start"])).days + 1
    days_ar = (pd.Timestamp(w["end"]) - pd.Timestamp(w["archive_start"])).days + 1
    fc, ar = {}, {}
    for i in range(0, len(cells), 25):
        batch = cells[i:i + 25]
        lat = ",".join(x.split("_")[0] for x in batch)
        lon = ",".join(x.split("_")[1] for x in batch)
        tag = f"hist{year}_{i:03d}"
        ft = c.check_get(f"histforecast_{tag}", wf.HISTORICAL_FORECAST_URL,
                         {"latitude": lat, "longitude": lon, "start_date": w["forecast_start"], "end_date": w["end"],
                          "hourly": "temperature_2m", "timezone": "UTC"}, len(batch), weight(len(batch), days_fc), HIST_CAP, HIST_TAG)
        aa = c.check_get(f"histarchive_{tag}", wf.OM_URL,
                         {"latitude": lat, "longitude": lon, "start_date": w["archive_start"], "end_date": w["end"],
                          "daily": "temperature_2m_mean", "timezone": LONDON, "models": wf.OM_MODEL},
                         len(batch), weight(len(batch), days_ar), HIST_CAP, HIST_TAG)
        for cell, x, y in zip(batch, ft, aa, strict=True):
            fc[cell] = london_daily(x["hourly"]["time"], x["hourly"]["temperature_2m"])
            ar[cell] = pd.Series(y["daily"]["temperature_2m_mean"], index=pd.to_datetime(y["daily"]["time"]), dtype=float).dropna()
    res = scored_only(fc, ar, w)
    res.update(cells=len(cells), window=[w["scored_from"].date().isoformat(), w["scored_to"].date().isoformat()],
               requests_from=[w["forecast_start"], w["archive_start"]],
               weighted_calls=round(weight(len(cells), days_fc) + weight(len(cells), days_ar), 1))
    return res


def river_cells(spot_files: list[Path]) -> list[str]:
    s = pd.concat([pd.read_csv(f) for f in spot_files])
    r = s[s["kind"] == "river"]
    lat = np.round(np.round(r["lat"].to_numpy(float) / 0.1) * 0.1, 3) + 0.0
    lon = np.round(np.round(r["lon"].to_numpy(float) / 0.1) * 0.1, 3) + 0.0
    return sorted({f"{a:.3f}_{b:.3f}" for a, b in zip(lat, lon, strict=True)})


def london_daily(times: list[str], values: list) -> pd.Series:
    """London calendar-day means from hourly UTC values; a day counts only if every one of its hours (23, 24 or 25)
    has a value."""
    t = pd.to_datetime(times, utc=True)
    s = pd.Series(np.array(values, dtype=float), index=t).dropna()
    local = s.index.tz_convert(LONDON)
    day = local.normalize()
    g = s.groupby(day)
    out = {}
    for d, v in g:
        nxt = (d + pd.Timedelta(hours=36)).normalize()
        expected = int(round((nxt - d).total_seconds() / 3600))
        if len(v) == expected:
            out[d.tz_localize(None)] = float(v.mean())
    return pd.Series(out, dtype=float).sort_index()


def a7(s: pd.Series) -> pd.Series:
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    return full.rolling(7, min_periods=7).mean().dropna()


def measures(fc: dict[str, pd.Series], ar: dict[str, pd.Series]) -> dict:
    daily, seven = [], []
    per_cell = {}
    for cell in fc:
        f, a = fc[cell], ar.get(cell)
        if a is None or not len(a) or not len(f):
            continue
        both = pd.concat([f.rename("f"), a.rename("a")], axis=1, join="inner").dropna()
        if not len(both):
            continue
        d = both["f"] - both["a"]
        daily.append(d.to_numpy())
        f7 = a7(both["f"])
        a7_ = a7(both["a"])
        j = pd.concat([f7.rename("f"), a7_.rename("a")], axis=1, join="inner").dropna()
        seven.append((j["f"] - j["a"]).to_numpy())
        per_cell[cell] = float(d.mean())
    d = np.concatenate(daily) if daily else np.array([])
    s7 = np.concatenate(seven) if seven else np.array([])
    pc = np.array(list(per_cell.values()))
    res = {
        "cells_compared": len(per_cell), "daily_pairs": int(len(d)), "a7_pairs": int(len(s7)),
        "daily_mean": float(d.mean()) if len(d) else None, "daily_rms": float(np.sqrt(np.mean(d ** 2))) if len(d) else None,
        "a7_mean": float(s7.mean()) if len(s7) else None, "a7_rms": float(np.sqrt(np.mean(s7 ** 2))) if len(s7) else None,
        "cell_mean_min": float(pc.min()) if len(pc) else None, "cell_mean_max": float(pc.max()) if len(pc) else None,
    }
    res["pass"] = bool(len(s7) and abs(res["a7_mean"]) <= BIAS_MAX and res["a7_rms"] <= RMS_MAX)
    return res


def rain_identical(with_temp: list[dict], rain_only: list[dict]) -> dict:
    """Do the two forecast requests give the same precipitation, hour by hour, cell by cell?"""
    diffs = cells = hours = 0
    for a, b in zip(with_temp, rain_only, strict=True):
        ta, tb = a["hourly"]["time"], b["hourly"]["time"]
        pa, pb = a["hourly"]["precipitation"], b["hourly"]["precipitation"]
        cells += 1
        if ta != tb:
            diffs += 1
            continue
        hours += len(pa)
        diffs += sum(1 for x, y in zip(pa, pb, strict=True) if x != y)
    return {"cells": cells, "hours": hours, "values_or_cells_differing": diffs}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--spots", nargs="+", type=Path, required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--today", help="London date the check ran on (YYYY-MM-DD); default today")
    ap.add_argument("--historical", type=int, help="amendment 3: the in-season check on this season's archived forecasts")
    a = ap.parse_args(argv)
    cells = river_cells(a.spots)
    if a.historical:
        res = historical(wf.OMClient(a.cache, a.fetch), cells, a.historical)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / f"air_check_hist{a.historical}.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        return
    today = pd.Timestamp(a.today) if a.today else pd.Timestamp(datetime.now(UTC)).tz_convert(LONDON).normalize()
    today = pd.Timestamp(today.date())
    start, end = (today - timedelta(days=PAST_DAYS)).date().isoformat(), (today - timedelta(days=1)).date().isoformat()
    c = wf.OMClient(a.cache, a.fetch)
    fc, ar, with_t, rain_only = {}, {}, [], []
    for i in range(0, len(cells), 25):
        batch = cells[i:i + 25]
        lat = ",".join(x.split("_")[0] for x in batch)
        lon = ",".join(x.split("_")[1] for x in batch)
        tag = f"{today.date()}_{i:03d}"
        base = {"latitude": lat, "longitude": lon, "past_days": PAST_DAYS, "forecast_days": FORECAST_DAYS,
                "timezone": "UTC"}
        w = len(batch) * 1.0          # call_weight(n, 38, 2) and (n, 38, 1) and (n, 31, 1): 1 a cell each
        ft = c.check_get(f"forecast_temp_{tag}", wf.FORECAST_URL,
                         {**base, "hourly": "precipitation,temperature_2m"}, len(batch), w, CHECK_CAP)
        fr = c.check_get(f"forecast_rain_{tag}", wf.FORECAST_URL, {**base, "hourly": "precipitation"},
                         len(batch), w, CHECK_CAP)
        aa = c.check_get(f"archive_{tag}", wf.OM_URL,
                         {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                          "daily": "temperature_2m_mean", "timezone": LONDON, "models": wf.OM_MODEL},
                         len(batch), w, CHECK_CAP)
        with_t += ft
        rain_only += fr
        for cell, x, y in zip(batch, ft, aa, strict=True):
            fc[cell] = london_daily(x["hourly"]["time"], x["hourly"]["temperature_2m"])
            fc[cell] = fc[cell][fc[cell].index < today]          # past days only: ERA5-Land has no today
            ar[cell] = pd.Series(y["daily"]["temperature_2m_mean"], index=pd.to_datetime(y["daily"]["time"]),
                                 dtype=float).dropna()
    res = measures(fc, ar)
    res["rain"] = rain_identical(with_t, rain_only)
    res["cells"] = len(cells)
    res["window"] = [start, end]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "air_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
