"""Freeze each lake bathing water's own level for the 7 that lake-range-v1 has none for (docs/LAKE-RANGE-OWN-LEVELS-2026-11.md),
by the rule bench read 2 passed with (docs/BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md): lake-range-v1 unchanged, and a
lake's node weights are the prior's plus the summed censored-normal log-likelihood of its own 2023-26 samples,
normalised (`scripts/backtest_bench/candidates/lake_range_v1_ownlevel.py`, `own_weights`). The samples are the bench's
frozen seen rows, the rows that read fitted on.

    uv run python scripts/lake_range_levels.py

Writes data/processed/lake_range_levels.v1.json. No request.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE / "backtest_bench"))
import bench  # noqa: E402

from dipcast import lake_range  # noqa: E402

OUT = REPO / "data" / "processed" / "lake_range_levels.v1.json"
CANDIDATE = HERE / "backtest_bench" / "candidates" / "lake_range_v1_ownlevel.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("own", CANDIDATE)
    own = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(own)
    model = REPO / "data" / "processed" / lake_range.FILE.name   # the committed file, whatever DIPCAST_ROOT says
    assert hashlib.sha256(model.read_bytes()).hexdigest() == lake_range.SHA256, "not the frozen lake-range-v1 file"
    m = json.loads(model.read_text())
    seen = bench.load("seen")
    spots = pd.read_csv(REPO / "spots.csv").set_index("id")
    lake = seen[(seen["kind"] == "lake") & ~seen["bw_id"].isin(m["sites"])]
    sites = {}
    for bw, g in sorted(lake.groupby("bw_id")):
        s = spots.loc[f"bw-{bw}"]
        sites[bw] = {"name": str(s["name"]), "lat": round(float(s["lat"]), 6), "lon": round(float(s["lon"]), 6),
                     "samples": int(len(g)), "seasons": [int(g["season"].min()), int(g["season"].max())],
                     "log_weights": [round(float(x), 6) for x in own.own_weights(m, g)]}
    doc = {"rule": "lake-range-own-levels-v1", "record": "docs/LAKE-RANGE-OWN-LEVELS-2026-11.md",
           "test": "docs/BENCH-READ-LAKE-RANGE-COVERAGE-2026-11.md", "model_sha256": lake_range.SHA256,
           "rows_sha256": json.loads(bench.MANIFEST.read_text())["files"]["seen"]["sha256"],
           "candidate_sha256": hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), "sites": sites}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(OUT, hashlib.sha256(OUT.read_bytes()).hexdigest(), len(sites))
    return 0


if __name__ == "__main__":
    sys.exit(main())
