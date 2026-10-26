"""Fit the river E. coli model with soil moisture (docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md) and write it as JSON.

    train_ecoli_sm.py <soil dir> <out ecoli_model_sm.json> [docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.json]

Run in a root where validate_ecoli.py, replay_ecoli_leads.py and train_ecoli.py have run (DIPCAST_ROOT etc.), offline.
The rows are train_ecoli.py's (scripts/soil_moisture_eval/diagnostics.rows_q1): the EA samples at inland bathing
waters with overflows upstream and forecast rain and exposure at every lead, rivers and lakes together, as the tests
fitted it. The inputs are today's seven plus `sm`, ECMWF IFS soil_moisture_9_to_27cm at 00:00 UTC of the sample's UTC
day (leads.soil_at_issue, lead 0). The site uses it for river spots only. `meta.sm_range` is the range of `sm` in the
fitting rows; the site holds a live value inside it. With the leads test's JSON, the coefficients must equal its
fit on all rows (coef_per_sd_all_rows) to 1e-9. The rivers-only test used that same fit, so the file is the model
the tests passed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "soil_moisture_eval"))
from diagnostics import rows_q1  # noqa: E402
from leads import CAND, soil_at_issue  # noqa: E402

from dipcast.ingest.soil import SOIL_MODEL, SOIL_VAR  # noqa: E402
from dipcast.model.ecoli import THRESHOLD, features, fit  # noqa: E402


def main(soil_dir: str, out_path: str, check: str | None = None) -> None:
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    X = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X["sm"] = soil_at_issue(rows, Path(soil_dir), 0)
    ok = np.isfinite(X["sm"].to_numpy())
    assert ok.all(), f"{(~ok).sum()} rows without sm"
    lake = rows["lake"].to_numpy() == 1.0
    meta = {
        "target": "E. coli > 900 cfu/100 ml",
        "use": "river spots only; lakes use ecoli_model.json",
        "fitted_on": "EA samples at inland bathing waters with overflows upstream, rivers and lakes together "
                     "(train_ecoli.py's rows, the frozen data folder of docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md)",
        "n_samples": int(len(rows)), "n_rivers": int((~lake).sum()), "n_lakes": int(lake.sum()),
        "n_sites": int(rows["bw_id"].nunique()), "n_over_900": int(y.sum()),
        "years": sorted(int(v) for v in rows["sample_time"].dt.year.unique()),
        "rain_source": "Open-Meteo archived forecast, lead 0 (48 h / 24 h to the sample time)",
        "exposure_source": "replayed lead-0 exposure",
        "sm_source": f"Open-Meteo, models={SOIL_MODEL}, {SOIL_VAR}, Previous Runs lead 0, at 00:00 UTC of the issue day",
        "sm_range": [float(X["sm"].min()), float(X["sm"].max())],
        "tests": ["docs/SOIL-MOISTURE-TEST-2026-10.md", "docs/SOIL-MOISTURE-ECOLI-LEADS-TEST-2026-11.md",
                  "docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.md"],
    }
    m = fit(X, y, CAND, meta=meta)
    if check:
        want = json.loads(Path(check).read_text())["coef_per_sd_all_rows"]
        diff = max(abs(m.coef[c] - want[c]) for c in CAND)
        assert diff < 1e-9, (m.coef, want)
        m.meta["check"] = f"coefficients equal {check}'s coef_per_sd_all_rows (largest difference {diff:.1g})"
    m.save(Path(out_path))
    print(json.dumps({"coef": m.coef, "intercept": m.intercept, "meta": m.meta}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
