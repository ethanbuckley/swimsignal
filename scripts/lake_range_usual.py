"""Each lake bathing water's typical inputs for the "higher or lower than usual" line
(docs/LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md): the median rain over 48 h and 24 h and the median exposure on its own
2023-26 Environment Agency sample days, from the rows lake-range-v1 was fitted on. Off CI, by hand, offline:

    # 1. #584's training rows, rebuilt by its own code (an archive of 0be59d2d) in a scratch root, no request:
    #    DIPCAST_ROOT, DIPCAST_STATE, DIPCAST_CACHE and LAKE_RANGE_OUT all in scratch; the shared rain cache's
    #    archive_*.parquet copied in; then lake_range_hindcast.stage_rows() (only its training part is needed).
    # 2. this script, on those rows:
    LAKE_RANGE_OUT=<scratch>/out uv run python scripts/lake_range_usual.py

It refuses to write unless the rows are the ones the frozen model was fitted on, by content: every input column's
mean and SD equal to the frozen file's, and each lake's intercept weights recomputed from its rows equal to the frozen
file's to its rounding (1e-6). Nothing is fitted or tuned. The file it writes is read by src/dipcast/lake_range.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from concentration_study import prepare, row_loglik  # noqa: E402

OUT = Path(os.environ.get("LAKE_RANGE_OUT", "lake_range_out"))
MODEL = HERE.parent / "data" / "processed" / "ecoli_lake_range.json"
DEST = HERE.parent / "data" / "processed" / "lake_range_usual.v1.json"
ROWS_CODE = "0be59d2d"   # #584's results commit: the code that built the rows


def same_rows(tr: pd.DataFrame, m: dict) -> dict:
    """The content checks; raises if the rows are not the frozen model's."""
    cols = m["cols"]
    for c in cols:
        assert float(tr[c].mean()) == m["mean"][c], (c, "mean")
        assert float(tr[c].std(ddof=0)) == m["sd"][c], (c, "sd")
    Z = np.column_stack([np.ones(len(tr))] + [(tr[c].to_numpy(float) - m["mean"][c]) / m["sd"][c] for c in cols])
    mu = Z @ np.asarray(m["beta"])
    u = np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])
    worst = 0.0
    for bw, s in m["sites"].items():
        g = (tr["bw_id"] == bw).to_numpy()
        ll = row_loglik(mu[g][:, None] + u[None, :], m["sigma_lake"], tr["y"].to_numpy()[g], tr["cens"].to_numpy()[g])
        post = np.asarray(m["log_prior"]) + ll.sum(0)
        d = float(np.max(np.abs(post - logsumexp(post) - np.asarray(s["log_weights"]))))
        assert d < 1e-6, (bw, d)
        worst = max(worst, d)
    return {"column_means_and_sds_equal": True, "intercept_weights_max_abs_difference": worst}


def main() -> None:
    path = OUT / "rows_train.parquet"
    tr = prepare(pd.read_parquet(path))
    m = json.loads(MODEL.read_text())
    assert m["rule"] == "lake-range-v1"
    assert len(tr) == m["fitted_on"]["rows"] and int((tr["lake"] == 1).sum()) == m["fitted_on"]["lake_rows"]
    checks = same_rows(tr, m)
    cols = ["bw_id", "sample_time", "ecoli", "qual", *m["cols"]]
    rows_sha = hashlib.sha256(pd.util.hash_pandas_object(tr[cols], index=False).to_numpy().tobytes()).hexdigest()
    sites = {}
    for bw in sorted(m["sites"]):
        g = tr[tr["bw_id"] == bw]
        assert len(g) and (g["lake"] == 1).all() and g["sample_time"].dt.month.between(5, 9).all()
        sites[bw] = {"name": m["sites"][bw]["name"], "samples": len(g),
                     "first": str(g["sample_time"].min().date()), "last": str(g["sample_time"].max().date()),
                     "rain_48h": float(g["rain_48h"].median()), "rain_24h": float(g["rain_24h"].median()),
                     "risk": float(g["risk_model"].median())}
    out = {
        "version": "lake-range-usual-v1",
        "rule": "lake-range-v1",
        "definition": ("Usual: lake-range-v1's likely reading for the same lake on the same date with that lake's "
                       "typical inputs, the median rain over 48 h and 24 h and the median exposure (risk) on its own "
                       "2023-26 Environment Agency sample days. Higher than usual: today's likely reading at least "
                       "twice usual; lower: at most half; otherwise about usual. Compared on the figures as "
                       "published (two significant figures); both under 10, which the page gives alike as "
                       "'under 10', is about usual."),
        "record": "docs/LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md",
        "model_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        "source": {
            "built_from": "lake-range-v1's 2023-26 training rows, rebuilt by scripts/lake_range_hindcast.py `rows` at "
                    f"{ROWS_CODE}, offline, from the shared inputs and rain cache",
            "rows_code_commit": ROWS_CODE,
            "rows": len(tr), "lake_rows": int((tr["lake"] == 1).sum()),
            "rows_sha256": rows_sha,
            "rows_parquet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "frozen_rows_sha256": m["fitted_on"]["rows_sha256"],
            "note": ("The rebuilt rows' hash (export's recipe) differs from the one the frozen file records; their "
                     "content matches it by every check below. The cause of the hash difference is not known."),
            "content_checks": checks,
        },
        "sites": sites,
    }
    DEST.write_text(json.dumps(out, indent=1) + "\n")
    print(DEST, hashlib.sha256(DEST.read_bytes()).hexdigest())
    print(json.dumps(sites, indent=1))


if __name__ == "__main__":
    main()
