"""Wessex Water's own river E. coli samples at three listed spots, for the site's research pages
(docs/WESSEX-RIVER-SAMPLES-CONTRACT-v1.md). From the cached ArcGIS rows, read-only:

    DIPCAST_ROOT=<scratch root> uv run python scripts/export_wessex_river_samples.py export [--out PATH]
    uv run python scripts/export_wessex_river_samples.py check [PATH]

`export` needs, under DIPCAST_ROOT, the river network and overflow table (data/processed/river_network.pkl,
overflows.parquet) and the Wessex cache (data/cache/wessex_wq/, or DIPCAST_CACHE/wessex_wq/). It places each spot and
its nearest sampling point on the river network and keeps the point only if the checks below hold. It writes nothing
else. `check` needs only the file.

The rows are "Wessex Water Environmental Water Quality 2019-2025" (ArcGIS item 4659ab28caa640c58e725b41ecbba79f),
fetched once on 25 Oct 2026 by scripts/soil_moisture_eval/rivers.py. They are the company's own samples, analysed at
an accredited laboratory (the item's description), not the Environment Agency's statutory bathing water samples.
CC BY 4.0: the credit and the changes made go with the data and on any page that shows it.

What SwimSignal changed: kept E. coli at three points only; joined positions under JOIN_M apart into one point (the
layer moves a point's last decimal between years); read "NA" in the operator field as no qualifier; named each point
after the spot it is linked from. The values, dates and qualifiers are as published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "wessex_river_samples.v1.json"
SCHEMA, VERSION = "swimsignal.wessex-river-samples", "1.0.0"
LINE = 900          # E. coli per 100 ml: the inland "sufficient" standard's line, as in ecoli_evidence.v1.json
JOIN_M = 10.0       # positions this close are one sampling point
NEAR_M = 2_500.0    # a point further than this in a straight line is not looked at
ALONG_MAX_M = 3_000.0   # nor one further than this along the river
ITEM = "4659ab28caa640c58e725b41ecbba79f"
LAYER = ("https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/"
         "Wessex_Water_Environmental_Water_Quality_view/FeatureServer/0")
# The licence as the item's licenseInfo gave it on the day of export, read by hand from
# https://www.arcgis.com/sharing/rest/content/items/<ITEM>?f=json, with the layer's own count and edit date.
LICENCE_CHECK = {
    "checked": "2026-11-13T15:18Z",
    "wording": "Wessex Water Environmental Water Quality © 2026 by Wessex Water is licensed under CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    "item_modified": "2026-06-05",
    "layer_data_last_edit": "2026-06-05",
    "layer_ecoli_count": 4123,
    "requests": 3,
}
ATTRIBUTION = ("River E. coli samples: Wessex Water Environmental Water Quality © 2026 by Wessex Water, licensed under "
               "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Selected and arranged by SwimSignal.")
CHANGES = [
    "Only E. coli, and only the sampling points linked from three SwimSignal spots, are kept.",
    f"Positions under {JOIN_M:g} m apart are joined into one sampling point.",
    "An operator of \"NA\" is read as no qualifier; \"<\" and \">\" are kept as the lab's limits.",
    "Each point is named after the SwimSignal spot it is linked from; the layer has no site name.",
]
CLAIM = {
    "public_wording": "Wessex Water's own river samples, analysed at the company's accredited laboratory, and the E. coli "
                      "counted in each. They are not Environment Agency bathing water samples. A sample is the water at "
                      "that point at the time it was taken: not today's water.",
    "not_claimed": ["the water now", "the water at the spot itself, where the point is not at it", "a forecast",
                    "a bathing water rating", "that the water is safe to swim", "a check of SwimSignal's forecast",
                    "which source the E. coli came from"],
}
# The listed spots with no Environment Agency samples of their own, or none before 2024 (Farleigh Hungerford became a
# bathing water in 2024: its EA samples are on samples.html), on the river spots.csv gives them.
SPOTS = {   # downstream first
    "avon-warleigh-weir": "River Avon",
    "bw-ukk2301-36051": "River Frome",
    "frome-tellisford-weir": "River Frome",
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def points(rows: list[dict]) -> list[dict]:
    """Sampling points: positions joined while under JOIN_M from the point's first position."""
    out: list[dict] = []
    for pos in sorted({(r["Latitude"], r["Longitude"]) for r in rows}):
        for p in out:
            if metres(*p["positions"][0], *pos) < JOIN_M:
                p["positions"].append(pos)
                break
        else:
            out.append({"positions": [pos]})
    for p in out:
        p["lat"] = round(statistics.fmean(a for a, _ in p["positions"]), 6)
        p["lon"] = round(statistics.fmean(b for _, b in p["positions"]), 6)
    return out


def sample(r: dict) -> dict:
    """One row as the page and the file give it. `over` is null where a limit leaves it unknown."""
    op = (r["Operator"] or "").strip()
    q = op if op in ("<", ">") else None
    v = float(r["Result"])
    v = int(v) if v == int(v) else v
    over = (v >= LINE or None) if q == ">" else (False if v <= LINE else None) if q == "<" else v > LINE
    t = str(r["SampleDate"])[:16]
    datetime.fromisoformat(t)
    return {"t": t, "ecoli": v, "q": q, "over": over, "id": int(r["OBJECTID"])}


def year_summary(s: list[dict]) -> list[dict]:
    out = []
    for y in sorted({x["t"][:4] for x in s}):
        z = [x for x in s if x["t"].startswith(y)]
        top = max(z, key=lambda x: (x["ecoli"], x["q"] == ">"))
        out.append({"year": int(y), "samples": len(z), "over_900": sum(x["over"] is True for x in z),
                    "first": z[0]["t"][:10], "last": z[-1]["t"][:10],
                    "highest": top["ecoli"], "highest_q": top["q"]})
    return out


def place(spots_csv: Path, rows: list[dict]) -> list[dict]:
    """For each spot, its nearest sampling point, placed on the river network beside the spot: the same named river,
    under ALONG_MAX_M apart along it, the same monitored overflows upstream of both and none between. Each check is
    kept in the file; a spot whose point fails one is left out, with why."""
    import pandas as pd

    from dipcast.model.transport import locate_pin, river_velocity, upstream_overflows
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows

    spots = pd.read_csv(spots_csv).set_index("id")
    net = RiverNetwork.load()
    ov = load_overflows(net)
    pts = points(rows)
    out = []
    for sid, river in SPOTS.items():
        s = spots.loc[sid]
        near = min(pts, key=lambda p: metres(s["lat"], s["lon"], p["lat"], p["lon"]))
        straight = metres(s["lat"], s["lon"], near["lat"], near["lon"])
        pin_s = locate_pin(net, float(s["lon"]), float(s["lat"]), river_hint=river, name=s["name"])
        pin_p = locate_pin(net, near["lon"], near["lat"], river_hint=river)
        up_s = upstream_overflows(net, pin_s, ov, velocity_ms=river_velocity(None)).set_index("site_id")
        up_p = upstream_overflows(net, pin_p, ov, velocity_ms=river_velocity(None)).set_index("site_id")
        common = up_s.index.intersection(up_p.index)
        # The spot's distance to each shared overflow less the point's: the point's distance along the river from
        # the spot, positive when it is downstream of the spot.
        gaps = (up_p.loc[common, "distance_m"] - up_s.loc[common, "distance_m"]) if len(common) else pd.Series(dtype=float)
        along = float(gaps.median()) if len(gaps) else None
        between = sorted(set(up_s.index) ^ set(up_p.index))
        checks = {
            "same_river": pin_s.watercourse == pin_p.watercourse == river,
            "within_straight": straight <= NEAR_M,
            "along_known": along is not None and float(gaps.max() - gaps.min()) < 1.0,
            "within_along": along is not None and abs(along) <= ALONG_MAX_M,
            "no_overflow_between": not between,
        }
        rec = {
            "spot_id": sid, "spot_name": str(s["name"]), "river": river,
            "point": {"lat": near["lat"], "lon": near["lon"], "positions": [list(p) for p in near["positions"]],
                      "snap_m": round(pin_p.snap.dist_m, 1) if pin_p.snap else None,
                      "placement": pin_p.placement, "side_channel": bool(pin_p.adopted_main_channel)},
            "straight_m": round(straight),
            "along_m": None if along is None else round(along),
            "direction": None if along is None else ("downstream" if along > 0 else "upstream"),
            "overflows_upstream": {"spot": len(up_s), "point": len(up_p), "between": between},
            "checks": checks,
            "linked": all(checks.values()),
        }
        if rec["linked"]:
            mine = [r for r in rows if (r["Latitude"], r["Longitude"]) in set(near["positions"])]
            sam = sorted((sample(r) for r in mine), key=lambda x: (x["t"], x["id"]))
            seen = {}
            for x in sam:
                seen[x["t"]] = seen.get(x["t"], 0) + 1
            for x in sam:
                x["same_time"] = seen[x["t"]] > 1
            rec["samples"] = sam
            rec["summary"] = {"samples": len(sam), "over_900": sum(x["over"] is True for x in sam),
                              "over_unknown": sum(x["over"] is None for x in sam),
                              "below_limit": sum(x["q"] == "<" for x in sam),
                              "above_limit": sum(x["q"] == ">" for x in sam),
                              "same_time_pairs": sum(1 for v in seen.values() if v > 1),
                              "first": sam[0]["t"][:10], "last": sam[-1]["t"][:10], "years": year_summary(sam)}
        out.append(rec)
    return out


def build(cache: Path, spots_csv: Path) -> dict:
    import pandas as pd
    from dipcast import config

    pq, prov = cache / "ecoli.parquet", cache / "provenance.json"
    rows = pd.read_parquet(pq).to_dict("records")
    provenance = json.loads(prov.read_text())
    sites = place(spots_csv, rows)
    linked = [x for x in sites if x["linked"]]
    return {
        "schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "line": LINE,
        "units": "E. coli per 100 ml, as the layer's Units field gives them (\"E. Coli/ 100 mL\")",
        "time_note": "Sample times are as the layer gives them, with no time zone; read as UK local time.",
        "claim": CLAIM,
        "who": "Wessex Water: the company's own river samples, not Environment Agency statutory samples",
        "attribution": ATTRIBUTION,
        "changes": CHANGES,
        "source": {"title": "Wessex Water Environmental Water Quality 2019-2025", "item": ITEM,
                   "item_url": f"https://www.arcgis.com/home/item.html?id={ITEM}", "layer": LAYER,
                   "query": provenance.get("where"), "fetched": provenance.get("fetched"),
                   "rows": provenance.get("rows"), "licence_check": LICENCE_CHECK,
                   "files_sha256": {"ecoli.parquet": sha256(pq), "provenance.json": sha256(prov)},
                   "network_sha256": {"river_network.pkl": sha256(config.PROCESSED / "river_network.pkl"),
                                      "overflows.parquet": sha256(config.state_read("overflows.parquet"))},
                   "spots_csv_sha256": sha256(spots_csv),
                   "code_sha256": {"scripts/export_wessex_river_samples.py": sha256(Path(__file__))}},
        "placement_rule": {"join_m": JOIN_M, "near_m": NEAR_M, "along_max_m": ALONG_MAX_M,
                           "how": "Spot and point placed by transport.locate_pin with the spot's river; distance along "
                                  "the river from the shared upstream overflows' distances; an overflow upstream of one "
                                  "and not the other is one between them."},
        "spots": [x["spot_id"] for x in linked],
        "sites": sites,
        "coverage": {"sites": len(linked), "samples": sum(x["summary"]["samples"] for x in linked)},
    }


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("line", "units", "claim", "who", "attribution", "changes", "source", "sites", "spots", "coverage"):
        if k not in doc:
            err.append(f"missing {k}")
    if "not today's water" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not today's water")
    if "not Environment Agency" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say these are not Environment Agency samples")
    if "CC BY 4.0" not in doc.get("attribution", ""):
        err.append("the attribution must name CC BY 4.0")
    linked = [x for x in doc.get("sites", []) if x.get("linked")]
    if [x["spot_id"] for x in linked] != doc.get("spots"):
        err.append("spots do not match the linked sites")
    for x in doc.get("sites", []):
        if x.get("linked") != all((x.get("checks") or {False: False}).values()):
            err.append(f"{x.get('spot_id')}: linked does not follow its checks")
    for x in linked:
        s = x.get("samples", [])
        if [(a["t"], a["id"]) for a in s] != sorted((a["t"], a["id"]) for a in s):
            err.append(f"{x['spot_id']}: samples not in time order")
        for a in s:
            if a["q"] not in (None, "<", ">") or not isinstance(a["ecoli"], (int, float)) or a["ecoli"] < 0:
                err.append(f"{x['spot_id']} {a['t']}: a value or qualifier out of range")
            if a["q"] is None and a["over"] != (a["ecoli"] > doc.get("line", LINE)):
                err.append(f"{x['spot_id']} {a['t']}: over does not follow the value")
        sm = x.get("summary", {})
        if sm.get("samples") != len(s) or sum(y["samples"] for y in sm.get("years", [])) != len(s):
            err.append(f"{x['spot_id']}: counts do not add up")
        if sm.get("over_900") != sum(a["over"] is True for a in s):
            err.append(f"{x['spot_id']}: over-900 count does not match")
    if doc.get("coverage", {}).get("samples") != sum(len(x.get("samples", [])) for x in linked):
        err.append("coverage does not match the samples")
    return err


def dumps(doc: dict) -> str:
    """Indented, with each sample on one line, so a change to a sample is one line of a diff."""
    marks, d = {}, json.loads(json.dumps(doc))
    for x in d["sites"]:
        if "samples" in x:
            k = f"@@samples-{x['spot_id']}@@"
            marks[f'"{k}"'] = "[\n" + ",\n".join("   " + json.dumps(a, ensure_ascii=False) for a in x["samples"]) + "\n  ]"
            x["samples"] = k
    text = json.dumps(d, ensure_ascii=False, indent=1)
    for k, v in marks.items():
        text = text.replace(k, v)
    return text + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--out", type=Path, default=OUT)
    e.add_argument("--spots", type=Path, default=ROOT / "spots.csv")
    c = sub.add_parser("check")
    c.add_argument("path", type=Path, nargs="?", default=OUT)
    a = ap.parse_args()
    if a.cmd == "export":
        if "DIPCAST_ROOT" not in os.environ:
            raise SystemExit("set DIPCAST_ROOT to a scratch root that links the network, overflows and Wessex cache")
        from dipcast import config
        doc = build(config.CACHE / "wessex_wq", a.spots)
        if err := check(doc):
            raise SystemExit("\n".join(err))
        a.out.write_text(dumps(doc))
        for x in doc["sites"]:
            print(x["spot_id"], x["linked"], x["straight_m"], "m straight,", x["along_m"], "m along,", x["direction"],
                  x.get("summary", {}).get("samples"), "samples")
    else:
        err = check(json.loads(a.path.read_text()))
        print("\n".join(err) or "ok")
        sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
