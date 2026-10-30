"""Rebuild the nine-company v2 models exactly as the v2 run fitted them, and check them against the recorded hashes
(docs/REGIONAL-ROUTING-2026-11.md, "The candidate's files"). Training reads only 2024-25; nothing of 2026 is read.

    git archive record/nine-company-v2-run src scripts | tar -x -C <code>
    DIPCAST_ROOT=<scratch root> DIPCAST_STATE=<scratch state> DIPCAST_CACHE=<rain cache, read only> \\
        PYTHONPATH=<code>/src <main checkout>/.venv/bin/python scripts/regional_routing_rebuild.py <code> <out>

<scratch root>/data/processed holds annual_returns.parquet and ea_events_<company>.parquet (2024-25), linked read only.
The fit is the run's own code (nine_v2_eval.frame, SpillModel.fit_pooled, fit_site_offsets, the same seeds and
settings), imported from the archive of the tag. The library versions must be the run's (scikit-learn 1.9.1,
pandas 3.0.5, numpy 2.5.3) or the bytes can differ.
"""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

RECORDED = {   # docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md, "Reproduction"
    "spill_model_v2_pooled.pkl": "bd8faaaf31031fa3",
    "spill_model_v2_offsets.pkl": "9e0fc54a9356e4ce",
    "spill_model_v2_offsets_r025.pkl": "ab2e7ba834bab881",
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(code: Path, out: Path) -> None:
    import numpy
    import pandas as pd
    import sklearn
    versions = (sklearn.__version__, pd.__version__, numpy.__version__)
    if versions != ("1.9.1", "3.0.5", "2.5.3"):
        raise SystemExit(f"library versions {versions} are not the run's")
    sys.path.insert(0, str(code / "scripts"))
    import nine_v2_eval as run   # the tagged harness: its constants, frame() and the PR #334 day code

    from dipcast import config
    from dipcast.model.features import daily_rain_features, spill_days
    from dipcast.model.spill_model import SpillModel
    from dipcast.model.training import NINE, cells_of, load_events, load_rain, site_years

    out.mkdir(parents=True, exist_ok=True)
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    ev = ev[ev["site_id"].notna()]
    labels = spill_days(ev)
    s24, _ = site_years(ar, ev, NINE, 2024)
    s25, _ = site_years(ar, ev, NINE, 2025)
    rain = load_rain(cells_of(pd.concat([s24, s25])))
    rain = rain[rain["time"] < pd.Timestamp("2026-01-01", tz="UTC")]
    daily = daily_rain_features(rain)
    del rain
    train = pd.concat([run.frame(s24, 2024, daily, labels), run.frame(s25, 2025, daily, labels)], ignore_index=True)
    print(f"training site-days {len(train)}, spill-days {int(train['y'].sum())}")
    m = SpillModel().fit_pooled(train, neg_frac=run.NEG_FRAC, seed=0)
    mb = copy.deepcopy(m).fit_site_offsets(train, prior_strength=run.PRIOR, recency=run.RECENCY_B)
    mb25 = copy.deepcopy(m).fit_site_offsets(train, prior_strength=run.PRIOR, recency=run.RECENCY_B25)
    m.trained_on = mb.trained_on = mb25.trained_on = (
        "Nine English water companies 2024-2025 (EA start/stop files, UK local days); verified on January-August 2026")
    bad = []
    for name, mod in (("v2_pooled", m), ("v2_offsets", mb), ("v2_offsets_r025", mb25)):
        p = out / f"spill_model_{name}.pkl"
        mod.save(p)
        got = sha256(p)
        ok = got.startswith(RECORDED[p.name])
        print(f"{p.name} {got[:16]} {'matches the record' if ok else 'DIFFERS from ' + RECORDED[p.name]}")
        bad += [] if ok else [p.name]
    if bad:
        raise SystemExit(f"not the recorded models: {bad}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
