"""docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md, stage 2: fetch the EA algae checks once, then score offline.

    stage2.py fetch <out dir> <committed features SHA-256>
        Refuses unless features.parquet hashes to the committed value, and refuses if checks.parquet exists (one
        fetch). Fetches every algae check at the 18 lake sites' sampling points since 1 May 2020 with
        ingest.wqa.fetch_algae, and writes checks.parquet and checks.sha256.
    stage2.py score <out dir> <committed features SHA-256> <checks SHA-256>
        Run under scripts/lake_distance_eval/run_offline.py (every connection refused and counted). The stop rules
        first (hashes, the level map), then the gate counts for both outcomes, then the scores. Writes score.json.

Nothing here has been run on real data. tests/test_lake_algae_sat_eval.py runs `score_frames` on synthetic frames.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import protocol as pr

ROOT = Path(__file__).resolve().parents[2]
SITES = ROOT / "data" / "raw" / "bathing_waters_inland.json"


def fetch(out: Path, features_sha: str) -> None:
    pr.check_hash(out / "features.parquet", features_sha)
    target = out / "checks.parquet"
    if target.exists():
        raise pr.StopRule("checks.parquet exists: the checks are fetched once")
    from dipcast.forecast_log import _local_times
    from dipcast.ingest.wqa import fetch_algae
    sites = pr.lake_sites(SITES)
    # A3: one sampling point a request. The service refuses several points over more than a year ("Unless querying
    # a single sampling point's observations, the maximum temporal range is 1 year", HTTP 400, 26 October 2026).
    rows = [r for p in sites["wqa_point"].tolist() for r in fetch_algae([p], "2020-05-01T00:00:00")]
    df = pd.DataFrame(rows, columns=["wqa_point", "sample_time", "result", "purpose"])
    df = df.assign(sample_time=_local_times(df["sample_time"])).dropna(subset=["sample_time"])
    df = df.sort_values(["wqa_point", "sample_time"]).reset_index(drop=True)
    df.to_parquet(target, index=False)
    h = pr.sha256(target)
    (out / "checks.sha256").write_text(h + "\n")
    print("checks fetched:", len(df), "SHA-256", h)


def pairing_table(paired: pd.DataFrame) -> list[dict]:
    t = paired.assign(has=paired["reading"].notna())
    g = t.groupby(["bw_id", "season"]).agg(checks=("has", "size"), with_reading=("has", "sum"),
                                           lag_median=("lag_days", "median"))
    return [{"bw_id": k[0], "season": int(k[1]), "checks": int(r.checks), "with_reading": int(r.with_reading),
             "lag_days_median": None if pd.isna(r.lag_median) else float(r.lag_median)} for k, r in g.iterrows()]


def score_frames(features: pd.DataFrame, checks: pd.DataFrame, sites: pd.DataFrame, sizes: dict) -> dict:
    """Everything after the stop rules: pure frames in, the report out."""
    pr.check_levels(_algae_levels())
    in_test = {k for k, v in sizes.items() if v["in_test"]}
    sites_in = sites[sites["bw_id"].isin(in_test)]
    c, dropped = pr.prepare_checks(checks, sites)
    scenes = pr.one_per_date(features[features["bw_id"].isin(in_test)])
    report = {"unknown_wording_dropped": dropped, "checks": int(len(c)),
              "checks_at_sites_in_test": int(c["bw_id"].isin(in_test).sum()),
              "sites_in_test": sorted(in_test), "sizes": sizes}
    c_in = c[c["bw_id"].isin(sites_in["bw_id"])].reset_index(drop=True)
    paired = pr.pair(c_in, scenes)
    report["pairing"] = pairing_table(paired)
    rows = paired[paired["reading"].notna()].reset_index(drop=True)
    report["rows"] = int(len(rows))
    report["gate"] = {o: pr.gate(rows, o) for o in ("A", "B")}
    report["outcomes"] = {}
    for o in ("A", "B"):
        r = pr.score_outcome(rows, o) if len(rows) and rows[o].nunique() == 2 else {"verdict": "Too few to judge"}
        if len(rows) and rows[o].nunique() == 2:
            r["auc_by_water_body"] = {wb: pr.auc(g["reading"], g[o]) for wb, g in rows.groupby("water_body")}
        report["outcomes"][o] = r
    # Description only: the 0- and 7-day windows, and statutory visits (purpose MS) at 3 days.
    desc = {}
    for w in pr.DESCRIPTION_PAIR_DAYS:
        p = pr.pair(c_in, scenes, window_days=w)
        p = p[p["reading"].notna()]
        desc[f"window_{w}"] = {o: {"rows": int(len(p)), "events": int(p[o].sum()), "auc": pr.auc(p["reading"], p[o])}
                               for o in ("A", "B")}
    ms = rows[rows["purpose"] == "MS"] if "purpose" in rows else rows.iloc[0:0]
    desc["statutory_only"] = {o: {"rows": int(len(ms)), "events": int(ms[o].sum()), "auc": pr.auc(ms["reading"], ms[o])}
                              for o in ("A", "B")}
    report["description"] = desc
    return report


def _algae_levels() -> dict:
    from dipcast import algae
    return dict(algae.LEVELS)


def score(out: Path, features_sha: str, checks_sha: str) -> None:
    pr.check_hash(out / "features.parquet", features_sha)
    pr.check_hash(out / "checks.parquet", checks_sha)
    features = pd.read_parquet(out / "features.parquet")
    checks = pd.read_parquet(out / "checks.parquet")
    sizes = json.loads((out / "sizes.json").read_text())
    report = score_frames(features, checks, pr.lake_sites(SITES), sizes)
    report["hashes"] = {"features": features_sha, "checks": checks_sha}
    (out / "score.json").write_text(json.dumps(report, indent=1, default=_json_default))
    print({o: report["outcomes"][o]["verdict"] for o in ("A", "B")})


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fetch":
        fetch(Path(sys.argv[2]), sys.argv[3])
    elif cmd == "score":
        score(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
