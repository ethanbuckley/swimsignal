"""The read of docs/RAIN-WORD-NO-OVERFLOW-2026-11.md: a rain-only word ("more", "about" or "less rain than usual
here in the last two days") on the reserve's October to April river samples at points with no monitored overflow
upstream.

    export DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<ERA5-Land cells for the 23 points>
    python scripts/rain_word/rain_word_read.py cuts docs/rain-word/test_cutpoints.json
    python scripts/rain_word/rain_word_read.py selftest <samples.parquet> <read-half no-overflow rows> <summer side-set rows>
    python scripts/rain_word/rain_word_read.py dev <rows.parquet> winter|summer
    python scripts/rain_word/rain_word_read.py build <samples.parquet> <out dir>
    python scripts/rain_word/rain_word_read.py read <out dir>

`cuts` reads rain only. `selftest` rebuilds rows already read (RIVER-WINTER's read half, RIVER-UNSEEN's summer side
set) and compares inputs. `dev` scores rows already read and writes nothing under docs/. `build` loads the reserve's
results for the no-overflow points' October to April rows of the odd winters, and for no other row; it prints counts
and drops, never a result. `read` refuses unless the statement, this script and the cut-points file are committed,
then writes docs/rain-word/result.json and appends to docs/rain-word/reads.jsonl whatever it shows.

Winter W is the year of its January: October to December of year Y belong to winter Y + 1. The reserve is the odd
winters 2013 to 2023 (docs/RIVER-WINTER-READ-2026-11.md)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "river_unseen"))
sys.path.insert(0, str(HERE.parent / "river_winter"))
sys.path.insert(0, str(HERE.parent))
import build_rows as br  # noqa: E402
import read as rd  # noqa: E402
import winter_read as wr  # noqa: E402

STATEMENT = REPO / "docs" / "RAIN-WORD-NO-OVERFLOW-2026-11.md"
OUT = REPO / "docs" / "rain-word"
CUTS = OUT / "test_cutpoints.json"
POINTS, SYSTEMS = wr.POINTS, wr.SYSTEMS
PRODUCTION, PRODUCTION_SHA, SEALED_SHA = wr.PRODUCTION, wr.PRODUCTION_SHA, wr.SEALED_SHA
TZ = "Europe/London"
WINTER, SUMMER = (10, 11, 12, 1, 2, 3, 4), (5, 6, 7, 8, 9)
WINDOW_END_HOUR = 12        # the page's rain: the 48 hours to midday (ecoli.SAMPLE_HOUR)
MIN_DAYS, MIN_GAP = 300, 1.0
RHO_BAR, MIN_ROWS, MIN_MONTH_ROWS, DRAWS, SEED = 0.15, 15, 3, 2000, 20261125
MIN_POINTS, MIN_READ_ROWS = 8, 700
MONTH_GROUPS = wr.MONTH_GROUPS


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ the word
def cut_points(r48: pd.Series) -> dict | None:
    """A place's cut-points from its own 48-hour rain on the days given: one third and two thirds, to 0.1 mm. None
    with fewer than MIN_DAYS days or cut-points closer than MIN_GAP mm."""
    r = r48.dropna().round(1)
    if len(r) < MIN_DAYS:
        return None
    lo, hi = (round(float(v), 1) for v in r.quantile([1 / 3, 2 / 3]))
    if hi - lo < MIN_GAP:
        return None
    return {"low": lo, "high": hi, "days": int(len(r)), "less": round(float((r < lo).mean()), 3),
            "more": round(float((r > hi).mean()), 3)}


def word(r48, low: float, high: float) -> np.ndarray:
    """-1 (less rain than usual), 0 (about usual) or 1 (more), for rain rounded to 0.1 mm as the page shows it."""
    r = np.round(np.asarray(r48, dtype=float), 1)
    return np.where(r < low, -1, np.where(r > high, 1, 0)).astype(float)


def day_rain(hourly: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    from dipcast.model.ecoli import rain_windows
    r48, _ = rain_windows(hourly, days + pd.Timedelta(hours=WINDOW_END_HOUR))
    return pd.Series(r48, index=days)


def winter_days_even() -> pd.DatetimeIndex:
    d = pd.date_range(wr.FIRST_DAY, "2022-04-30", freq="D", tz=TZ)
    return d[d.month.isin(WINTER) & ((d.year + (d.month >= 10)) % 2 == 0)]


def summer_days() -> pd.DatetimeIndex:
    d = pd.date_range("2012-05-01", "2022-09-30", freq="D", tz=TZ)
    return d[d.month.isin(SUMMER)]


def cuts(out: Path) -> dict:
    """Each no-overflow point's cut-points: winter from October to April days of the even winters (the read half's
    winters, February 2012 to April 2022), summer from May to September days of 2012 to 2022 (for the development
    figure on the summer side set only). Rain only; no sample is read."""
    from validate_ecoli import load_rain

    from dipcast.ingest.rainfall import grid_cell
    pts = br.which_points(pd.read_csv(POINTS), "no_overflow")
    hourly = load_rain().set_index(["cell_lat", "cell_lon"]).sort_index()
    out_pts, missing = {}, []
    wd, sd = winter_days_even(), summer_days()
    for p in pts.itertuples():
        cell = tuple(float(v) for v in grid_cell(float(p.lat), float(p.lon)))
        try:
            h = hourly.loc[cell].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            missing.append(p.point)
            continue
        out_pts[p.point] = {"cell": list(cell), "winter": cut_points(day_rain(h, wd)), "summer": cut_points(day_rain(h, sd))}
    doc = {"what": "Per no-overflow point (docs/RAIN-WORD-NO-OVERFLOW-2026-11.md): cut-points at one third and two thirds "
                   "of its cell's ERA5-Land rain in the 48 hours to 12:00 local. winter: October to April days of the even "
                   "winters, 1 February 2012 to 30 April 2022. summer: May to September days of 2012 to 2022. Under `low` is "
                   "less rain than usual, over `high` more, else about.",
           "min_days": MIN_DAYS, "min_gap_mm": MIN_GAP, "no_rain_cell": missing, "points": out_pts}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    return {"points": len(out_pts), "no_rain_cell": missing,
            "no_winter_cut_points": [k for k, v in out_pts.items() if v["winter"] is None]}


# ------------------------------------------------------------------------------------------------ rows
def build_rows_no_overflow(samples: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """build_rows.build's no-overflow branch, without loading the river network and overflows it does not use: the
    rain windows at the point's cell (build_rows.rows_without_overflows, unchanged), exposure 0, and the same derived
    columns."""
    from validate_ecoli import load_rain

    from dipcast.model.ecoli import THRESHOLD, features
    rain = load_rain()
    rows, drops = br.rows_without_overflows(samples, rain.set_index(["cell_lat", "cell_lon"]).sort_index())
    x = features(rows["rain_48h"], rows["rain_24h"], rows["risk_model"], np.zeros(len(rows)), rows["sample_time"])
    rows = pd.concat([rows.reset_index(drop=True), x.drop(columns=["lake"])], axis=1)
    rows["season"], rows["month"] = rows["sample_time"].dt.year, rows["sample_time"].dt.month
    rows["over"] = (rows["ecoli"] > THRESHOLD).astype(int)
    rows["log_ecoli"] = np.log10(rows["ecoli"].clip(lower=1))
    return rows, {"samples_in": int(len(samples)), "rows_out": int(len(rows)), "sites_out": int(rows["bw_id"].nunique()),
                  "drops": drops}


def compare(rows: pd.DataFrame, stored: pd.DataFrame) -> dict:
    m = rows.merge(stored, on=["bw_id", "sample_time"], suffixes=("_new", "_stored"))
    return {"rows_new": int(len(rows)), "rows_stored": int(len(stored)), "rows_matched": int(len(m)),
            "largest_difference": {c: float((m[c + "_new"] - m[c + "_stored"]).abs().max())
                                   for c in ("rain_48h", "rain_24h", "lrain48", "logit_risk", "log_ecoli")}}


def selftest(sealed: Path, read_half: Path, summer: Path) -> dict:
    """Rows already read, rebuilt by build_rows_no_overflow: RIVER-WINTER's read half at the no-overflow points (24
    November) and RIVER-UNSEEN's summer side set (16 November)."""
    pts, sysm = pd.read_csv(POINTS), pd.read_csv(SYSTEMS)
    s = wr.load_half(sealed, "read")
    s = s[s["time"].str.slice(0, 10) >= wr.FIRST_DAY].copy()
    s["kept"] = True
    samples, _ = br.point_samples(s, pts, sysm, "held_out", "no_overflow")
    out = {"read_half": compare(build_rows_no_overflow(samples)[0], pd.read_parquet(read_half))}
    t = wr.without_results(sealed)
    t = wr.with_results(sealed, t[t["kept"] & (t["span"] == "held_out")])
    samples, _ = br.point_samples(t, pts, sysm, "held_out", "no_overflow")
    out["summer_side_set"] = compare(build_rows_no_overflow(samples)[0], pd.read_parquet(summer))
    return out


def load_reserve(sealed: Path) -> pd.DataFrame:
    """The reserve's October to April rows at the 23 no-overflow points, with results for those row ids only. No
    result of any other reserve row is read."""
    assert sha(sealed) == SEALED_SHA, "not the sealed table the statement names"
    s = wr.without_results(sealed)
    pts = br.which_points(pd.read_csv(POINTS), "no_overflow")
    m = wr.winter_mask(s) & (wr.winter_of(s["year"], s["month"]) % 2 == 1) & s["point"].isin(pts["point"])
    return wr.with_results(sealed, s[m])


def build(sealed: Path, out: Path) -> dict:
    s = load_reserve(sealed)
    before = int((s["time"].str.slice(0, 10) < wr.FIRST_DAY).sum())
    s["kept"] = True       # point_samples keeps rows flagged kept in the named span; the winter rule is applied above
    samples, audit = br.point_samples(s, pd.read_csv(POINTS), pd.read_csv(SYSTEMS), "held_out", "no_overflow")
    rows, built = build_rows_no_overflow(samples)
    rows["season"] = wr.winter_of(rows["sample_time"].dt.year, rows["sample_time"].dt.month)
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "reserve_rows_no_overflow.parquet", index=False)
    audit.update(built)
    audit["rows_before_first_day"] = before
    audit["rows_by_winter"] = {str(int(k)): int(v) for k, v in rows.groupby("season").size().items()}
    audit["rows_by_point"] = {k: int(v) for k, v in rows.groupby("bw_id").size().items()}
    (out / "reserve_rows.audit.json").write_text(json.dumps(audit, indent=1) + "\n")
    return audit


# ------------------------------------------------------------------------------------------------ scoring
def add_figures(d: pd.DataFrame, cuts_doc: dict, season: str) -> pd.DataFrame:
    """`word` from each point's cut-points for `season`; rows at a point with none are dropped and counted. Also the
    continuous rain (lrain48) and production's river chance as deployed with exposure 0 (its log-odds)."""
    d = d.reset_index(drop=True).copy()
    cp = {k: v[season] for k, v in cuts_doc["points"].items() if v.get(season)}
    d = d[d["bw_id"].isin(cp)].reset_index(drop=True)
    d["word"] = pd.concat([pd.Series(word(g["rain_48h"], cp[b]["low"], cp[b]["high"]), index=g.index)
                           for b, g in d.groupby("bw_id")]).sort_index()
    d["rain"] = d["lrain48"]
    p = rd.production_deployed(json.loads(PRODUCTION.read_text()), d)
    d["p_prod"], d["z_prod"] = p, np.log(p / (1 - p))
    return d


def draws(d: pd.DataFrame, fn) -> np.ndarray:
    """`fn` on DRAWS resamples of river-system winters drawn with replacement (winter_read.draws with this seed)."""
    rng = np.random.default_rng(SEED)
    blocks = [g for _, g in d.groupby(["system", "season"])]
    out = []
    for _ in range(DRAWS):
        pick = rng.integers(0, len(blocks), len(blocks))
        out.append(fn(pd.concat([blocks[b].assign(_p=blocks[b]["bw_id"] + f"#{i}") for i, b in enumerate(pick)]), "_p"))
    return np.asarray(out, dtype=float)


def with_interval(d: pd.DataFrame, fn) -> dict:
    v = draws(d, fn)
    return {"value": round(float(fn(d, "bw_id")), 4), "ci95": [round(float(x), 4) for x in np.nanpercentile(v, [2.5, 97.5])]}


def raw(d, col, point="bw_id"):
    return rd.rho_points(d, col, point)


def month_removed(d, col, point="bw_id"):
    return rd.rho_points(wr.month_removed(d, col, point), "x", point)


def points_scored(d: pd.DataFrame, col: str = "word") -> int:
    return int(sum(1 for _, g in d.groupby("bw_id") if len(g) >= MIN_ROWS and g[col].nunique() > 1 and g["log_ecoli"].nunique() > 1))


def figures(d: pd.DataFrame, cols=("word", "rain", "z_prod")) -> dict:
    return {c: {"raw": round(raw(d, c), 4), "month_removed": round(month_removed(d, c), 4)} for c in cols if d[c].nunique() > 1}


def level(d: pd.DataFrame) -> dict:
    y = d["over"].to_numpy(float)
    by = {w: {"rows": int((d["word"] == v).sum()), "share_over_900": round(float(d.loc[d["word"] == v, "over"].mean()), 4),
              "median_count": round(float(d.loc[d["word"] == v, "ecoli"].median()), 1)}
          for w, v in (("less", -1), ("about", 0), ("more", 1)) if (d["word"] == v).any()}
    return {"rows": int(len(d)), "share_over_900": round(float(y.mean()), 4), "median_count": round(float(d["ecoli"].median()), 1),
            "mean_production_chance": round(float(d["p_prod"].mean()), 4), "by_word": by}


def score(d: pd.DataFrame) -> dict:
    c1 = with_interval(d, lambda x, p: raw(x, "word", p))
    c2 = with_interval(d, lambda x, p: month_removed(x, "word", p))
    res = {"rows": int(len(d)), "points": int(d["bw_id"].nunique()),
           "points_15_or_more": int((d.groupby("bw_id").size() >= MIN_ROWS).sum()), "points_scored": points_scored(d),
           "systems": int(d["system"].nunique()), "winters": sorted(int(s) for s in d["season"].unique()),
           "word_shares": {w: round(float((d["word"] == v).mean()), 4) for w, v in (("less", -1), ("about", 0), ("more", 1))},
           "condition_1_raw": c1, "condition_1_pass": bool(c1["ci95"][0] > RHO_BAR),
           "condition_2_month_removed": c2, "condition_2_pass": bool(c2["ci95"][0] > RHO_BAR)}
    rep = {"rho_by_figure": figures(d)}
    rep["rain_month_removed"] = with_interval(d, lambda x, p: month_removed(x, "rain", p))
    rep["production_month_removed"] = with_interval(d, lambda x, p: month_removed(x, "z_prod", p))
    rep["word_minus_rain_month_removed"] = with_interval(d, lambda x, p: month_removed(x, "word", p) - month_removed(x, "rain", p))
    rep["level"] = level(d)
    subsets = {k: d[d["month"].isin(m)] for k, m in MONTH_GROUPS.items()}
    subsets.update({"winters_to_2017": d[d["season"] <= 2017], "winters_from_2019": d[d["season"] >= 2019]})
    subsets.update({f"band_{b}": x for b, x in d.groupby("band")})
    rep["subsets"] = {k: {"rows": int(len(x)), "points_scored": points_scored(x), **figures(x, ("word", "rain")),
                          "share_over_900": round(float(x["over"].mean()), 4)} for k, x in subsets.items() if len(x)}
    rep["leave_one_system_out"] = {str(s): {"condition_1": round(raw(d[d["system"] != s], "word"), 4),
                                            "condition_2": round(month_removed(d[d["system"] != s], "word"), 4)}
                                   for s in sorted(d["system"].unique())}
    rep["by_point"] = {b: {"rows": int(len(g)), "rho_word": None if len(g) < MIN_ROWS or g["word"].nunique() < 2 else
                           round(float(spearmanr(g["word"], g["log_ecoli"])[0]), 4)} for b, g in d.groupby("bw_id")}
    res["reported"] = rep
    return res


def outcome(res: dict) -> str:
    if res["points_15_or_more"] < MIN_POINTS or res["rows"] < MIN_READ_ROWS:
        return "too few rows"
    if res["condition_1_pass"] and res["condition_2_pass"]:
        return "both pass"
    if res["condition_1_pass"]:
        return "order is the calendar: raw passes, month-removed fails"
    return "order fails"


def check_committed() -> None:
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", str(STATEMENT.relative_to(REPO)),
                            "scripts/rain_word", "scripts/river_unseen", "scripts/river_winter", str(CUTS.relative_to(REPO)),
                            "data/processed/ecoli_model.json"], capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("the statement, the scripts or the cut-points file has uncommitted changes: commit them first")
    text = STATEMENT.read_text()
    for h in (sha(CUTS), SEALED_SHA, PRODUCTION_SHA):
        if h[:8] not in text:
            raise SystemExit(f"{h[:8]} is not named in the statement")
    assert sha(PRODUCTION) == PRODUCTION_SHA, "a frozen file has changed"


def main(argv: list[str]) -> None:
    cmd = argv[0]
    if cmd == "cuts":
        print(json.dumps(cuts(Path(argv[1])), indent=1))
        return
    if cmd == "selftest":
        print(json.dumps(selftest(Path(argv[1]), Path(argv[2]), Path(argv[3])), indent=1))
        return
    if cmd == "dev":      # rows already read: a test of the script, written nowhere under docs/
        d = pd.read_parquet(argv[1])
        if "season" in d and argv[2] == "winter":
            d["season"] = wr.winter_of(d["sample_time"].dt.year, d["sample_time"].dt.month)
        res = score(add_figures(d, json.loads(CUTS.read_text()), argv[2]))
        print(json.dumps({**res, "outcome": outcome(res), "development": True}, indent=1))
        return
    if cmd == "build":
        check_committed()
        print(json.dumps(build(Path(argv[1]), Path(argv[2])), indent=1))
        return
    assert cmd == "read", cmd
    check_committed()
    rows_p = Path(argv[1]) / "reserve_rows_no_overflow.parquet"
    d = add_figures(pd.read_parquet(rows_p), json.loads(CUTS.read_text()), "winter")
    res = score(d)
    res["outcome"] = outcome(res)
    res["inputs"] = {"reserve_rows_no_overflow": sha(rows_p), "cut_points": sha(CUTS), "production": PRODUCTION_SHA,
                     "sealed_samples": SEALED_SHA}
    print(json.dumps(res, indent=1))
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps({"read_at": stamp, "commit": commit, **res}, indent=1) + "\n")
    with (OUT / "reads.jsonl").open("a") as f:
        f.write(json.dumps({"read_at": stamp, "commit": commit, "figure": "rain word, winter cut-points", "half": "odd winters (reserve), no-overflow points",
                            "outcome": res["outcome"], "rows": res["rows"], "condition_1_raw": res["condition_1_raw"],
                            "condition_2_month_removed": res["condition_2_month_removed"], "inputs": res["inputs"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
