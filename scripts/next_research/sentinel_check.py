"""Development check for the sentinel idea (docs/NEXT-RESEARCH-SHORTLIST-2026-11.md): is what the estimate leaves
unexplained shared between bathing waters sampled on the same day? Seen samples and hindsight estimates only.

    python scripts/next_research/sentinel_check.py data/research/ecoli_evidence.v1.json <a copy of the site's spots-lite.json>

The second file gives each bathing water's position. Intervals resample days, seed 20261124."""

import itertools
import json
import sys

import numpy as np
import pandas as pd

BANDS = (("under 50 km", 0, 50), ("50 to 150 km", 50, 150), ("over 150 km", 150, 1e9))


def km(a, b) -> float:
    p = np.pi / 180
    return float(6371 * np.hypot((b[1] - a[1]) * p * np.cos((a[0] + b[0]) / 2 * p), (b[0] - a[0]) * p))


def load(evidence: str, spots_file: str) -> pd.DataFrame:
    ev = json.load(open(evidence))
    spots = {s["id"]: s for s in json.load(open(spots_file))["spots"]}
    rows = []
    for site in ev["sites"]:
        sp = spots.get(site["spot_id"])
        if not sp:
            continue
        for x in site["samples"]:
            if x.get("hindsight") is None or x.get("ecoli") is None:
                continue
            rows.append({"site": site["spot_id"], "kind": site["kind"], "lat": sp["lat"], "lon": sp["lon"],
                         "day": x["t"][:10], "y": np.log10(max(x["ecoli"], 1)), "h": x["hindsight"]})
    return pd.DataFrame(rows)


def main(evidence: str, spots_file: str) -> None:
    d = load(evidence, spots_file)
    for kind in ("river", "lake"):
        k = d[d.kind == kind].copy()
        h = np.clip(k.h, 1e-3, 1 - 1e-3)
        z = np.log(h / (1 - h))
        k["count_c"] = k.y - k.groupby("site").y.transform("mean")       # the count with the site's level taken off
        zc = z - z.groupby(k.site).transform("mean")
        slope = float((zc * k.count_c).sum() / (zc ** 2).sum())
        k["left"] = k.count_c - slope * zc                               # and the estimate's part taken off
        pos = {i: (r.lat, r.lon) for i, r in k.groupby("site")[["lat", "lon"]].first().iterrows()}
        rng = np.random.default_rng(20261124)
        print(kind, "rows", len(k), "sites", k.site.nunique(), "| slope on the estimate's log-odds %.3f" % slope,
              "| share of within-site variance left %.2f" % (k.left.var() / k.count_c.var()))
        for label, lo, hi in BANDS:
            pairs = [(a.left, c.left, a.count_c, c.count_c, day) for day, g in k.groupby("day")
                     for (_, a), (_, c) in itertools.combinations(g.iterrows(), 2)
                     if a.site != c.site and lo <= km(pos[a.site], pos[c.site]) < hi]
            if len(pairs) < 30:
                print("  ", label, "pairs", len(pairs), "too few")
                continue
            p = pd.DataFrame(pairs, columns=["r1", "r2", "c1", "c2", "day"])
            days = p.day.unique()
            boot = []
            for _ in range(1000):
                q = pd.concat([p[p.day == dd] for dd in rng.choice(days, len(days))])
                boot.append(np.corrcoef(q.r1, q.r2)[0, 1])
            print("  ", label, "pairs", len(p), "days", len(days),
                  "| same-day correlation of counts %.3f" % np.corrcoef(p.c1, p.c2)[0, 1],
                  "| of what the estimate leaves %.3f (%.3f to %.3f)" % (np.corrcoef(p.r1, p.r2)[0, 1],
                                                                        *np.percentile(boot, [2.5, 97.5])))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
