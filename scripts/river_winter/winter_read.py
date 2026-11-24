"""The read of docs/RIVER-WINTER-READ-2026-11.md: production's river E. coli chance on October to April river
samples that no model here has scored.

    export DIPCAST_ROOT=<scratch copy of data/> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<ERA5-Land cells>/cache
    python scripts/river_winter/winter_read.py counts <samples.parquet>
    python scripts/river_winter/winter_read.py selftest <samples.parquet> <RIVER-UNSEEN's held-out summer rows>
    python scripts/river_winter/winter_read.py build <samples.parquet> <out dir>
    python scripts/river_winter/winter_read.py read <out dir> <summer held-out rows> [--dev <rows.parquet>]

`counts` reads every column of the sealed table except the result. `build` joins the read half's results to rain and
exposure through river_unseen/build_rows.py, unchanged; it prints counts and drops, never a result. `read` refuses
unless the statement and these scripts are committed, then writes docs/river-winter/result.json and appends to
docs/river-winter/reads.jsonl whatever it shows. `read --dev <rows>` scores rows already seen (a test of the
script) and writes nothing under docs/.

Winter W is the year of its January: October to December of year Y belong to winter Y + 1. The read half is the
even winters. The odd winters are the reserve: their results are never loaded."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "river_unseen"))
import build_rows as br  # noqa: E402
import freeze_candidate as fc  # noqa: E402
import read as rd  # noqa: E402

STATEMENT = REPO / "docs" / "RIVER-WINTER-READ-2026-11.md"
OUT = REPO / "docs" / "river-winter"
POINTS, SYSTEMS = REPO / "docs" / "river-unseen" / "points.csv", REPO / "docs" / "river-unseen" / "systems.csv"
CANDIDATE, PRODUCTION = REPO / "docs" / "river-unseen" / "river_range_v0e.json", REPO / "data" / "processed" / "ecoli_model.json"
SEALED_SHA = "95ca8c9f5e371ff0dd99defaa542a2a1a869b75910fa7900f4293054669cae9b"
PRODUCTION_SHA = "7daf7c8e407a82ba1344ab1b925092953791c138d690d5dc18093221d49ca09c"
CANDIDATE_SHA = "3c8bfe59ad92665aa7323c0ca2c5c355d6522a5edf65bff6c5bc5229b8b446c8"
MATERIAL = "RIVER / RUNNING SURFACE WATER"
PURPOSES = {"MS", "MP", "MU", "MN", "PI", "PN"}
RHO_BAR, MIN_ROWS, MIN_MONTH_ROWS, DRAWS, SEED = 0.15, 15, 3, 2000, 20261124
MIN_POINTS, MIN_READ_ROWS = 20, 1500
FIRST_DAY = "2012-02-01"   # amendment 1: the rain on disk starts 1 January 2012 and one spill input sums 30 days
DOY = ("doy_sin", "doy_cos")
MONTH_GROUPS = {"oct_nov": (10, 11), "dec_feb": (12, 1, 2), "mar_apr": (3, 4)}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def winter_of(year, month):
    return year + (month >= 10)


def winter_mask(s: pd.DataFrame) -> pd.Series:
    """Rows the statement keeps, before the half is chosen: river water, a kept purpose, October to April, 2012-22."""
    return ((s["material"] == MATERIAL) & s["purpose_code"].isin(PURPOSES) & ~s["month"].between(5, 9)
            & (s["span"] == "held_out"))


def load_half(sealed: Path, half: str) -> pd.DataFrame:
    """The sealed table's rows for one half. Results of the other half, and of rows the statement does not keep, are
    never loaded: the mask is made from the other columns, then results are read for the chosen ids only."""
    assert half == "read", "the reserve half is not opened by this script"
    assert sha(sealed) == SEALED_SHA, "not the sealed table the statement names"
    s = without_results(sealed)
    return with_results(sealed, s[winter_mask(s) & (winter_of(s["year"], s["month"]) % 2 == 0)])


def without_results(sealed: Path) -> pd.DataFrame:
    import pyarrow.dataset as ds
    return pd.read_parquet(sealed, columns=[c for c in ds.dataset(sealed).schema.names if c != "result"])


def with_results(sealed: Path, s: pd.DataFrame) -> pd.DataFrame:
    """`s` with the result column, read for its row ids only."""
    import pyarrow.dataset as ds
    res = ds.dataset(sealed).to_table(columns=["id", "result"], filter=ds.field("id").isin(s["id"].tolist())).to_pandas()
    assert len(res) == len(s) and res["id"].is_unique
    return s.merge(res, on="id", validate="one_to_one")


def counts(sealed: Path) -> dict:
    """Row counts for both halves by set. No result is read."""
    s = without_results(sealed)
    s = s[winter_mask(s)].assign(winter=lambda d: winter_of(d["year"], d["month"]))
    pts = pd.read_csv(POINTS)
    out = {}
    for which in ("kept", "no_overflow"):
        x = s[s["point"].isin(br.which_points(pts, which)["point"])]
        for half, m in (("read", x["winter"] % 2 == 0), ("reserve", x["winter"] % 2 == 1)):
            c = x[m].groupby("point").size()
            out[f"{which}_{half}"] = {"rows": int(m.sum()), "before_first_day": int((x[m]["time"].str.slice(0, 10) < FIRST_DAY).sum()), "points": int(len(c)), "points_15_or_more": int((c >= MIN_ROWS).sum()),
                                      "rows_at_them": int(c[c >= MIN_ROWS].sum()),
                                      "by_winter": {str(int(k)): int(v) for k, v in x[m].groupby("winter").size().items()}}
    return out


def build_rows_calendar_days(samples: pd.DataFrame, net, ov, model, rain_hourly, daily) -> tuple[pd.DataFrame, dict]:
    """lake_range_hindcast.build_rows with one change (amendment 1): the hindcast's first day is found by stepping
    back whole calendar days, not multiples of 24 hours. Stepping back 24-hour blocks across a clock change lands on
    01:00 or 23:00, which either cannot be placed (October) or matches no sample day (March). May to September
    rows never cross a clock change, so they build exactly as before (`selftest`)."""
    from validate_ecoli import hindcast

    from dipcast.ingest.rainfall import grid_cell
    from dipcast.model.ecoli import rain_windows
    from dipcast.model.forecast import MAX_MISSING_SHARE
    from dipcast.model.transport import history_days
    import lake_range_hindcast as lrh
    out, drops = [], {"no_upstream": 0, "no_site_rain": 0, "rain_window": 0, "exposure_missing": 0}
    for bw_id, g in samples.groupby("bw_id"):
        s = g.iloc[0]
        try:
            _, up = lrh._site_up(net, ov, bw_id, float(s.lat), float(s.lon))
        except KeyError:
            drops["no_upstream"] += len(g)
            continue
        if not len(up):
            drops["no_upstream"] += len(g)
            continue
        cl, cn = (float(v) for v in grid_cell(float(s.lat), float(s.lon)))
        try:
            site_rain = rain_hourly.loc[(cl, cn)].set_index("time")["precip_mm"].sort_index()
        except KeyError:
            drops["no_site_rain"] += len(g)
            continue
        g = g.sort_values("sample_time").reset_index(drop=True)
        risk, miss = pd.Series(dtype=float), pd.Series(dtype=float)
        sample_days = pd.DatetimeIndex(sorted(g["day"].unique()))
        lead_days = history_days(up["travel_h"])
        for y in sorted(g["sample_time"].dt.year.unique()):   # one calendar year at a time: days stay consecutive
            sd = sample_days[sample_days.year == y]
            days = pd.date_range(sd.min() - pd.DateOffset(days=lead_days), sd.max(), freq="D")
            r, m = hindcast(up, daily, days, model)
            risk, miss = pd.concat([risk, r]), pd.concat([miss, m])
        r48, r24 = rain_windows(site_rain, pd.DatetimeIndex(g["sample_time"]))
        g["rain_48h"], g["rain_24h"] = r48, r24
        g["risk_model"] = risk.reindex(g["day"]).to_numpy()
        g["missing_share"] = miss.reindex(g["day"]).to_numpy()
        g["upstream"] = len(up)
        bad_rain = g["rain_48h"].isna() | g["rain_24h"].isna()
        drops["rain_window"] += int(bad_rain.sum())
        bad_exp = ~bad_rain & (g["risk_model"].isna() | (g["missing_share"] > MAX_MISSING_SHARE))
        drops["exposure_missing"] += int(bad_exp.sum())
        out.append(g[~bad_rain & ~bad_exp])
    return pd.concat(out, ignore_index=True), drops


def build_set(samples: pd.DataFrame, no_overflow: bool) -> tuple[pd.DataFrame, dict]:
    """build_rows.build with the calendar-day builder in place of lake_range_hindcast's."""
    sys.path.insert(0, str(HERE.parent))
    import lake_range_hindcast as lrh
    lrh.build_rows = build_rows_calendar_days
    return br.build(samples, at_points=True, no_overflow=no_overflow)


def selftest(sealed: Path, stored: Path) -> dict:
    """The summer rows RIVER-UNSEEN read on 16 November, rebuilt with the calendar-day builder and compared with the
    stored rows, input by input. Those rows are already read; nothing here is a result."""
    s = without_results(sealed)
    s = with_results(sealed, s[s["kept"] & (s["span"] == "held_out")])    # May to September rows, read on 16 November
    samples, _ = br.point_samples(s, pd.read_csv(POINTS), pd.read_csv(SYSTEMS), "held_out", "kept")
    rows, built = build_set(samples, no_overflow=False)
    m = rows.merge(pd.read_parquet(stored), on=["bw_id", "sample_time"], suffixes=("_new", "_stored"))
    return {"rows_new": int(len(rows)), "rows_matched": int(len(m)), "drops": built["drops"],
            "largest_difference": {c: float((m[c + "_new"] - m[c + "_stored"]).abs().max())
                                   for c in ("rain_48h", "rain_24h", "risk_model", "missing_share", "logit_risk")}}


def build(sealed: Path, out: Path) -> dict:
    """The read half's rows at the kept points and at the no-overflow points, built as the summer read built its rows
    apart from amendment 1's two changes: calendar-day steps, and no row sampled before FIRST_DAY."""
    s = load_half(sealed, "read")
    early = s["time"].str.slice(0, 10) < FIRST_DAY
    s = s[~early].copy()
    s["kept"] = True       # point_samples keeps rows flagged kept in the named span; the winter rule is applied above
    pts, sysm = pd.read_csv(POINTS), pd.read_csv(SYSTEMS)
    audit = {}
    for which in ("kept", "no_overflow"):
        samples, a = br.point_samples(s, pts, sysm, "held_out", which)
        rows, built = build_set(samples, no_overflow=which == "no_overflow")
        rows["season"] = winter_of(rows["sample_time"].dt.year, rows["sample_time"].dt.month)
        rows.to_parquet(out / f"winter_rows_{which}.parquet", index=False)
        a.update(built)
        a["rows_by_winter"] = {str(int(k)): int(v) for k, v in rows.groupby("season").size().items()}
        audit[which] = a
    audit["left_out_before_first_day_all_points"] = int(early.sum())
    (out / "winter_rows.audit.json").write_text(json.dumps(audit, indent=1) + "\n")
    return audit


def add_figures(d: pd.DataFrame, cand: dict, prod: dict) -> pd.DataFrame:
    """The figures scored. `z_prod` is production's river chance as deployed, as its log-odds (same order as the
    chance); `z_prod_noseason` leaves out its two day-of-year terms."""
    d = d.reset_index(drop=True).copy()
    p = rd.production_deployed(prod, d)
    d["p_prod"] = p
    d["z_prod"] = np.log(p / (1 - p))
    d["z_prod_noseason"] = d["z_prod"] - sum(prod["coef"][f] * (d[f] - prod["mean"][f]) / prod["scale"][f] for f in DOY)
    d["mu_candidate"] = fc.predict(cand, d)["mu_log10"].to_numpy()
    d["rain"] = d["lrain48"]
    d["exposure"] = d["logit_risk"]
    return d


def month_removed(d: pd.DataFrame, col: str, point: str) -> pd.DataFrame:
    """`col` and the log count with the point's mean for that calendar month taken off; point-months with fewer than
    MIN_MONTH_ROWS rows are left out."""
    g = d.groupby([point, "month"])
    keep = g[col].transform("size") >= MIN_MONTH_ROWS
    out = d.loc[keep, list(dict.fromkeys([point, "system", "season", "bw_id"]))].copy()
    out["x"] = (d[col] - g[col].transform("mean"))[keep]
    out["log_ecoli"] = (d["log_ecoli"] - g["log_ecoli"].transform("mean"))[keep]
    return out


def rho_raw(d: pd.DataFrame, col: str, point: str = "bw_id") -> float:
    return rd.rho_points(d, col, point)


def rho_month_removed(d: pd.DataFrame, col: str, point: str = "bw_id") -> float:
    return rd.rho_points(month_removed(d, col, point), "x", point)


def draws(d: pd.DataFrame, fn) -> np.ndarray:
    """`fn` on 2,000 resamples of river-system winters drawn with replacement (read.system_season_draws with this
    read's seed). `fn` takes (rows, point column)."""
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


def n_points(d: pd.DataFrame) -> int:
    return int((d.groupby("bw_id").size() >= MIN_ROWS).sum())


def figures(d: pd.DataFrame, cols=("z_prod", "mu_candidate", "rain", "exposure", "z_prod_noseason")) -> dict:
    out = {}
    for c in cols:
        if d[c].nunique() > 1:
            out[c] = {"raw": round(rho_raw(d, c), 4), "month_removed": round(rho_month_removed(d, c), 4)}
    return out


def level(d: pd.DataFrame) -> dict:
    y, p = d["over"].to_numpy(float), d["p_prod"].to_numpy(float)
    return {"rows": int(len(d)), "share_over_900": round(float(y.mean()), 4), "mean_production_chance": round(float(p.mean()), 4),
            "median_count": round(float(d["ecoli"].median()), 1), "brier_production": round(rd.brier(p, y), 4),
            "brier_own_rate_hindsight": round(rd.brier(np.full(len(y), y.mean()), y), 4)}


def score(d: pd.DataFrame, side: pd.DataFrame | None, summer: pd.DataFrame | None) -> dict:
    c1 = with_interval(d, lambda x, p: rho_raw(x, "z_prod", p))
    c2 = with_interval(d, lambda x, p: rho_month_removed(x, "z_prod", p))
    res = {"rows": int(len(d)), "points": int(d["bw_id"].nunique()), "points_15_or_more": n_points(d),
           "systems": int(d["system"].nunique()), "winters": sorted(int(s) for s in d["season"].unique()),
           "over_900": int(d["over"].sum()), "share_at_a_lab_limit": round(float(d["ecoli_qual"].isin(["<", ">"]).mean()), 4),
           "condition_1_raw": c1, "condition_1_pass": bool(c1["ci95"][0] > RHO_BAR),
           "condition_2_month_removed": c2, "condition_2_pass": bool(c2["ci95"][0] > RHO_BAR)}
    rep = {"rho_by_figure": figures(d)}
    for name, col in (("rain", "rain"), ("exposure", "exposure"), ("candidate", "mu_candidate"), ("no_season_terms", "z_prod_noseason")):
        rep[f"{name}_month_removed"] = with_interval(d, lambda x, p, c=col: rho_month_removed(x, c, p))
        rep[f"production_minus_{name}_month_removed"] = with_interval(
            d, lambda x, p, c=col: rho_month_removed(x, "z_prod", p) - rho_month_removed(x, c, p))
    rep["level"] = level(d)
    subsets = {k: d[d["month"].isin(m)] for k, m in MONTH_GROUPS.items()}
    subsets.update({"winters_to_2016": d[d["season"] <= 2016], "winters_from_2018": d[d["season"] >= 2018]})
    subsets.update({f"band_{b}": x for b, x in d.groupby("band")})
    subsets.update({f"purpose_{p}": x for p, x in d.groupby("purpose")})
    rep["subsets"] = {k: {"rows": int(len(x)), "points_15_or_more": n_points(x), **figures(x, ("z_prod", "rain", "exposure")),
                          "share_over_900": round(float(x["over"].mean()), 4)} for k, x in subsets.items() if len(x)}
    rep["leave_one_system_out"] = {str(s): {"condition_1": round(rho_raw(d[d["system"] != s], "z_prod"), 4),
                                            "condition_2": round(rho_month_removed(d[d["system"] != s], "z_prod"), 4)}
                                   for s in sorted(d["system"].unique())}
    if side is not None and len(side):
        rep["no_overflow"] = {"rows": int(len(side)), "points_15_or_more": n_points(side), "level": level(side),
                              "rho_by_figure": figures(side, ("z_prod", "rain", "z_prod_noseason")),
                              "rain_month_removed": with_interval(side, lambda x, p: rho_month_removed(x, "rain", p)),
                              "production_month_removed": with_interval(side, lambda x, p: rho_month_removed(x, "z_prod", p))}
    if summer is not None:
        same = summer[summer["bw_id"].isin(d["bw_id"].unique())]
        rep["summer_rows_already_read"] = {"all_59_points": {"rows": int(len(summer)), **figures(summer, ("z_prod", "rain", "exposure")),
                                                             "level": level(summer)},
                                           "points_of_this_read": {"rows": int(len(same)), **figures(same, ("z_prod", "rain", "exposure")),
                                                                   "level": level(same)}}
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
                            "scripts/river_winter", "scripts/river_unseen", "docs/river-unseen/river_range_v0e.json",
                            "data/processed/ecoli_model.json"], capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("the statement, the scripts or a frozen file has uncommitted changes: commit them first")
    text = STATEMENT.read_text()
    for h in (PRODUCTION_SHA, CANDIDATE_SHA, SEALED_SHA):
        if h[:8] not in text:
            raise SystemExit(f"{h[:8]} is not named in the statement")
    assert sha(PRODUCTION) == PRODUCTION_SHA and sha(CANDIDATE) == CANDIDATE_SHA, "a frozen file has changed"


def main(argv: list[str]) -> None:
    if argv[0] == "counts":
        print(json.dumps(counts(Path(argv[1])), indent=1))
        return
    if argv[0] == "selftest":
        print(json.dumps(selftest(Path(argv[1]), Path(argv[2])), indent=1))
        return
    if argv[0] == "build":
        check_committed()
        print(json.dumps(build(Path(argv[1]), Path(argv[2])), indent=1))
        return
    assert argv[0] == "read", argv[0]
    cand, prod = json.loads(CANDIDATE.read_text()), json.loads(PRODUCTION.read_text())
    if "--dev" in argv:
        d = pd.read_parquet(argv[argv.index("--dev") + 1])
        for c, v in (("system", d["bw_id"]), ("band", "seen"), ("purpose", "seen"), ("ecoli_qual", "=")):
            if c not in d:
                d[c] = v
        res = score(add_figures(d, cand, prod), None, None)
        print(json.dumps({**res, "outcome": outcome(res)}, indent=1))
        return
    check_committed()
    rows_dir, summer_p = Path(argv[1]), Path(argv[2])
    kept_p, side_p = rows_dir / "winter_rows_kept.parquet", rows_dir / "winter_rows_no_overflow.parquet"
    d = add_figures(pd.read_parquet(kept_p), cand, prod)
    side = add_figures(pd.read_parquet(side_p), cand, prod)
    summer = add_figures(pd.read_parquet(summer_p), cand, prod)
    res = score(d, side, summer)
    res["outcome"] = outcome(res)
    res["inputs"] = {"winter_rows_kept": sha(kept_p), "winter_rows_no_overflow": sha(side_p), "summer_rows": sha(summer_p),
                     "production": PRODUCTION_SHA, "candidate": CANDIDATE_SHA, "sealed_samples": SEALED_SHA}
    print(json.dumps(res, indent=1))
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps({"read_at": stamp, "commit": commit, **res}, indent=1) + "\n")
    with (OUT / "reads.jsonl").open("a") as f:
        f.write(json.dumps({"read_at": stamp, "commit": commit, "figure": "production as deployed", "half": "even winters",
                            "outcome": res["outcome"], "rows": res["rows"], "condition_1_raw": res["condition_1_raw"],
                            "condition_2_month_removed": res["condition_2_month_removed"], "inputs": res["inputs"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
