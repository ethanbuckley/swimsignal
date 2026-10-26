"""docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md, stage 2: fetch the chlorophyll-a values once, then score offline.

    chl_stage2.py fetch <out dir> <lakes.json> <committed features SHA-256>
        Refuses unless features.parquet hashes to the committed value, and refuses if values.parquet exists (one
        fetch). One request per chosen point (Amendment A3 of #377: the service limits several points to a year),
        determinand 7887, 1 May 2020 to 30 September 2026, as CSV. Writes values.parquet and values.sha256. Prints
        counts and the hash, never a value.
    chl_stage2.py score <out dir> <lakes.json> <committed features SHA-256> <values SHA-256>
        Run under scripts/lake_distance_eval/run_offline.py (every connection refused and counted). The stop rules
        first (hashes, unit, determinand), then the gate, then the scores. Writes score.json.

This is the only file that reads a result. Nothing here has been run on real data; tests/test_lake_chlorophyll_eval.py
runs `score_frames` on synthetic frames.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lake_algae_sat_eval"))
import net  # noqa: E402

import chl_protocol as cp  # noqa: E402
import wqa_meta as w  # noqa: E402

FETCH_MAX_REQUESTS, FETCH_MAX_BYTES = 80, 20 * 1024**2      # 40 points, one CSV page each expected
VALUE_COLUMNS = {"samplingPoint.notation": "wqa_point", "phenomenonTime": "sample_time",
                 "determinand.notation": "determinand", "unit": "unit", "samplingPurpose": "purpose",
                 "result": "result"}


def parse_values(text: str) -> pd.DataFrame:
    rd = csv.reader(io.StringIO(text))
    try:
        header = [h.strip().lstrip("﻿") for h in next(rd)]
    except StopIteration:
        return pd.DataFrame(columns=list(VALUE_COLUMNS.values()))
    where = {VALUE_COLUMNS[h]: i for i, h in enumerate(header) if h in VALUE_COLUMNS}
    missing = set(VALUE_COLUMNS.values()) - set(where)
    if missing:
        raise cp.StopRule(f"CSV lacks {sorted(missing)}")
    return pd.DataFrame([{k: r[i] for k, i in where.items()} for r in rd if r], columns=list(VALUE_COLUMNS.values()))


def fetch(out: Path, lakes_json: Path, features_sha: str, http=None, sleep=None) -> None:
    cp.check_hash(out / "features.parquet", features_sha)
    target = out / "values.parquet"
    if target.exists():
        raise cp.StopRule("values.parquet exists: the values are fetched once")
    kw = {"sleep": sleep} if sleep is not None else {}
    c = w.Capped(ledger=out / "ledger-fetch.jsonl", client=http or _http(), max_requests=FETCH_MAX_REQUESTS,
                 max_bytes=FETCH_MAX_BYTES, max_requests_total=FETCH_MAX_REQUESTS, max_bytes_total=FETCH_MAX_BYTES,
                 **kw)
    frames = []
    for p in json.loads(Path(lakes_json).read_text())["points"]:
        skip = 0
        while True:
            u = w.url("/data/observation", pointNotation=p["wqa_point"], determinand=cp.DETERMINAND,
                      dateFrom="2020-05-01", dateTo="2026-09-30", limit=w.CSV_LIMIT, skip=skip)
            _, body = c.request("POST", u, headers={"Accept": "text/csv"})
            page = parse_values(body.decode("utf-8", errors="replace"))
            frames.append(page)
            if len(page) < w.CSV_LIMIT:
                break
            skip += w.CSV_LIMIT
    df = pd.concat(frames, ignore_index=True).sort_values(["wqa_point", "sample_time"]).reset_index(drop=True)
    df.to_parquet(target, index=False)
    h = cp.sha256(target)
    (out / "values.sha256").write_text(h + "\n")
    print("values fetched:", len(df), "rows at", df["wqa_point"].nunique(), "points; SHA-256", h, c.summary())


def _http():
    import httpx
    return httpx.Client(timeout=net.TIMEOUT_S, follow_redirects=False, headers={"User-Agent": w.USER_AGENT})


def pairing_table(paired: pd.DataFrame) -> list[dict]:
    t = paired.assign(has=paired["reading"].notna())
    g = t.groupby(["wqa_point", "season"]).agg(samples=("has", "size"), with_reading=("has", "sum"))
    return [{"wqa_point": k[0], "season": int(k[1]), "samples": int(r.samples), "with_reading": int(r.with_reading)}
            for k, r in g.iterrows()]


def score_frames(features: pd.DataFrame, values: pd.DataFrame, points: list[dict], sizes: dict) -> dict:
    """Everything after the hash checks: frames in, the report out."""
    in_test = {k for k, v in sizes.items() if v["in_test"]}
    samples, how = cp.prepare_samples(values, points)
    report = {"values": how, "samples": int(len(samples)), "points_in_test": sorted(in_test),
              "points_out": sorted(set(sizes) - in_test)}
    s_in = samples[samples["wqa_point"].isin(in_test)].reset_index(drop=True)
    report["samples_at_points_in_test"] = int(len(s_in))
    report["samples_in_2022"] = int((s_in["season"] == 2022).sum())
    scenes = cp.sat.one_per_date(features[features["bw_id"].isin(in_test)])
    paired = cp.pair(s_in, scenes, cp.PAIR_DAYS)
    report["pairing"] = pairing_table(paired)
    rows = paired[paired["reading"].notna()].reset_index(drop=True)
    report["lag_days"] = {int(k): int(v) for k, v in rows["lag_days"].value_counts().sort_index().items()}
    report["result"] = cp.score(rows)
    # Description only.
    desc = {}
    same = rows[rows["lag_days"] == 0]
    desc["same_day"] = {"pairs": int(len(same)), "rho": cp.spearman(same["reading"], same["log_chl"])}
    meas = rows[rows["how"] == "measured"]
    desc["censored_left_out"] = {"pairs": int(len(meas)), "rho": cp.spearman(meas["reading"], meas["log_chl"])}
    desc["rho_by_lake"] = {k: {"pairs": int(len(g)), "rho": cp.spearman(g["reading"], g["log_chl"])}
                           for k, g in rows.groupby("wb_id")}
    desc["rho_by_season"] = {int(k): {"pairs": int(len(g)), "rho": cp.spearman(g["reading"], g["log_chl"])}
                             for k, g in rows.groupby("season")}
    if len(rows) >= 2 and rows["reading"].nunique() >= 2:
        b, a = np.polyfit(rows["reading"].to_numpy(dtype=float), rows["log_chl"].to_numpy(dtype=float), 1)
        desc["fit_all_pairs"] = {"intercept": float(a), "slope": float(b)}
    report["description"] = desc
    return report


def score(out: Path, lakes_json: Path, features_sha: str, values_sha: str) -> None:
    cp.check_hash(out / "features.parquet", features_sha)
    cp.check_hash(out / "values.parquet", values_sha)
    features = pd.read_parquet(out / "features.parquet")
    values = pd.read_parquet(out / "values.parquet")
    sizes = json.loads((out / "sizes.json").read_text())
    points = json.loads(Path(lakes_json).read_text())["points"]
    report = score_frames(features, values, points, sizes)
    report["hashes"] = {"features": features_sha, "values": values_sha}
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch" and len(sys.argv) == 5:
        fetch(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    elif cmd == "score" and len(sys.argv) == 6:
        score(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        raise SystemExit(__doc__)
