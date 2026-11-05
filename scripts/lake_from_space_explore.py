"""Lake from Space: a bounded exploratory analysis of the committed satellite lake observations.

Exploratory, on seen data (docs/LAKE-FROM-SPACE-EXPLORATION-2026-11.md). It reads only committed files, fetches nothing
and imports no dipcast code, so it cannot write to the state database or a cache:

- data/research/lake_observations.v1.json (contract docs/LAKE-OBSERVATIONS-CONTRACT-v1.md)
- docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-score.json (#386's own pairing counts)

It writes one JSON file, the exhibit's analysis panel and the document's tables.

    uv run python scripts/lake_from_space_explore.py [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OBS = ROOT / "data/research/lake_observations.v1.json"
SCORE386 = ROOT / "docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-score.json"
OUT = ROOT / "prototypes/research-lab/lake-from-space/exploration.json"

SEED = 20261101          # fixed before any figure below was computed
DRAWS = 2000
SEASON = (5, 6, 7, 8, 9)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    # average ties
    for v in np.unique(x):
        m = x == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def spearman(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return float("nan")
    ra, rb = ranks(a), ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def cluster_boot(clusters: dict, stat, rng) -> tuple[float, float]:
    """95% interval of stat(rows) by resampling whole lakes."""
    keys = list(clusters)
    vals = []
    for _ in range(DRAWS):
        pick = rng.integers(0, len(keys), len(keys))
        rows = [r for i in pick for r in clusters[keys[i]]]
        v = stat(rows)
        if v == v:
            vals.append(v)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def d(s: str) -> date:
    return date.fromisoformat(s[:10])


def lab_value(row) -> float:
    # #386's handling: "<" at half the reported limit, ">" at the limit
    v = float(row["value"])
    return v / 2 if row.get("censored") == "<" else v


def build_pairs(obs: dict) -> list[dict]:
    """#386's pairing on the committed readings: a lab sample on day d takes the primary in-season reading dated d-1..d+1,
    nearest first, the earlier on a tie. One pair a sample. Sites sharing a WQA point are counted once."""
    pairs, seen_points = [], set()
    for lake in obs["lakes"]:
        point = (lake.get("site_ids") or {}).get("wqa_point")
        if not lake["lab"] or point in seen_points:
            continue
        seen_points.add(point)
        reads = {}
        for s in lake["series"]:
            if s.get("primary") and s["season"] == "in_season" and not s.get("experimental"):
                reads[d(s["date"])] = s
        for lab in lake["lab"]:
            day = d(lab["sample_time"])
            if day.month not in SEASON:
                continue
            for lag in (0, -1, 1):
                s = reads.get(date.fromordinal(day.toordinal() + lag))
                if s:
                    pairs.append({
                        "lake_id": lake["lake_id"], "point": point, "water_body": lake["water_body"],
                        "lake_type": lake.get("lake_type"), "sample_day": day.isoformat(), "scene_day": s["date"],
                        "lag": lag, "ndci": s["ndci"], "chl": lab_value(lab), "censored": lab.get("censored"),
                        "season": day.year,
                    })
                    break
    return pairs


def by_lake(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["lake_id"]].append(r)
    return out


def pooled_rho(rows):
    return spearman([r["ndci"] for r in rows], [np.log10(r["chl"]) for r in rows])


def changes(pairs: list[dict]) -> list[dict]:
    """Consecutive pairs at one lake within one season: did the satellite index move the same way as lab chlorophyll?"""
    out = []
    groups = defaultdict(list)
    for p in pairs:
        groups[(p["lake_id"], p["season"])].append(p)
    for (lake, season), rows in groups.items():
        rows.sort(key=lambda r: r["sample_day"])
        for a, b in zip(rows, rows[1:]):
            dc = np.log10(b["chl"]) - np.log10(a["chl"])
            dn = b["ndci"] - a["ndci"]
            out.append({"lake_id": lake, "lake_type": a["lake_type"], "season": season, "from": a["sample_day"],
                        "to": b["sample_day"], "days": (d(b["sample_day"]) - d(a["sample_day"])).days,
                        "d_ndci": round(dn, 5), "d_log10_chl": round(float(dc), 4)})
    return out


def agreement(rows, min_dn=0.0):
    use = [r for r in rows if abs(r["d_ndci"]) > min_dn and r["d_log10_chl"] != 0]
    if not use:
        return float("nan"), 0
    same = sum(1 for r in use if (r["d_ndci"] > 0) == (r["d_log10_chl"] > 0))
    return same / len(use), len(use)


def calendar_check(pairs: list[dict], ch: list[dict], rng) -> dict:
    """Could the calendar alone call the direction? For each change, the other lakes' mean log10 lab value by month gives
    a 'seasonal' guess (up if the later month is usually higher). Compared on the changes where that guess is not a
    tie, against the index on the same changes."""
    month = {(p["lake_id"], p["sample_day"]): int(p["sample_day"][5:7]) for p in pairs}
    rows = []
    for c in ch:
        others = [p for p in pairs if p["lake_id"] != c["lake_id"]]
        means = {}
        for m in SEASON:
            v = [np.log10(p["chl"]) for p in others if int(p["sample_day"][5:7]) == m]
            means[m] = np.mean(v) if v else np.nan
        m0, m1 = month[(c["lake_id"], c["from"])], month[(c["lake_id"], c["to"])]
        guess = means[m1] - means[m0] if m0 != m1 else 0.0
        if guess == 0 or guess != guess or c["d_log10_chl"] == 0:
            continue
        rows.append({**c, "calendar_up": bool(guess > 0)})

    def share(rr, key):
        if not rr:
            return float("nan")
        if key == "calendar":
            return sum(1 for r in rr if r["calendar_up"] == (r["d_log10_chl"] > 0)) / len(rr)
        return sum(1 for r in rr if (r["d_ndci"] > 0) == (r["d_log10_chl"] > 0)) / len(rr)

    groups = by_lake(rows)
    cal, idx = share(rows, "calendar"), share(rows, "index")
    diff_ci = cluster_boot(groups, lambda rr: share(rr, "index") - share(rr, "calendar"), rng)
    return {"changes": len(rows), "calendar_same_direction": round(cal, 3), "index_same_direction": round(idx, 3),
            "index_minus_calendar": round(idx - cal, 3), "ci": [round(diff_ci[0], 3), round(diff_ci[1], 3)],
            "note": "Changes between two different months only. The calendar guess uses other lakes' monthly means "
                    "of log10 lab chlorophyll from the same pairs."}


def anomaly_rows(pairs):
    """Each pair minus its lake-season means: what is left is change within a lake's season."""
    groups = defaultdict(list)
    for p in pairs:
        groups[(p["lake_id"], p["season"])].append(p)
    out = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        mn = np.mean([r["ndci"] for r in rows])
        mc = np.mean([np.log10(r["chl"]) for r in rows])
        for r in rows:
            out.append({**r, "a_ndci": r["ndci"] - mn, "a_chl": np.log10(r["chl"]) - mc})
    return out


def anomaly_rho(rows):
    return spearman([r["a_ndci"] for r in rows], [r["a_chl"] for r in rows])


def month_removed_rho(rows):
    """The within-season anomalies with each month's mean anomaly (over these rows) taken off both, so a shared rise or
    fall through the summer cannot make the correlation on its own."""
    if len(rows) < 3:
        return float("nan")
    m = np.array([int(r["sample_day"][5:7]) for r in rows])
    a = np.array([r["a_ndci"] for r in rows])
    c = np.array([r["a_chl"] for r in rows])
    for k in np.unique(m):
        a[m == k] -= a[m == k].mean()
        c[m == k] -= c[m == k].mean()
    return spearman(a, c)


def gaps(obs: dict) -> dict:
    """Waiting time between usable in-season readings at the lakes whose record holds every image."""
    all_gaps, month_hits, month_days = [], defaultdict(int), defaultdict(int)
    per_lake = {}
    for lake in obs["lakes"]:
        if lake["series_scope"] != "every_scene" or not lake["mask"]["passes_size_rule"]:
            continue
        days = sorted({d(s["date"]) for s in lake["series"] if s.get("primary") and s["season"] == "in_season"
                       and not s.get("experimental")})
        lake_gaps = []
        for season in sorted({x.year for x in days}):
            ds = [x for x in days if x.year == season]
            start, end = date(season, 5, 1), date(season, 9, 30)
            edges = [start] + ds + [end]
            lake_gaps += [(b - a).days for a, b in zip(edges, edges[1:]) if (b - a).days > 0]
            for m in SEASON:
                month_days[m] += 1
                month_hits[m] += any(x.month == m for x in ds)
        all_gaps += lake_gaps
        if lake_gaps:
            per_lake[lake["lake_id"]] = {"name": lake["name"], "median_gap_days": float(np.median(lake_gaps)),
                                         "longest_gap_days": int(max(lake_gaps))}
    g = np.array(all_gaps)
    return {
        "lakes": len(per_lake),
        "median_gap_days": float(np.median(g)), "p75_gap_days": float(np.percentile(g, 75)),
        "p90_gap_days": float(np.percentile(g, 90)), "longest_gap_days": int(g.max()),
        "share_gaps_over_14_days": round(float((g > 14).mean()), 3),
        "months_with_a_reading": {str(m): round(month_hits[m] / month_days[m], 3) for m in SEASON},
        "per_lake": per_lake,
        "note": "Gaps are counted inside 1 May-30 September of each season with images, season edges included. "
                "Seasons with no images at all (2022) are not counted as gaps.",
    }


def detectable(obs: dict) -> dict:
    """Within-season spread of the index at a lake against the repeat-reading noise the export measured."""
    q = obs["quality"]
    spreads = []
    for lake in obs["lakes"]:
        if lake["series_scope"] != "every_scene":
            continue
        by_season = defaultdict(list)
        for s in lake["series"]:
            if s.get("primary") and s["season"] == "in_season" and not s.get("experimental"):
                by_season[s["date"][:4]].append(s["ndci"])
        for season, v in by_season.items():
            if len(v) >= 6:
                v = np.array(v)
                spreads.append({"lake_id": lake["lake_id"], "season": season, "n": len(v),
                                "p10_p90": float(np.percentile(v, 90) - np.percentile(v, 10))})
    p = np.array([s["p10_p90"] for s in spreads])
    return {
        "repeat_median": q["same_date_abs_difference_median"], "repeat_p90": q["same_date_abs_difference_p90"],
        "lake_seasons": len(spreads),
        "season_spread_p10_p90_median": float(np.median(p)),
        "share_spread_over_repeat_p90": round(float((p > q["same_date_abs_difference_p90"]).mean()), 3),
        "note": "Spread is the 10th-to-90th percentile range of one lake's usable in-season readings in one season "
                "(seasons with 6 or more). Repeat noise is two readings of one lake on one date.",
    }


def pairing_yield(score: dict, obs: dict) -> dict:
    """#386's own counts: lab samples per season and how many found a usable scene within a day."""
    types = {}
    for lake in obs["lakes"]:
        pt = (lake.get("site_ids") or {}).get("wqa_point")
        if pt and lake.get("lake_type"):
            types[pt] = lake["lake_type"]
    by = defaultdict(lambda: {"samples": 0, "with_reading": 0, "points": set(), "points_paired": set()})
    for row in score["pairing"]:
        t = types.get(row["wqa_point"], "unknown")
        for key in (f"{t}:{row['season']}", f"all:{row['season']}"):
            b = by[key]
            b["samples"] += row["samples"]
            b["with_reading"] += row["with_reading"]
            b["points"].add(row["wqa_point"])
            if row["with_reading"]:
                b["points_paired"].add(row["wqa_point"])
    table = []
    for key in sorted(by):
        t, season = key.split(":")
        b = by[key]
        table.append({"group": t, "season": int(season), "samples": b["samples"], "pairs": b["with_reading"],
                      "rate": round(b["with_reading"] / b["samples"], 3) if b["samples"] else None,
                      "points": len(b["points"]), "points_paired": len(b["points_paired"])})
    shallow = [r for r in table if r["group"] == "shallow" and r["season"] != 2022]
    return {"table": table,
            "shallow_pairs_per_season": [r["pairs"] for r in shallow],
            "shallow_lakes_paired_per_season": [r["points_paired"] for r in shallow],
            "protocol_minimum": {"pairs": 30, "lakes": 6,
                                 "source": "docs/SATELLITE-RECOVERY-2026-10.md section 5 (draft)"}}


def outliers(obs: dict) -> list[dict]:
    """In-season primary readings far below a lake's usual range: candidates for a quality look, not removals."""
    out = []
    for lake in obs["lakes"]:
        v = [s for s in lake["series"] if s.get("primary") and s["season"] == "in_season"]
        if len(v) < 5:
            continue
        x = np.array([s["ndci"] for s in v])
        med, mad = np.median(x), np.median(np.abs(x - np.median(x))) or 0.01
        for s in v:
            z = (s["ndci"] - med) / (1.4826 * mad)
            if abs(z) > 5:
                out.append({"lake_id": lake["lake_id"], "name": lake["name"], "date": s["date"], "ndci": s["ndci"],
                            "lake_median": round(float(med), 4), "robust_z": round(float(z), 1),
                            "clear_core": s["clear_core"], "n_core": s["n_core"],
                            "sun_elevation_deg": s.get("sun_elevation_deg")})
    return sorted(out, key=lambda r: -abs(r["robust_z"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    before = {str(p.relative_to(ROOT)): sha(p) for p in (OBS, SCORE386)}
    obs = json.loads(OBS.read_text())
    score = json.loads(SCORE386.read_text())
    rng = np.random.default_rng(SEED)

    pairs = build_pairs(obs)
    lakes = by_lake(pairs)
    rho = pooled_rho(pairs)
    rho_ci = cluster_boot(lakes, pooled_rho, rng)

    anom = anomaly_rows(pairs)
    a_rho = anomaly_rho(anom)
    a_ci = cluster_boot(by_lake(anom), anomaly_rho, rng)
    m_rho = month_removed_rho(anom)
    m_ci = cluster_boot(by_lake(anom), month_removed_rho, rng)
    a_type = {}
    for t in ("shallow", "deeper"):
        rows = [r for r in anom if r["lake_type"] == t]
        a_type[t] = {"rows": len(rows), "lakes": len(by_lake(rows)), "rho": anomaly_rho(rows),
                     "ci": cluster_boot(by_lake(rows), anomaly_rho, rng)}

    ch = changes(pairs)
    ch_lakes = by_lake(ch)
    agree = {}
    for label, cut in (("any", 0.0), ("over_repeat_median", obs["quality"]["same_date_abs_difference_median"]),
                       ("over_repeat_p90", obs["quality"]["same_date_abs_difference_p90"])):
        share, n = agreement(ch, cut)
        lo, hi = cluster_boot(ch_lakes, lambda rows, c=cut: agreement(rows, c)[0], rng)
        agree[label] = {"min_abs_d_ndci": cut, "changes": n, "same_direction": round(share, 3),
                        "ci": [round(lo, 3), round(hi, 3)]}
    agree_type = {}
    for t in ("shallow", "deeper"):
        rows = [r for r in ch if r["lake_type"] == t]
        share, n = agreement(rows)
        lo, hi = cluster_boot(by_lake(rows), lambda rr: agreement(rr)[0], rng)
        agree_type[t] = {"changes": n, "lakes": len(by_lake(rows)), "same_direction": round(share, 3),
                         "ci": [round(lo, 3), round(hi, 3)]}

    result = {
        "schema": "swimsignal.lake-from-space-exploration",
        "version": "0.1.0",
        "status": "exploratory, on data already seen by #386; not a test and not a confirmation",
        "seed": SEED, "draws": DRAWS,
        "inputs_sha256": before,
        "reproduction": {
            "pairs": len(pairs), "lakes": len(lakes), "pooled_rho": round(rho, 3),
            "ci": [round(rho_ci[0], 3), round(rho_ci[1], 3)],
            "lag_days": {str(k): sum(1 for p in pairs if p["lag"] == k) for k in (-1, 0, 1)},
            "record_386": {"pairs": 207, "lakes": 38, "rho": 0.502, "ci": [0.2997, 0.667],
                           "lag_days": score["lag_days"]},
            "note": "Rebuilt from the published observation file, not #386's private rows. Three Windermere and "
                    "Frensham points use the bathing water's 300 m core here, not the WQA point's own.",
        },
        "within_season": {
            "rows": len(anom), "lakes": len(by_lake(anom)), "rho": round(a_rho, 3),
            "ci": [round(a_ci[0], 3), round(a_ci[1], 3)],
            "month_removed": {"rho": round(m_rho, 3), "ci": [round(m_ci[0], 3), round(m_ci[1], 3)]},
            "by_type": {t: {**v, "rho": round(v["rho"], 3), "ci": [round(v["ci"][0], 3), round(v["ci"][1], 3)]}
                        for t, v in a_type.items()},
            "note": "Each pair minus its lake-season mean of index and log10 lab value, so lake level and the season's "
                    "level are removed; only change inside a season is left. Lake-seasons with one pair drop out. The "
                    "shallow/deeper split is #386's, stated before its run; neither group is a lead finding here.",
        },
        "direction": {"by_threshold": agree, "by_type": agree_type, "calendar": calendar_check(pairs, ch, rng),
                      "changes": ch,
                      "note": "Consecutive pairs at one lake in one season. 0.5 is a coin toss."},
        "detectable_change": detectable(obs),
        "gaps": gaps(obs),
        "pairing_yield": pairing_yield(score, obs),
        "quality_flags": outliers(obs),
        "pairs": pairs,
    }
    after = {str(p.relative_to(ROOT)): sha(p) for p in (OBS, SCORE386)}
    assert before == after, "an input changed during the run"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, default=float) + "\n")
    summary = {k: result[k] for k in ("reproduction", "within_season")}
    summary["direction"] = {"by_threshold": agree, "by_type": agree_type, "calendar": result["direction"]["calendar"]}
    summary["detectable_change"] = {k: v for k, v in result["detectable_change"].items() if k != "note"}
    summary["gaps"] = {k: v for k, v in result["gaps"].items() if k not in ("per_lake", "note")}
    summary["pairing_yield"] = {k: v for k, v in result["pairing_yield"].items() if k != "table"}
    summary["quality_flags"] = result["quality_flags"][:8]
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
