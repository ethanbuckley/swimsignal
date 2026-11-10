"""The Accuracy page's two simple rules, recomputed from published files (docs/SIMPLE-REFERENCES-LIVE-2026-11.md), and
the code docs/PREREGISTRATION-2027-AMENDMENT-4.md names for the 2027 secondary references.

Reads the published scored rows and the state release's forecast log and poll files, read only (no pipeline run, no
Open-Meteo call), joins each scored row to its logged forecast by overflow, day, lead and issue time, and prints
dipcast.simple_references.score's figures as JSON:

    gh release download state -p dipcast.duckdb -p live_history.parquet -p live_coverage.parquet \\
        -p poll_log.parquet -D /tmp/s
    curl -sLO https://swimsignal.co.uk/data/verification_live.csv
    uv run python scripts/simple_references.py --scored verification_live.csv --state /tmp/s --out refs.json

--to limits the target days (the page uses every day to yesterday). --interim-check instead fits each rule's chances
on the rows scored, as the interim read did (docs/INTERIM-USEFULNESS-2026-10.md), on 29 Sep to 23 Oct 2026, to check
the moved code against that record; it is not the page's rule.

The 2027 secondary references (amendment 4): chances fitted on every live row from 29 Sep 2026, scores on the primary
analysis's rows (the frozen list's overflows, the season, the frozen model's forecasts) against the season/site
climatology, with blocks from 1 May 2027:

    uv run python scripts/simple_references.py --scored verification_live.csv --state /tmp/s --to 2027-09-30 \
        --score-from 2027-05-01 --sites data/eval2027/sites.csv --climatology data/eval2027/climatology.json \
        --repo . --tag eval-2027-model --out results-2027-simple-references.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_2027 as E  # noqa: E402
from evaluate_2027 import read_published, sha256  # noqa: E402

from dipcast import simple_references as sr  # noqa: E402
from dipcast.forecast_log import DECISION_HOUR, LOCAL_TZ, load_coverage  # noqa: E402

DECISION_SQL = f"""
    SELECT site_id, issue_day, target_day, lead, epoch_ms(issued_at) AS issued_ms, rain_mm
    FROM forecast_overflows
    WHERE has_live AND coalesce(rain_available, TRUE) AND target_day BETWEEN ? AND ?
      AND (issued_at AT TIME ZONE '{LOCAL_TZ}') <= (issue_day::TIMESTAMP + INTERVAL {int(DECISION_HOUR)} HOUR)
    QUALIFY row_number() OVER (PARTITION BY site_id, issue_day, target_day ORDER BY issued_at DESC) = 1
"""
INTERIM_LAST_DAY = date(2026, 10, 23)


def scored_frame(scored: Path, con: duckdb.DuckDBPyConnection, first: date, last: date) -> tuple[pd.DataFrame, dict]:
    """The published rows as verify_live's frame (site_id, company, issue_day, target_day, lead, issued_at, p_cal,
    p_clim, y, rain_mm), each joined to the logged forecast it was scored from."""
    sc = read_published(scored)
    sc = sc[(sc["day"] >= str(first)) & (sc["day"] <= str(last))].reset_index(drop=True)
    dec = con.execute(DECISION_SQL, [first, last]).df()
    dec = dec.assign(site_id=dec["site_id"].astype(str), day=pd.to_datetime(dec["target_day"]).dt.strftime("%Y-%m-%d"))
    df = sc.assign(overflow_id=sc["overflow_id"].astype(str)).merge(
        dec[["site_id", "day", "lead", "issue_day", "issued_ms", "rain_mm"]],
        left_on=["overflow_id", "day", "lead"], right_on=["site_id", "day", "lead"], how="left")
    t = pd.to_datetime(df["issued_ms"], unit="ms", utc=True).dt.tz_convert(LOCAL_TZ)
    match = df["issued_ms"].notna() & (t.dt.strftime("%Y-%m-%dT%H:%M%:z") == df["issued_at"])
    join = {"rows": len(df), "joined": int(df["issued_ms"].notna().sum()), "issue_time_matches": int(match.sum())}
    df = df[match].reset_index(drop=True)
    fc = pd.DataFrame({"site_id": df["overflow_id"], "company": df["company"], "day": df["day"],
                       "issue_day": pd.to_datetime(df["issue_day"]).dt.date, "target_day": pd.to_datetime(df["day"]).dt.date,
                       "lead": df["lead"].astype(int), "issued_at": t[match].reset_index(drop=True),
                       "p_cal": df["forecast_calibrated"].astype(float), "p_clim": df["climatology"].astype(float),
                       "y": df["observed"].astype(int), "rain_mm": df["rain_mm"].astype(float),
                       "climatology": df["climatology"].astype(float)})
    if "version" in df:
        fc["version"] = df["version"].to_numpy()
    return fc, join


def season_rows(fc: pd.DataFrame, a) -> tuple[pd.DataFrame, dict]:
    """The 2027 primary analysis's rows marked keep (evaluate_2027.evaluate_spills' selection: the frozen list's
    overflows, the frozen model's forecasts), with the list's company and water and the season/site climatology."""
    info: dict = {}
    fc = fc.copy()
    fc["keep"] = True
    if a.sites:
        units = E.read_published(a.sites, dtype=str, keep_default_na=False)
        units = units[units["unit"] == "overflow"].set_index("id")
        inlist = fc["site_id"].isin(units.index)
        fc["keep"] &= inlist
        fc.loc[inlist, "company"] = units.loc[fc.loc[inlist, "site_id"], "company"].to_numpy()
        fc["water"] = fc["site_id"].map(units["water"])
        info["sites"] = {"file": str(a.sites), "sha256": sha256(a.sites), "rows_outside_list": int((~inlist).sum())}
    if a.climatology:
        clim = json.loads(a.climatology.read_text())
        f = clim["spill_month"]["factor"]
        month = pd.to_datetime(fc["target_day"]).dt.month.astype(str)
        fc["p_clim"] = np.clip(fc["climatology"].to_numpy() * month.map(f).astype(float).to_numpy(), E.CLIM_FLOOR, E.CLIM_CAP)
        info["climatology"] = {"file": str(a.climatology), "sha256": sha256(a.climatology), "reference": "season/site"}
    model = E.parse_stamp(a.model) if a.model else (E.frozen_hashes(a.repo, a.tag) if a.repo and a.tag else None)
    window = fc[(fc["target_day"] >= a.score_from) & fc["keep"]] if a.score_from else fc[fc["keep"]]
    kept, info["versions"] = E.split_versions(window, model, a.repo, a.tag)
    fc.loc[window.index.difference(kept.index), "keep"] = False
    return fc, info


def interim_check(fc: pd.DataFrame, rain_log: pd.DataFrame, hist, cov, polls) -> dict:
    """The interim read's in-sample fit on its own dates, scored by the moved code: skill against persistence and rain
    over 10 mm on the rows with both, all companies, leads 0 and 1-4 (point estimates)."""
    df = fc[fc["target_day"] <= INTERIM_LAST_DAY].reset_index(drop=True)
    df = df.assign(issued_ms=sr.epoch_ms(df["issued_at"]),
                   target_day=pd.to_datetime(df["target_day"]))
    r48 = sr.rain_48h(df[["site_id", "issued_ms", "target_day", "lead", "rain_mm"]], rain_log).to_numpy()
    ps = sr.persistence_status(df[["site_id", "issued_ms"]], hist, cov, polls)
    y, lead = df["y"].to_numpy(float), df["lead"].to_numpy()
    known, rain_ok = ps["known"].to_numpy(), ~np.isnan(r48)

    def fit(side, ok):
        p = np.full(len(y), np.nan)
        for k in np.unique(lead):
            for s in (True, False):
                m = ok & (lead == k) & (side == s)
                p[m] = y[m].mean() if m.any() else np.nan
        return p
    pp, pr = fit(ps["active"].to_numpy(), known), fit(r48 > sr.RAIN_MM, rain_ok)
    common = known & rain_ok
    out = {"rows": len(df), "status_known": int(known.sum()), "rain_both_days": int(rain_ok.sum()), "common": int(common.sum()),
           "lead0_active": int((common & (lead == 0) & ps["active"].to_numpy()).sum())}
    p = df["p_cal"].to_numpy()
    for lg, leads in sr.LEAD_GROUPS.items():
        m = common & np.isin(lead, leads)
        b = np.mean((p[m] - y[m]) ** 2)
        out[lg] = {"rows": int(m.sum()), "skill_persistence": float(1 - b / np.mean((pp[m] - y[m]) ** 2)),
                   "skill_rain10": float(1 - b / np.mean((pr[m] - y[m]) ** 2))}
    return out


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path, help="folder with dipcast.duckdb and the three poll files")
    ap.add_argument("--from", dest="first", type=date.fromisoformat, default=sr.FIRST_DAY)
    ap.add_argument("--to", dest="last", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    ap.add_argument("--resamples", type=int, default=sr.RESAMPLES)
    ap.add_argument("--score-from", type=date.fromisoformat, help="score from this target day (chances still fitted from --from)")
    ap.add_argument("--sites", type=Path, help="the frozen list, data/eval2027/sites.csv: score its overflows only")
    ap.add_argument("--climatology", type=Path, help="data/eval2027/climatology.json: the season/site reference")
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--tag")
    ap.add_argument("--model")
    ap.add_argument("--interim-check", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    files = ("dipcast.duckdb", "live_history.parquet", "live_coverage.parquet", "poll_log.parquet")
    before = {f: sha256(a.state / f) for f in files}
    con = duckdb.connect(str(a.state / "dipcast.duckdb"), read_only=True)
    try:
        fc, join = scored_frame(a.scored, con, a.first, a.last)
        rain_log = sr.rain_log_rows(con, a.first, a.last, sr.epoch_ms(fc["issued_at"]))
    finally:
        con.close()
    hist = pd.read_parquet(a.state / "live_history.parquet")
    cov = load_coverage(a.state / "live_coverage.parquet")
    polls = pd.read_parquet(a.state / "poll_log.parquet")
    season = {}
    if a.score_from or a.sites or a.climatology or a.model or a.tag:
        fc, season = season_rows(fc, a)
    res = (interim_check(fc, rain_log, hist, cov, polls) if a.interim_check
           else sr.score(fc, rain_log, hist, cov, polls, resamples=a.resamples, first_day=a.first, score_from=a.score_from,
                         score_to=a.last))
    if season:
        res["season"] = season
    after = {f: sha256(a.state / f) for f in files}
    out = {"inputs": {"scored": {"file": a.scored.name, "sha256": sha256(a.scored)}, **before},
           "inputs_unchanged": before == after, "join": join, "result": res}
    text = json.dumps(out, indent=1, default=float)
    if a.out:
        a.out.write_text(text + "\n")
    else:
        print(text)
    return out


if __name__ == "__main__":
    main()
