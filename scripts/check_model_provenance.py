"""Check which layer-2 settings reproduce the site offsets stored in the spill model files.

    check_model_provenance.py [--holdout PATH] [--prod PATH]

Rebuilds the United Utilities rows the files were fitted on (train.py's covariates and filters, from
config.PROCESSED's edm_events.parquet and annual_returns.parquet and the rain archive cache, cut into UTC days by
scripts/legacy_utc_days.py, not by features.py, whose day boundary may change), takes each model file's own
layer 1 (so layer 1 is held fixed), and recomputes the offsets with SpillModel.fit_site_offsets' formula
at several recency weights with prior PRIOR_STRENGTH. A setting reproduces a file when every stored
offset is matched to within 1e-9. The hold-out file uses the 2023-24 rows, production all rows.
Reads only; writes nothing. Off CI: it needs the data folder and about 4 GB.

Exit 0 when each file is reproduced by some setting and its recorded site_recency (if any) is that setting;
1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.argv = [sys.argv[0], "2025", *sys.argv[1:]]
import legacy_utc_days as L  # noqa: E402
import train as T  # noqa: E402  (train.py reads sys.argv at import)

from dipcast import config  # noqa: E402
from dipcast.model.features import ALL_FEATURES  # noqa: E402
from dipcast.model.spill_model import PRIOR_STRENGTH, SpillModel  # noqa: E402

RECENCIES = (1.0, 0.9, 0.8, 0.75, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.1)
TOL = 1e-9


def rows(ev: pd.DataFrame | None = None, ar: pd.DataFrame | None = None, rain: pd.DataFrame | None = None) -> pd.DataFrame:
    """The rows the 13 Sep 2026 files were fitted on: train.main's rows, after its rain and quality filters and
    before the train/test split, on UTC days (legacy_utc_days). Inputs default to the data folder's."""
    ev = pd.read_parquet(config.PROCESSED / "edm_events.parquet") if ev is None else ev
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet") if ar is None else ar
    daily = L.daily_rain_features(T.load_rain_archive() if rain is None else rain)
    labels = L.spill_days(ev)
    cov = T.site_year_covariates(ar)
    qual = ar[(ar.company == T.COMPANY)][["site_id", "year", "edm_operational_pct"]].rename(
        columns={"edm_operational_pct": "edm_pct_same_year"})
    frames = []
    for y in sorted(labels["day"].dt.year.unique()):
        sy = cov[cov.year == y].drop(columns="year")
        if sy.empty:
            continue
        days = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D", tz=L.DAY_TZ)
        sd = L.build_site_days(sy.assign(company=T.COMPANY), daily, days, labels)
        sd["year"] = y
        frames.append(sd)
    df = pd.concat(frames, ignore_index=True)
    qual = qual.drop_duplicates(subset=["site_id", "year"])
    qual["year"] = qual["year"].astype("int64")
    df["year"] = df["year"].astype("int64")
    df = df.merge(qual, on=["site_id", "year"], how="left")
    df = df[df["rain_d"].notna()]
    df = df[(df["edm_pct_same_year"].isna()) | (df["edm_pct_same_year"] >= T.MIN_EDM_PCT)]
    return df.astype({f: np.float32 for f in ALL_FEATURES})


def check(name: str, model: SpillModel, df: pd.DataFrame) -> bool:
    stored = pd.Series(model.site_offset)
    base = pd.DataFrame({"site_id": df["site_id"].to_numpy(), "year": df["year"].to_numpy(),
                         "y": df["y"].to_numpy(), "p": model.predict_pooled(df)})
    n_days = base.groupby("site_id").size().reindex(stored.index)
    same_rows = bool((n_days == pd.Series(model.site_n).reindex(stored.index)).all())
    print(f"{name}: {len(df)} rows, {len(stored)} stored offsets, rows per site match site_n: {same_rows}, "
          f"recorded recency {model.site_recency}, prior {model.site_prior}")
    hits = []
    for r in RECENCIES:
        w = np.power(r, base["year"].max() - base["year"].to_numpy()) if r < 1 else 1.0
        g = base.assign(y=base["y"] * w, p=base["p"] * w).groupby("site_id").agg(n=("y", "sum"), e=("p", "sum"))
        off = np.log((g["n"] + PRIOR_STRENGTH) / (g["e"] + PRIOR_STRENGTH)).reindex(stored.index)
        d = (off - stored).abs()
        exact = int((d < TOL).sum())
        print(f"  recency {r:<5} max|diff| {d.max():.2e}  exact {exact}/{len(d)}")
        if exact == len(d):
            hits.append(r)
    ok = bool(hits) and same_rows and (model.site_recency is None or model.site_recency in hits)
    print(f"  reproduced by recency {hits or 'none'} at prior {PRIOR_STRENGTH}: {'yes' if ok else 'NO'}")
    return ok


def main() -> None:
    args = sys.argv[2:]
    path = {k: Path(args[args.index(k) + 1]) if k in args else None for k in ("--holdout", "--prod")}
    df = rows()
    ok = check("hold-out", SpillModel.load(path["--holdout"] or config.PROCESSED / "spill_model_holdout_2025.pkl"),
               df[df["year"] < T.TEST_YEAR])
    ok &= check("production", SpillModel.load(path["--prod"] or config.PROCESSED / "spill_model.pkl"), df)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
