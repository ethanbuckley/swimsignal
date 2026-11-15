"""Exploratory readout for docs/WESSEX-RIVER-SAMPLES-CHECK-2026-11.md, as its protocol (commit 434ce288) fixes it.
No network, no model run: committed files only.

    uv run python scripts/wessex_river_samples_check.py

A. Level and order at the three points, from the soil-moisture rivers test's committed per-station figures
   (docs/SOIL-MOISTURE-RIVERS-TEST-2026-11.json): observed share over 900 with a Wilson 95% interval, the mean
   reference and candidate estimates (the candidate is the live river rule, #361), and within-point rho with an
   approximate Fisher-z interval. Both intervals treat samples as independent, so they are too narrow.
B. From the Wessex export alone: share over 900 in May-Sep and Oct-Apr, 2021-25; at Farleigh Hungerford, beside the
   Environment Agency's bathing water samples in May-Sep 2024 and 2025 (ecoli_evidence.v1.json).
C. Post hoc, defined after A and B were seen, as the protocol's named next step when the Frome points read low: at the
   Farleigh Hungerford bathing water, the EA samples' share over 900 beside the mean leave-one-year-out hindsight
   estimate (ecoli_evidence.v1.json; EA samples, so in the fit's population, each estimate out of its own year).
D. Post hoc, the step C's result named: at Farleigh, Wessex's and the EA's samples taken on the same day (2024-25),
   each pair's log10 ratio, Wessex over EA.
Writes docs/WESSEX-RIVER-SAMPLES-CHECK-2026-11.json.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SM = ROOT / "docs" / "SOIL-MOISTURE-RIVERS-TEST-2026-11.json"
WSX = ROOT / "data" / "research" / "wessex_river_samples.v1.json"
EA = ROOT / "data" / "research" / "ecoli_evidence.v1.json"
OUT = ROOT / "docs" / "WESSEX-RIVER-SAMPLES-CHECK-2026-11.json"
Z = 1.959964
# The soil-moisture test's station strings for each point (f"wsx {lat:.5f},{lon:.5f}"): Warleigh's point moved its
# sixth decimal in 2025, so it has two.
STATIONS = {
    "avon-warleigh-weir": ["wsx 51.37705,-2.30064", "wsx 51.37705,-2.30063"],
    "bw-ukk2301-36051": ["wsx 51.30928,-2.28610"],
    "frome-tellisford-weir": ["wsx 51.29962,-2.27946"],
}
IN_SEASON = range(5, 10)


def wilson(k: int, n: int) -> list[float]:
    p = k / n
    c = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return [round(c - h, 3), round(c + h, 3)]


def fisher(rho: float, n: int) -> list[float] | None:
    if n < 5:
        return None
    z, se = math.atanh(rho), 1 / math.sqrt(n - 3)
    return [round(math.tanh(z - Z * se), 3), round(math.tanh(z + Z * se), 3)]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def part_a(sm: dict) -> dict:
    per = {s["station"]: s for s in sm["per_station"] if s["region"] == "Wessex"}
    out = {}
    for spot, names in STATIONS.items():
        rows = [per[n] for n in names]
        n, k = sum(r["n"] for r in rows), sum(r["exceedances"] for r in rows)
        mean = lambda key: round(sum(r[key] * r["n"] for r in rows) / n, 4)
        obs, ci = round(k / n, 3), wilson(k, n)
        ref, cand = mean("mean_reference"), mean("mean_candidate")
        out[spot] = {
            "samples": n, "over_900": k, "observed_share": obs, "observed_ci95": ci,
            "mean_reference": ref, "mean_candidate": cand, "gap_observed_minus_candidate": round(obs - cand, 3),
            "level": "reads low" if cand < ci[0] else "reads high" if cand > ci[1] else "within",
            "rho": [{"station": r["station"], "n": r["n"], "reference": round(r["rho_reference"], 3),
                     "candidate": round(r["rho_candidate"], 3), "candidate_ci95": fisher(r["rho_candidate"], r["n"])}
                    for r in rows],
        }
    return out


def part_b(wsx: dict, ea: dict) -> dict:
    out = {}
    for x in wsx["sites"]:
        s = [a for a in x["samples"] if a["over"] is not None and 2021 <= int(a["t"][:4]) <= 2025]
        split = {}
        for name, keep in (("may_sep", lambda m: m in IN_SEASON), ("oct_apr", lambda m: m not in IN_SEASON)):
            z = [a for a in s if keep(int(a["t"][5:7]))]
            k = sum(a["over"] for a in z)
            split[name] = {"samples": len(z), "over_900": k, "share": round(k / len(z), 3), "ci95": wilson(k, len(z))}
        out[x["spot_id"]] = split
    far = next(x for x in wsx["sites"] if x["spot_id"] == "bw-ukk2301-36051")
    bw = next(x for x in ea["sites"] if x["spot_id"] == "bw-ukk2301-36051")
    side = {}
    for y in (2024, 2025):
        w = [a for a in far["samples"] if a["t"].startswith(str(y)) and int(a["t"][5:7]) in IN_SEASON and a["over"] is not None]
        e = [a for a in bw["samples"] if a["t"].startswith(str(y)) and int(a["t"][5:7]) in IN_SEASON and a.get("over") is not None]
        side[str(y)] = {"wessex_point": {"samples": len(w), "over_900": sum(a["over"] for a in w)},
                        "ea_bathing_water": {"samples": len(e), "over_900": sum(bool(a["over"]) for a in e)}}
    out["farleigh_side_by_side"] = side
    return out


def part_c(ea: dict) -> dict:
    bw = next(x for x in ea["sites"] if x["spot_id"] == "bw-ukk2301-36051")
    h = [a for a in bw["samples"] if a["hindsight"] is not None and a.get("over") is not None]
    out = {}
    for y in ("2024", "2025", "2026", "all"):
        z = [a for a in h if y == "all" or a["t"].startswith(y)]
        k = sum(bool(a["over"]) for a in z)
        out[y] = {"samples": len(z), "over_900": k, "observed_share": round(k / len(z), 3), "observed_ci95": wilson(k, len(z)),
                  "mean_hindsight": round(sum(a["hindsight"] for a in z) / len(z), 3)}
    far = next(x for x in json.loads(WSX.read_text())["sites"] if x["spot_id"] == "bw-ukk2301-36051")
    wd, ed = {a["t"][:10]: a for a in far["samples"]}, {a["t"][:10]: a for a in bw["samples"]}
    pairs = [{"day": d, "wessex": wd[d]["ecoli"], "wessex_time": wd[d]["t"][11:16], "ea": ed[d]["ecoli"],
              "ea_t": ed[d]["t"], "log10_ratio": round(math.log10(wd[d]["ecoli"] / ed[d]["ecoli"]), 3)}
             for d in sorted(set(wd) & set(ed)) if not wd[d]["q"] and not ed[d]["q"]]
    r = sorted(x["log10_ratio"] for x in pairs)
    med = (r[len(r) // 2] + r[(len(r) - 1) // 2]) / 2 if r else None
    return {"post_hoc": True, "farleigh_bathing_water_ea": out,
            "farleigh_same_day": {"pairs": pairs, "wessex_higher": sum(x > 0 for x in r), "equal": sum(x == 0 for x in r),
                                  "median_log10_ratio": None if med is None else round(med, 3)}}


def main() -> None:
    sm, wsx, ea = (json.loads(p.read_text()) for p in (SM, WSX, EA))
    doc = {"protocol": "docs/WESSEX-RIVER-SAMPLES-CHECK-2026-11.md at 434ce288", "exploratory": True,
           "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (SM, WSX, EA)},
           "a_level_and_order": part_a(sm), "b_descriptive": part_b(wsx, ea), "c_post_hoc": part_c(ea)}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps(doc, indent=1))


if __name__ == "__main__":
    main()
