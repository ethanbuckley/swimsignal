"""Does a recent rise at a river bathing water's own gauge order its E. coli samples beyond rain?
(docs/LEVEL-RISE-CHECK-2026-11.md). Offline, on the backtest bench's SEEN rows only (2023-26): development evidence.

    python scripts/level_rise_check/score.py <bench seen.parquet> docs/level-rise-check/gauges.csv <fetch out dir> \\
        docs/level-rise-check/result.json

Per sample: rise24, the level at the sample time less the lowest level in the 24 hours before, as a share of the
gauge's usual range; and index, the level's place in that range. Never opens the bench's held-out file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = ["lrain48", "lrain24", "doy_sin", "doy_cos", "logit_risk"]
NEAR, WINDOW, MIN_SHARE, MIN_ROWS, SEED, DRAWS = pd.Timedelta("30min"), pd.Timedelta("24h"), 0.8, 15, 20261116, 4000


def level_features(times: pd.Series, series: pd.DataFrame, low: float, high: float) -> pd.DataFrame:
    """rise24 and index for each sample time (UTC), NaN where the gauge has no reading within 30 minutes or fewer
    than 80% of the 24 hours' 15-minute readings."""
    s = series.set_index("time")["value"].sort_index()
    span = high - low
    out = []
    for t in times:
        w = s[t - WINDOW:t]
        if w.empty or t - w.index[-1] > NEAR or len(w) < MIN_SHARE * 96 or span <= 0:
            out.append((np.nan, np.nan))
        else:
            out.append(((w.iloc[-1] - w.min()) / span, (w.iloc[-1] - low) / span))
    return pd.DataFrame(out, columns=["rise24", "index"], index=times.index)


def loso(x: pd.DataFrame, cols: list[str]) -> pd.Series:
    """A pooled least-squares fit of log10 E. coli, each site predicted from the others."""
    pred = pd.Series(index=x.index, dtype=float)
    for site in x["bw_id"].unique():
        tr, te = x[x["bw_id"] != site], x[x["bw_id"] == site]
        beta, *_ = np.linalg.lstsq(np.c_[np.ones(len(tr)), tr[cols].to_numpy(float)], tr["log_ecoli"].to_numpy(float),
                                   rcond=None)
        pred[te.index] = np.c_[np.ones(len(te)), te[cols].to_numpy(float)] @ beta
    return pred


def rho_site(x: pd.DataFrame, col: str) -> float:
    r = [spearmanr(g[col], g["log_ecoli"])[0] for _, g in x.groupby("site") if len(g) >= MIN_ROWS and g[col].nunique() > 1]
    return float(np.mean(r)) if r else float("nan")


def paired(x: pd.DataFrame, a: str, b: str) -> dict:
    """rho_site(a) - rho_site(b) with a 95% interval from resampled sites."""
    rng, sites = np.random.default_rng(SEED), x["bw_id"].unique()
    per = {s: x[x["bw_id"] == s] for s in sites}
    d = []
    for _ in range(DRAWS):
        draw = pd.concat([per[s].assign(site=f"{s}#{i}") for i, s in enumerate(rng.choice(sites, len(sites)))])
        d.append(rho_site(draw, a) - rho_site(draw, b))
    x = x.assign(site=x["bw_id"])
    return {"a": round(rho_site(x, a), 3), "b": round(rho_site(x, b), 3), "difference": round(rho_site(x, a) - rho_site(x, b), 3),
            "ci95": [round(float(v), 3) for v in np.nanpercentile(d, [2.5, 97.5])]}


def main(seen: Path, gauges: Path, fetched: Path, out: Path) -> None:
    rows = pd.read_parquet(seen)
    assert set(rows["part"]) == {"seen"}, "seen rows only"
    rows = rows[rows["kind"] == "river"].copy()
    g = pd.read_csv(gauges).dropna(subset=["measure"]).set_index("bw_id")
    parts = []
    for bw, x in rows.groupby("bw_id"):
        f = fetched / "series" / f"{g.loc[bw, 'gauge']}.parquet" if bw in g.index else None
        if f is None or not f.exists():
            continue
        t = x["sample_time"].dt.tz_convert("UTC")
        parts.append(x.join(level_features(t, pd.read_parquet(f), float(g.loc[bw, "low"]), float(g.loc[bw, "high"]))))
    d = pd.concat(parts)
    have = d.dropna(subset=["rise24", "index"]).copy()
    have["site"] = have["bw_id"]
    have["base"] = loso(have, BASE)
    have["base_rise"] = loso(have, BASE + ["rise24"])
    have["base_rise_index"] = loso(have, BASE + ["rise24", "index"])
    have["rain_only"] = loso(have, BASE[:4])
    have["rain_rise_index"] = loso(have, BASE[:4] + ["rise24", "index"])
    dry = have[have["rain_48h"] < 2]
    res = {
        "rows": {"river_seen": int(len(rows)), "at_sites_with_a_series": int(len(d)), "with_level_features": int(len(have)),
                 "sites": int(have["bw_id"].nunique()), "over_900": int(have["over"].sum())},
        "primary_base_plus_rise_vs_base": paired(have, "base_rise", "base"),
        "reported": {
            "base_plus_rise_and_index_vs_base": paired(have, "base_rise_index", "base"),
            "rain_plus_rise_and_index_vs_rain_only": paired(have, "rain_rise_index", "rain_only"),
            "rise24_alone_vs_lrain48_alone": paired(have, "rise24", "lrain48"),
            "index_alone_vs_lrain48_alone": paired(have, "index", "lrain48"),
            "dry_days": {"rows": int(len(dry)), "over_900": int(dry["over"].sum()),
                         "index_alone_vs_base": paired(dry, "index", "base"),
                         "rise24_alone_vs_base": paired(dry, "rise24", "base")},
            "rise24_share_above_0.05": round(float((have["rise24"] > 0.05).mean()), 3),
            "over_900_when_rise24_above_0.05": round(float(have[have["rise24"] > 0.05]["over"].mean()), 3),
            "over_900_otherwise": round(float(have[have["rise24"] <= 0.05]["over"].mean()), 3),
            "by_site_rho": {n: {"n": int(len(x)), "rise24": round(float(spearmanr(x["rise24"], x["log_ecoli"])[0]), 2),
                                "index": round(float(spearmanr(x["index"], x["log_ecoli"])[0]), 2),
                                "lrain48": round(float(spearmanr(x["lrain48"], x["log_ecoli"])[0]), 2)}
                            for n, x in have.groupby("name") if len(x) >= MIN_ROWS}},
    }
    res["supported"] = bool(res["primary_base_plus_rise_vs_base"]["ci95"][0] > 0)
    out.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
