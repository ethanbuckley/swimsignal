"""docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md, the one scoring run, offline.

    incident_score.py <out dir> <features file> <committed features SHA-256> <committed incidents SHA-256>

Run under scripts/lake_distance_eval/run_offline.py (every outgoing connection refused and counted), from a git
archive of the harness commit. The stop rules come first (both hashes, the fetch's completeness, the type check,
algae incidents with a readable start and an end not before it); then the gate; then the scores. Writes score.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import algae_incidents as inc
from incident_fetch import SIZES, test_sites


def description(incidents: pd.DataFrame, days: pd.DataFrame, sc: pd.DataFrame) -> dict:
    alg = incidents[incidents["kind"] == "algae"]
    lab = days.assign(has=np.isfinite(days["reading"].to_numpy(dtype=float)))
    by = lab.groupby(["label"]).agg(days=("has", "size"), with_reading=("has", "sum"))
    out = {
        "incidents_by_kind": incidents.groupby(["kind", "code"], dropna=False).size().reset_index(name="n")
        .to_dict("records"),
        "algae_incidents": alg.to_dict("records"),
        "open_ended": incidents[incidents["open_ended"]].to_dict("records"),
        "malformed_non_algae": int(incidents["malformed"].sum()),
        "days_by_label": {k: {"days": int(r.days), "with_reading": int(r.with_reading)} for k, r in by.iterrows()},
    }
    # Control days with an algae incident open at another site of the same water body.
    inc_wb_days = set(zip(lab.loc[lab["label"] == "incident", "water_body"],
                          lab.loc[lab["label"] == "incident", "date"], strict=True))
    ctl = lab[lab["label"] == "control"]
    out["control_days_with_incident_elsewhere_on_lake"] = int(sum(
        (w, d) in inc_wb_days for w, d in zip(ctl["water_body"], ctl["date"], strict=True)))
    # Other pairing windows.
    for w in inc.DESCRIPTION_PAIR_DAYS:
        t = inc.strata_table(inc.attach_readings(days, sc, window_days=w))
        out[f"window_{w}"] = {"S": inc.pooled_s(t), "strata": int((t["pairs"] > 0).sum()),
                              "incident_days": int(t.loc[t["pairs"] > 0, "incident_days"].sum())}
    # Without Frensham Great Pond in 2026 (its incident was seen before this statement).
    t = inc.strata_table(days)
    rest = t[~((t["water_body"] == "Frensham Great Pond") & (t["season"] == 2026))]
    out["without_frensham_2026"] = {"S": inc.pooled_s(rest), "strata": int((rest["pairs"] > 0).sum())}
    return out


def score_frames(records: list[dict], fetch_day, features: pd.DataFrame, sizes: dict) -> dict:
    sites = {k: v["water_body"] for k, v in sizes.items() if v["in_test"]}
    incidents = inc.incidents_at_sites(records, set(sites), fetch_day)
    sc = inc.scenes(features, set(sites))
    days = inc.attach_readings(inc.label_days(incidents, sites), sc)
    report = {"sites": sorted(sites), "fetch_day": fetch_day.isoformat(), "scenes": int(len(sc))}
    report["result"] = inc.score(days, incidents, sc)
    report["description"] = description(incidents, days, sc)
    return report


def main(out: Path, features_path: Path, features_sha: str, incidents_sha: str) -> None:
    if features_sha.strip().lower() != inc.FEATURES_SHA256:
        raise inc.StopRule("the features hash given is not the one committed in #377")
    inc.check_hash(features_path, features_sha)
    inc.check_hash(out / "incidents.json", incidents_sha)
    sites = test_sites()
    records, fetch_day = inc.load_fetch(out / "incidents.json", sites)
    sizes = json.loads(SIZES.read_text())
    features = pd.read_parquet(features_path)
    report = score_frames(records, fetch_day, features, sizes)
    report["hashes"] = {"features": features_sha, "incidents": incidents_sha}
    (out / "score.json").write_text(json.dumps(report, indent=1, default=_json_default))
    print("verdict:", report["result"]["verdict"])


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4])
