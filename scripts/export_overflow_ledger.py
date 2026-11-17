"""The overflow ledger (LEDGER stage 1, docs/OVERFLOW-LEDGER-CONTRACT-v1.md): what each monitored storm overflow
contributes to the forecast model's exposure at the listed swim spots, rolled up per overflow.

It makes no exposure calculation of its own. The weight of each overflow at each spot is the forecast's, as Research Lab
exhibit 2 exports it at every build (scripts/lab_pollution_paths.py `export`, which calls transport.upstream_overflows
with the production settings). This script reads that export and adds it up per overflow. An account of the model, not
of measured bacteria: a weight is survival times a dilution factor, from 0 to 1, not a share of a spill that arrives.

Offline; nothing is fetched. Two ways to run it:

    # 1. from an export already made (the repository's copy, or a site build's lab/assets/paths/)
    PYTHONPATH=src python scripts/export_overflow_ledger.py --paths prototypes/research-lab/assets/paths

    # 2. remake the export first, in scratch, from the cached network and overflow table (AGENTS.md: scratch
    #    DIPCAST_ROOT and DIPCAST_STATE whose data folders link the inputs; the caches are hashed before and after)
    DIPCAST_ROOT=<scratch> DIPCAST_STATE=<scratch>/state PYTHONPATH=src python scripts/export_overflow_ledger.py \
        --remake <scratch>/paths

    python scripts/export_overflow_ledger.py --check     # the committed file against this contract
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "data" / "research" / "overflow_ledger.v1.json"
SCHEMA, VERSION = "swimsignal.overflow-ledger", "1.0.0"
ROUND = 5   # the export's own rounding of a weight

CLAIM = {
    "public_wording": (
        "An account of SwimSignal's forecast model, not of measured bacteria. For each monitored storm overflow it "
        "adds up the weight the model gives that overflow at every listed swim spot it reaches. A weight is the "
        "model's survival factor times its dilution factor, from 0 to 1. It is not the share of a spill that arrives, "
        "and it is not a measurement."),
    "not_claimed": [
        "that any overflow caused a sample result, or any share of the bacteria at a spot",
        "that any overflow or company broke a permit or a rule",
        "how much any overflow discharged: the model has no spill volume",
        "that the weights match real water: travel times and dilution are the model's settings, not measurements",
        "anything about sources the model does not hold: treated sewage, farms, septic tanks, road and town runoff",
        "that a spot the table leaves out is clean, or that an overflow it leaves out reaches no swimmer",
    ],
    "evidence": {
        "text": ("At 59 river points no model here had seen, the production estimate put a point's days in order "
                 "with a within-point correlation of 0.376. Rain in the last 48 hours alone gave 0.355. So the "
                 "overflow chain adds little to the order at rivers."),
        "record": "docs/RIVER-UNSEEN-PROTOCOL-2026-11.md",
        "read": "2026-11-16",
    },
}

DEFINITIONS = {
    "weight": ("The forecast's own factor for one overflow at one spot: survival over the model's travel time (T90 in "
               "settings) times the model's dilution factor. From 0 to 1. Read from the exhibit 2 export, not recomputed."),
    "spots_reached": "Listed spots with this overflow upstream within the model's trace limit (settings.max_upstream_km).",
    "weight_sum": "This overflow's weights added over the spots it reaches.",
    "weight_max": "Its largest weight at any one spot; max_spot is that spot.",
    "top_at": "The number of spots where this overflow has the largest weight of all the spot's overflows.",
    "spills_a_year": ("The Environment Agency's long-term average spill count for the overflow, from the latest annual "
                      "return the overflow table holds. A count of spills in a year, not of days and not of volume."),
    "weighted_spills": ("The year figure: spills_a_year times weight, added over the spots reached. Units are "
                        "weighted spills a year. It is the model's long-run accounting for an average year. It is "
                        "not a count of days at any level, and it is null where the return gives no average."),
    "group": ("Spots joined by at least one shared upstream overflow, with every overflow that reaches any of them. "
              "A catchment as the model sees it, not a mapped catchment boundary."),
    "season_figure_not_made": (
        "A count of modelled high-level spot-days per overflow in a bathing season is not in this version. The "
        "existing outputs do not support it: the export holds weights and yearly averages, and the forecast log holds "
        "each overflow's daily chance only from 12 October 2026 (docs/CATCH-SIM-2026-12.md), after the season. A "
        "season hindcast would be a second calculation, which stage 1 does not make."),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _groups(reach: dict[str, set[int]], n_spots: int) -> list[list[int]]:
    """Spots joined by a shared overflow (connected parts of the spot-overflow graph), largest first."""
    parent = list(range(n_spots))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for spots in reach.values():
        first, *rest = sorted(spots)
        for s in rest:
            parent[find(s)] = find(first)
    parts: dict[int, list[int]] = {}
    for s in sorted({s for spots in reach.values() for s in spots}):
        parts.setdefault(find(s), []).append(s)
    return sorted(parts.values(), key=lambda p: (-len(p), p[0]))


def rollup(paths: Path, generated_at: str | None = None, inputs: list[dict] | None = None) -> dict:
    """The ledger from one exhibit 2 export folder (index.json and a file a spot)."""
    index = json.loads((paths / "index.json").read_text())
    spots, per_spot = [], {}
    for rec in index["spots"]:
        f = paths / f"{rec['id']}.json"
        status = "error" if "error" in rec else "off_network" if rec.get("note") else "traced"
        ovs = json.loads(f.read_text())["overflows"] if status == "traced" and f.is_file() else []
        # a missing name or watercourse is a NaN in the export: null here, so the file is plain JSON
        ovs = [{k: None if isinstance(v, float) and v != v else v for k, v in o.items()} for o in ovs]
        if status == "traced" and not ovs:
            status = "no_overflow"
        per_spot[len(spots)] = ovs
        spots.append({"id": rec["id"], "name": rec["name"], "kind": rec["kind"], "area": rec.get("area"),
                      "status": status, "overflows": len(ovs),
                      "weight_sum": round(sum(o["weight"] or 0 for o in ovs), ROUND)})

    by_id: dict[str, dict] = {}
    for si, ovs in per_spot.items():
        top = max((o["weight"] or 0 for o in ovs), default=0)
        for o in ovs:
            e = by_id.setdefault(o["id"], {"meta": o, "links": []})
            e["links"].append((si, o["weight"] or 0.0, o["travel_h"], (o["weight"] or 0) == top and top > 0))
    reach = {k: {ln[0] for ln in e["links"]} for k, e in by_id.items()}
    groups = _groups(reach, len(spots))
    group_of = {s: gi for gi, g in enumerate(groups) for s in g}

    companies = sorted({e["meta"]["company"] or "Not stated" for e in by_id.values()})
    rows = []
    for oid, e in by_id.items():
        m, links = e["meta"], sorted(e["links"], key=lambda ln: (-ln[1], ln[0]))
        wsum = sum(ln[1] for ln in links)
        spills = m.get("spills_a_year")
        rows.append({
            "site_id": oid, "name": m["name"], "company": companies.index(m["company"] or "Not stated"),
            "water": m.get("water"), "lat": m["lat"], "lon": m["lon"], "spills_a_year": spills,
            "spots_reached": len(links), "weight_sum": round(wsum, ROUND), "weight_max": round(links[0][1], ROUND),
            "max_spot": links[0][0], "top_at": sum(1 for ln in links if ln[3]),
            "weighted_spills": None if spills is None else round(spills * wsum, 2),
            "group": group_of[links[0][0]],
            "links": [[ln[0], round(ln[1], ROUND), ln[2]] for ln in links]})
    rows.sort(key=lambda r: (-r["weight_sum"], r["site_id"]))
    cols = ["site_id", "name", "company", "water", "lat", "lon", "spills_a_year", "spots_reached", "weight_sum",
            "weight_max", "max_spot", "top_at", "weighted_spills", "group", "links"]

    by_company = []
    for ci, name in enumerate(companies):
        mine = [r for r in rows if r["company"] == ci]
        by_company.append({"company": name, "overflows": len(mine), "links": sum(r["spots_reached"] for r in mine),
                           "spots": len({ln[0] for r in mine for ln in r["links"]}),
                           "weight_sum": round(sum(r["weight_sum"] for r in mine), 3),
                           "weighted_spills": round(sum(r["weighted_spills"] or 0 for r in mine), 1),
                           "no_average": sum(1 for r in mine if r["weighted_spills"] is None)})
    by_company.sort(key=lambda c: -c["weight_sum"])

    group_rows = []
    for gi, g in enumerate(groups):
        mine = [r for r in rows if r["group"] == gi]
        lead = max(g, key=lambda s: (spots[s]["overflows"], -s))
        group_rows.append({"id": gi, "name": spots[lead]["name"], "spots": g, "overflows": len(mine),
                           "links": sum(r["spots_reached"] for r in mine)})

    count = lambda st: sum(1 for s in spots if s["status"] == st)   # noqa: E731
    return {
        "schema": SCHEMA, "version": VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "stage": "exploratory: model accounting, not a measurement and not a test",
        "source_export": {"made": index["made"], "script": "scripts/lab_pollution_paths.py export",
                          "settings": index["settings"], "inputs": index.get("inputs")},
        "inputs": inputs or [],
        "code_sha256": sha256(Path(__file__)),
        "attribution": index["credit"],
        "claim": CLAIM,
        "definitions": DEFINITIONS,
        "coverage": {"spots": len(spots), "spots_with_overflows": count("traced"), "spots_no_overflow": count("no_overflow"),
                     "spots_off_network": count("off_network"), "spots_error": count("error"),
                     "overflows": len(rows), "links": sum(r["spots_reached"] for r in rows),
                     "overflows_reaching_one_spot": sum(1 for r in rows if r["spots_reached"] == 1),
                     "overflows_without_average": sum(1 for r in rows if r["spills_a_year"] is None),
                     "groups": len(groups)},
        "spots": spots,
        "companies": companies,
        "company": by_company,
        "groups": group_rows,
        "overflows": {c: [r[c] for r in rows] for c in cols},
    }


def check(doc: dict) -> list[str]:
    """Faults in a ledger file against the contract; empty when it holds."""
    bad = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        bad.append("schema or major version")
    ov, spots = doc["overflows"], doc["spots"]
    n = len(ov["site_id"])
    if any(len(v) != n for v in ov.values()):
        bad.append("overflow columns differ in length")
    if len(set(ov["site_id"])) != n:
        bad.append("an overflow is listed twice")
    per_spot = [0.0] * len(spots)
    counts = [0] * len(spots)
    for i in range(n):
        links = ov["links"][i]
        ws = [ln[1] for ln in links]
        if any(not 0 <= w <= 1 for w in ws):
            bad.append(f"{ov['site_id'][i]}: a weight outside 0 to 1")
        if len(links) != ov["spots_reached"][i] or abs(sum(ws) - ov["weight_sum"][i]) > 1e-4 or abs(max(ws) - ov["weight_max"][i]) > 1e-9:
            bad.append(f"{ov['site_id'][i]}: roll-up does not match its links")
        sp = ov["spills_a_year"][i]
        if (sp is None) != (ov["weighted_spills"][i] is None) or (sp is not None and abs(sp * sum(ws) - ov["weighted_spills"][i]) > 0.02):
            bad.append(f"{ov['site_id'][i]}: weighted spills")
        for s, w, _ in links:
            per_spot[s] += w
            counts[s] += 1
    for s, rec in enumerate(spots):
        if counts[s] != rec["overflows"] or abs(per_spot[s] - rec["weight_sum"]) > 1e-3:
            bad.append(f"{rec['id']}: the spot's total does not match the links")
        if (rec["status"] == "traced") != (rec["overflows"] > 0):
            bad.append(f"{rec['id']}: status")
    cov = doc["coverage"]
    if cov["overflows"] != n or cov["links"] != sum(ov["spots_reached"]) or cov["spots"] != len(spots):
        bad.append("coverage counts")
    if sorted(s for g in doc["groups"] for s in g["spots"]) != [s for s, r in enumerate(spots) if r["overflows"]]:
        bad.append("groups do not cover each spot with overflows once")
    for k in ("public_wording", "not_claimed", "evidence"):
        if not doc.get("claim", {}).get(k):
            bad.append(f"claim.{k}")
    if not doc.get("attribution"):
        bad.append("attribution")
    return bad


def remake(folder: Path) -> list[dict]:
    """Exhibit 2's export into `folder` from the cached network and overflow table, the caches hashed before and after."""
    assert os.environ.get("DIPCAST_ROOT") and os.environ.get("DIPCAST_STATE"), "set scratch DIPCAST_ROOT and DIPCAST_STATE"
    assert REPO not in folder.resolve().parents, "the remade export goes to scratch, not into the repository"
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(HERE))
    from dipcast import config
    assert config.ROOT.resolve() != REPO.resolve(), "DIPCAST_ROOT must be a scratch root"
    shared = [config.PROCESSED / "river_network.pkl", config.PROCESSED / "overflows.parquet",
              config.PROCESSED / "lakes.parquet", config.RIVERS_GPKG]
    before = {p.name: sha256(p.resolve()) for p in shared if p.exists()}
    import lab_pollution_paths as lpp
    from dipcast.model.forecast import _net, _overflows
    net, ov = _net(), _overflows()
    lpp.export(folder, lpp.spots_frame(), net, ov, {
        "overflows": "data/processed/overflows.parquet (the cached overflow table)",
        "network": "OS Open Rivers via data/processed/river_network.pkl, mended as the build mends it"},
        say=lambda m: None)
    after = {p.name: sha256(p.resolve()) for p in shared if p.exists()}
    assert before == after, "a shared input changed during the run"
    wrote = [p for p in Path(os.environ["DIPCAST_ROOT"]).rglob("*") if p.is_file() and not p.is_symlink()]
    assert not wrote, f"files written into the scratch root: {wrote[:3]}"
    return [{"file": k, "sha256": v, "unchanged_after": True} for k, v in before.items()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--paths", type=Path, help="an exhibit 2 export folder to roll up")
    ap.add_argument("--remake", type=Path, help="remake the export into this scratch folder first, then roll it up")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="check the file at --out and write nothing")
    a = ap.parse_args()
    if a.check:
        bad = check(json.loads(a.out.read_text()))
        print("\n".join(bad) or f"ok: {a.out}")
        sys.exit(1 if bad else 0)
    assert bool(a.paths) != bool(a.remake), "give --paths or --remake"
    inputs = remake(a.remake) if a.remake else []
    doc = rollup(a.remake or a.paths, inputs=inputs)
    bad = check(doc)
    assert not bad, bad
    a.out.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False) + "\n")
    c = doc["coverage"]
    print(f"{a.out}: {c['overflows']} overflows, {c['links']} links, {c['spots_with_overflows']} of {c['spots']} spots, "
          f"{c['groups']} groups, {a.out.stat().st_size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
