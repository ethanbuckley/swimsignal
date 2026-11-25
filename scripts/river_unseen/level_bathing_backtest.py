"""`river-level-v1`'s earlier-samples range (L2) at bathing-water rivers, on bench rows already seen
(docs/RIVER-LEVEL-BATHING-BACKTEST-2026-11.md). Development.

    python scripts/river_unseen/level_bathing_backtest.py sites <seen river rows> docs/river-level/bathing_sites.csv
    python scripts/river_unseen/level_bathing_backtest.py score <seen river rows> docs/river-level/bathing_sites.csv \\
        docs/river-level/river_level_v1.json docs/river-unseen/river_range_v0e.json docs/river-level

`sites` reads positions only and writes each site's km of channel upstream (scratch DIPCAST_ROOT and DIPCAST_STATE).
`score` uses the frozen line and spreads as they are. For a site and a season, the site's level is its mean residual
over its own earlier seasons (10 samples or more), shrunk by tau^2 / (tau^2 + sigma^2 / n). It writes
<out>/bathing_result.json and appends to <out>/runs.jsonl whatever it shows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_candidate as fc  # noqa: E402
import level_candidate as lc  # noqa: E402
import read as rd  # noqa: E402


def sites(rows_p: Path, out: Path) -> None:
    assert "DIPCAST_ROOT" in os.environ and "DIPCAST_STATE" in os.environ, "set a scratch DIPCAST_ROOT and DIPCAST_STATE"
    from dipcast.model.forecast import _net
    from dipcast.model.transport import locate_pin

    t = pd.read_parquet(rows_p, columns=["bw_id", "name", "lat", "lon"]).drop_duplicates("bw_id")
    net, got = _net(), []
    for p in t.itertuples():
        pin = locate_pin(net, p.lon, p.lat, kind_hint="river")
        got.append({"point": p.bw_id, "name": p.name,
                    "upstream_km": round((net.upstream_length(pin.trace_node) + pin.trace_offset_m) / 1000.0, 1)})
    pd.DataFrame(got).sort_values("point").to_csv(out, index=False)
    print(len(got), "sites; km of channel upstream:", pd.DataFrame(got)["upstream_km"].describe().round(1).to_dict())


def earlier_samples_ranges(d: pd.DataFrame, m: dict) -> pd.DataFrame:
    """A range for every sample whose site has lc.MIN_EARLY or more samples in earlier seasons."""
    t2, s2, out = m["tau"] ** 2, m["sigma"] ** 2, []
    for _, site in d.groupby("bw_id"):
        for season in sorted(site["season"].unique()):
            e, x = site[site["season"] < season], site[site["season"] == season]
            if len(e) < lc.MIN_EARLY:
                continue
            n = len(e)
            level = (t2 / (t2 + s2 / n)) * float((e["log_ecoli"] - lc.fixed(m, e)).mean())
            sd = np.sqrt(t2 * s2 / (n * t2 + s2) + s2)
            out.append(lc.ranges(x, lc.fixed(m, x) + level, lc.Z * sd).assign(sd_log10=sd))
    return pd.concat(out)


def log_density(x: pd.DataFrame) -> pd.Series:
    return pd.Series(norm.logpdf(x["log_ecoli"], x["mu_log10"], x["sd_log10"]), index=x.index)


def score(d: pd.DataFrame, m: dict, cand: dict) -> dict:
    d = d.assign(system=d["bw_id"], band="bathing")
    new = earlier_samples_ranges(d, m)
    same = d.loc[new.index]
    old = lc.ranges(same, fc.predict(cand, same)["mu_log10"].to_numpy(), lc.Z * cand["sd_log10"]).assign(sd_log10=cand["sd_log10"])
    gain = (log_density(new) - log_density(old)).rename("gain")
    g = new.assign(gain=gain)
    draws = rd.system_season_draws(g, lambda b: float(b["gain"].mean()))
    by_site = lambda x: {k: round(float(v), 3) for k, v in x.groupby("bw_id")["inside"].mean().items()}  # noqa: E731
    keep = ("rows", "points", "coverage", "coverage_ci95", "above", "below", "pass", "median_half_width_log10", "rho_within_point")
    return {"form": "river-level-v1, earlier samples (L2), frozen", "evidence": "development (bench rows already seen)",
            "seasons_scored": {int(k): int(v) for k, v in new.groupby("season").size().items()},
            "L2": {k: v for k, v in lc.summary(new).items() if k in keep},
            "river_range_v0e_same_rows_in_sample": {k: v for k, v in lc.summary(old).items() if k in keep},
            "log_density_gain_over_v0e": {"value": round(float(gain.mean()), 4),
                                          "ci95": [round(float(v), 4) for v in np.nanpercentile(draws, [2.5, 97.5])]},
            "coverage_by_site": {"L2": by_site(new), "v0e": by_site(old)}}


def main(argv: list[str]) -> None:
    if argv[0] == "sites":
        return sites(Path(argv[1]), Path(argv[2]))
    rows_p, sites_p, model_p, cand_p, out = (Path(a) for a in argv[1:6])
    d = pd.read_parquet(rows_p)
    if "ecoli_qual" not in d or d["ecoli_qual"].isna().any():
        d["ecoli_qual"] = d.get("ecoli_qual", pd.Series("=", index=d.index)).fillna("=")
    d = lc.with_place_inputs(d, pd.read_csv(sites_p))
    res = score(d, json.loads(model_p.read_text()), json.loads(cand_p.read_text()))
    res["outcome"] = "L2 passes at bathing-water rivers" if res["L2"]["pass"] else "L2 fails at bathing-water rivers"
    print(json.dumps(res, indent=1))
    commit = subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "bathing_result.json").write_text(json.dumps({"run_at": stamp, "commit": commit, "rows_sha256": rd.sha(rows_p),
                                                         "model_sha256": rd.sha(model_p), **res}, indent=1) + "\n")
    with (out / "runs.jsonl").open("a") as f:
        f.write(json.dumps({"run_at": stamp, "commit": commit, "what": "bathing backtest", "outcome": res["outcome"],
                            "L2": res["L2"]["coverage"]}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
