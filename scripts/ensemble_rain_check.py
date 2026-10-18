"""The check for docs/ENSEMBLE-RAIN-TEST-2026-11.md: the published scored live forecasts, each joined to
its row in the forecast log, which holds the three ensemble members' calibrated spill chances
(forecast_overflows.p_cal_members). Two questions on the same rows, leads 2 to 4 deciding:

- Question 1 (S1, S2): does the members' spread mark the forecasts that go wrong? Per unit of company,
  target day and lead: the spread of the members' summed chances against |observed − forecast| spills,
  and the same given the error the forecast itself expects (sum of p(1 − p)).
- Question 2 (M1-M3): is the members' mean no worse than the single forecast, by Brier score?

Off CI, by hand, after the window:

    gh release download state -p dipcast.duckdb -D /tmp/ens-state
    uv run python scripts/ensemble_rain_check.py --db /tmp/ens-state/dipcast.duckdb \\
        --start 2026-10-25 --end 2026-11-21 --out ens-check.json [--era5 overflows.parquet]

--scored defaults to the published file (https://swimsignal.co.uk/data/verification_live.csv). --era5
adds the rain comparison (reported, not deciding): ERA5-Land for the overflows' cells over the window,
from Open-Meteo's archive, about one call a cell; the overflow table gives each overflow's position.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import duckdb
import httpx
import numpy as np
import pandas as pd
from scipy.stats import rankdata

from dipcast import config
from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ

CSV_URL = "https://swimsignal.co.uk/data/verification_live.csv"
DECIDING = (2, 3, 4)       # the days the band is drawn on: 3 to 5 on the page, lead 0 being today
MIN_UNIT_ROWS = 20         # a unit (company, target day, lead) with fewer rows is left out of question 1
MIN_SPILLS = 500           # rows with a spill at the deciding leads, with members
MIN_UNITS = 300
MIN_COMPANY_SPILLS = 50    # M3 applies to a company with at least this many
SLACK = 1.02               # M2, M3: "no worse" by up to 2%
SANITY_MAE = 0.0005        # the log keeps members as 4-byte floats; the headline p is a double
MIN_MEMBER_SHARE = 0.8
N_BOOT = 2000
SEED = 20261018

# The decision forecasts, as forecast_log.select_decision_forecasts picks them (the latest issued by
# DECISION_HOUR local time on the issue day, live-fed overflows, rain present), with the members.
SQL = f"""
    WITH f AS (
        SELECT site_id, issue_day, target_day, lead, p_cal, p_cal_members, rain_mm, rain_members, issued_at,
               (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR) AS before_cutoff
        FROM forecast_overflows
        WHERE has_live AND coalesce(rain_available, TRUE) AND target_day BETWEEN ? AND ?)
    SELECT site_id, target_day, lead, p_cal, p_cal_members, rain_mm, rain_members FROM f WHERE before_cutoff
    QUALIFY row_number() OVER (PARTITION BY site_id, issue_day, target_day ORDER BY issued_at DESC) = 1
"""


def read_scored(src: str) -> pd.DataFrame:
    if src.startswith("http"):
        r = httpx.get(src, timeout=120, headers=config.EA_HEADERS, follow_redirects=True)
        r.raise_for_status()
        text = r.text
    else:
        text = Path(src).read_text(encoding="utf-8")
    return pd.read_csv(io.StringIO(text), comment="#", dtype={"overflow_id": str})


def _members(col: pd.Series, k: int = 3) -> np.ndarray:
    """A column of lists as an (n, k) array, NaN where a row has no list or not k values."""
    out = np.full((len(col), k), np.nan)
    for i, v in enumerate(col.to_numpy()):
        if isinstance(v, (list, tuple, np.ndarray)) and len(v) == k:
            out[i] = np.asarray([np.nan if x is None else x for x in v], dtype=float)
    return out


def load_rows(db: str, scored: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """The scored rows from `start` to `end`, each with its logged headline (p_db) and members (m0-m2,
    r0-r2 the members' rain). A scored row with no row in the log keeps NaN members."""
    sc = scored[(scored["day"] >= start) & (scored["day"] <= end)].copy()
    con = duckdb.connect(db, read_only=True)
    try:
        fc = con.execute(SQL, [start, end]).df()
    finally:
        con.close()
    fc["day"] = pd.to_datetime(fc["target_day"]).dt.strftime("%Y-%m-%d")
    m, r = _members(fc["p_cal_members"]), _members(fc["rain_members"])
    fc = fc.assign(overflow_id=fc["site_id"].astype(str), p_db=fc["p_cal"].astype(float),
                   **{f"m{k}": m[:, k] for k in range(3)}, **{f"r{k}": r[:, k] for k in range(3)})
    keep = ["overflow_id", "day", "lead", "p_db", "rain_mm", "m0", "m1", "m2", "r0", "r1", "r2"]
    return sc.merge(fc[keep], on=["overflow_id", "day", "lead"], how="left")


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2)) if len(y) else float("nan")


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    with np.errstate(invalid="ignore", divide="ignore"):   # a constant column: NaN, left out of the interval
        return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def partial_spearman(a: np.ndarray, b: np.ndarray, given: np.ndarray) -> float:
    """Ranks of a and of b each regressed on the rank of `given` (least squares, with an intercept),
    and the residuals correlated."""
    if len(a) < 4:
        return float("nan")
    x = np.column_stack([np.ones(len(given)), rankdata(given)])
    res = [ra - x @ np.linalg.lstsq(x, ra, rcond=None)[0] for ra in (rankdata(a), rankdata(b))]
    with np.errstate(invalid="ignore", divide="ignore"):
        return float(np.corrcoef(*res)[0, 1])


def units(rows: pd.DataFrame) -> pd.DataFrame:
    """Question 1's units: company, target day and lead, with at least MIN_UNIT_ROWS rows. H the forecast
    count of spills, O the observed, E = |O − H|, S the spread of the members' sums, V = sum p(1 − p)."""
    g = rows.assign(v=rows["p"] * (1 - rows["p"])).groupby(["company", "day", "lead"])
    u = g.agg(n=("y", "size"), H=("p", "sum"), O=("y", "sum"), V=("v", "sum"),
              s0=("m0", "sum"), s1=("m1", "sum"), s2=("m2", "sum")).reset_index()
    u = u[u["n"] >= MIN_UNIT_ROWS].copy()
    s = u[["s0", "s1", "s2"]].to_numpy()
    u["S"] = s.max(axis=1) - s.min(axis=1)
    u["E"] = (u["O"] - u["H"]).abs()
    return u.drop(columns=["s0", "s1", "s2"]).reset_index(drop=True)


def _by_day(day: pd.Series) -> tuple[np.ndarray, list[np.ndarray]]:
    days = np.unique(day.to_numpy())
    idx = {d: np.flatnonzero(day.to_numpy() == d) for d in days}
    return days, [idx[d] for d in days]


def boot(day: pd.Series, stat, n_boot: int = N_BOOT, seed: int = SEED) -> list[float]:
    """The 2.5th and 97.5th percentiles of `stat(index)` over draws of target days with replacement,
    every row or unit of a drawn day going in together."""
    days, groups = _by_day(day)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(days), len(days))
        vals.append(stat(np.concatenate([groups[i] for i in pick])))
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if len(vals) else [float("nan")] * 2


def question1(u: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    S, E, V = (u[c].to_numpy(dtype=float) for c in ("S", "E", "V"))
    out = {"units": len(u), "units_with_a_spill": int((u["O"] > 0).sum()),
           "rho": spearman(S, E), "partial_rho": partial_spearman(S, E, V), "rho_V": spearman(V, E)}
    out["rho_ci"] = boot(u["day"], lambda i: spearman(S[i], E[i]), n_boot)
    out["partial_rho_ci"] = boot(u["day"], lambda i: partial_spearman(S[i], E[i], V[i]), n_boot)
    out["S1"] = bool(out["rho"] > 0 and out["rho_ci"][0] > 0)
    out["S2"] = bool(out["partial_rho"] > 0 and out["partial_rho_ci"][0] > 0)
    return out


def question2(rows: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    y, p, mean = (rows[c].to_numpy(dtype=float) for c in ("y", "p", "mean"))
    out = {"rows": len(rows), "spills": int(y.sum()), "brier_p": brier(p, y), "brier_mean": brier(mean, y)}
    out["diff_ci"] = boot(rows["day"], lambda i: brier(mean[i], y[i]) - brier(p[i], y[i]), n_boot)
    out["by_lead"] = [{"lead": int(k), "rows": len(g), "spills": int(g["y"].sum()),
                       "brier_p": brier(g["p"].to_numpy(), g["y"].to_numpy()),
                       "brier_mean": brier(g["mean"].to_numpy(), g["y"].to_numpy())} for k, g in rows.groupby("lead")]
    out["by_company"] = [{"company": c, "rows": len(g), "spills": int(g["y"].sum()),
                          "brier_p": brier(g["p"].to_numpy(), g["y"].to_numpy()),
                          "brier_mean": brier(g["mean"].to_numpy(), g["y"].to_numpy())} for c, g in rows.groupby("company")]
    out["M1"] = bool(out["brier_mean"] <= out["brier_p"])
    out["M2_failing"] = [r["lead"] for r in out["by_lead"] if r["brier_mean"] > SLACK * r["brier_p"]]
    out["M2"] = not out["M2_failing"]
    out["M3_failing"] = [r["company"] for r in out["by_company"]
                         if r["spills"] >= MIN_COMPANY_SPILLS and r["brier_mean"] > SLACK * r["brier_p"]]
    out["M3"] = not out["M3_failing"]
    return out


def describe(rows: pd.DataFrame) -> list[dict]:
    """Per lead: how often the headline sits inside the members' range, the range's mean width, and each
    member's Brier score beside the headline's."""
    out = []
    for k, g in rows.groupby("lead"):
        m = g[["m0", "m1", "m2"]].to_numpy()
        lo, hi, p, y = m.min(axis=1), m.max(axis=1), g["p"].to_numpy(), g["y"].to_numpy()
        out.append({"lead": int(k), "rows": len(g), "inside": float(np.mean((p >= lo) & (p <= hi))),
                    "mean_width": float(np.mean(hi - lo)), "brier_p": brier(p, y),
                    "brier_members": [brier(m[:, j], y) for j in range(3)]})
    return out


def check(rows: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    """The stated sanity checks, minimum data and conditions. `rows` as load_rows gives them."""
    rows = rows.rename(columns={"observed": "y"}).assign(p=lambda d: d["forecast_calibrated"].astype(float))
    has = np.isfinite(rows[["m0", "m1", "m2"]].to_numpy()).all(axis=1)
    deciding = rows["lead"].isin(DECIDING).to_numpy()
    res = {"scored_rows": len(rows), "first_day": rows["day"].min(), "last_day": rows["day"].max(),
           "rows_with_members": int(has.sum()),
           "member_share_deciding": float(has[deciding].mean()) if deciding.any() else 0.0}
    logged = rows["p_db"].notna().to_numpy() & has
    res["sanity_mae"] = float(np.abs(rows.loc[logged, "p"] - rows.loc[logged, "p_db"]).mean()) if logged.any() else float("nan")
    res["sane"] = bool(logged.any() and res["sanity_mae"] < SANITY_MAE and res["member_share_deciding"] >= MIN_MEMBER_SHARE)
    ok = rows[has].assign(mean=lambda d: d[["m0", "m1", "m2"]].mean(axis=1))
    dec = ok[ok["lead"].isin(DECIDING)]
    u = units(dec)
    res["spills_deciding"] = int(dec["y"].sum())
    res["enough"] = bool(res["spills_deciding"] >= MIN_SPILLS and len(u) >= MIN_UNITS)
    res["question1"] = question1(u, n_boot)
    res["question2"] = question2(dec, n_boot)
    q1, q2 = res["question1"], res["question2"]
    # Reported, not deciding: each lead alone, leads 0 and 1, and where the headline sits.
    res["by_lead"] = [{"lead": int(k), "question1": question1(units(g), n_boot), "question2": question2(g, n_boot)}
                      for k, g in ok.groupby("lead")]
    res["describe"] = describe(ok)
    if not res["sane"]:
        res["band"] = res["headline"] = "stopped: a sanity check failed"
    elif not res["enough"]:
        res["band"] = res["headline"] = "too little data: extend the window by 14 days, once; then inconclusive"
    else:
        res["band"] = "stays (S1 and S2 pass)" if q1["S1"] and q1["S2"] else "comes off the page"
        res["headline"] = ("switches to the members' mean at leads 2 to 4" if q2["M1"] and q2["M2"] and q2["M3"]
                           else "stays on the single forecast")
    return res


def era5_daily(cells: list[tuple[float, float]], start: str, end: str) -> pd.DataFrame:
    """ERA5-Land hourly rain for each cell from `start` to `end`, summed over Europe/London days: the
    same days as the forecast's rain_mm. Ten cells a request, a 429 not retried."""
    from dipcast.ingest.rainfall import BATCH, _request
    frames = []
    t0 = (pd.Timestamp(start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    t1 = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for i in range(0, len(cells), BATCH):
        chunk = cells[i:i + BATCH]
        res = _request(config.OPEN_METEO_ARCHIVE, {
            "latitude": ",".join(f"{c[0]:.3f}" for c in chunk), "longitude": ",".join(f"{c[1]:.3f}" for c in chunk),
            "start_date": t0, "end_date": t1, "hourly": "precipitation", "timezone": "UTC"}, retry_429=False)
        for (cl, cn), r in zip(chunk, res if isinstance(res, list) else [res], strict=True):
            t = pd.to_datetime(r["hourly"]["time"], utc=True).tz_convert(LOCAL_TZ)
            s = pd.Series(np.asarray(r["hourly"]["precipitation"], dtype=float), index=t)
            d = s.groupby(s.index.strftime("%Y-%m-%d")).agg(lambda x: x.sum() if x.notna().sum() >= 20 else np.nan)
            frames.append(pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "day": d.index, "rain_obs": d.to_numpy()}))
    return pd.concat(frames, ignore_index=True)


def rain_check(rows: pd.DataFrame, truth: pd.DataFrame, positions: pd.DataFrame) -> list[dict]:
    """Reported, not deciding: per lead, over overflow cell-days with members, the members' rain range
    against |headline rain − ERA5-Land|, and the same given the headline rain."""
    from dipcast.ingest.rainfall import grid_cell
    pos = positions.drop_duplicates("site_id").assign(site_id=lambda d: d["site_id"].astype(str))
    cl, cn = grid_cell(pos["lat"].to_numpy(), pos["lon"].to_numpy())
    pos = pos.assign(cell_lat=cl, cell_lon=cn)[["site_id", "cell_lat", "cell_lon"]]
    x = rows.merge(pos, left_on="overflow_id", right_on="site_id").merge(truth, on=["cell_lat", "cell_lon", "day"])
    x = x.dropna(subset=["rain_mm", "rain_obs", "r0", "r1", "r2"]).drop_duplicates(["cell_lat", "cell_lon", "day", "lead"])
    out = []
    for k, g in x.groupby("lead"):
        r = g[["r0", "r1", "r2"]].to_numpy()
        spread, err, head = r.max(axis=1) - r.min(axis=1), (g["rain_mm"] - g["rain_obs"]).abs().to_numpy(), g["rain_mm"].to_numpy()
        out.append({"lead": int(k), "cell_days": len(g), "rho": spearman(spread, err),
                    "partial_rho_given_rain": partial_spearman(spread, err, head),
                    "mae_headline": float(err.mean()),
                    "mae_member_mean": float(np.abs(r.mean(axis=1) - g["rain_obs"].to_numpy()).mean())})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="dipcast.duckdb from the state release")
    ap.add_argument("--scored", default=CSV_URL)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--era5", default=None, help="an overflow table (site_id, lat, lon): adds the rain comparison")
    a = ap.parse_args()
    rows = load_rows(a.db, read_scored(a.scored), a.start, a.end)
    res = check(rows)
    if a.era5:
        pos = pd.read_parquet(a.era5, columns=["site_id", "lat", "lon"])
        from dipcast.ingest.rainfall import cells_for_sites
        ids = set(rows["overflow_id"])
        pos = pos[pos["site_id"].astype(str).isin(ids)]
        truth = era5_daily(cells_for_sites(pos["lat"], pos["lon"]), a.start, a.end)
        res["rain"] = rain_check(rows, truth, pos)
    text = json.dumps(res, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
