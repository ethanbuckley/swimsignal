"""Measured lake water temperatures, May to September 2000-2026, for the site's research pages
(docs/LAKE-TEMPERATURE-OBS-CONTRACT-v1.md). Offline, from the lake temperature test's cached EA readings:

    DIPCAST_ROOT=<checkout with data/raw/wfd_lakes_cycle3.geojson> \\
        uv run python scripts/export_lake_temperature_obs.py export [--work DIR] [--out PATH]
    uv run python scripts/export_lake_temperature_obs.py check [PATH]

The readings are the Environment Agency Water Quality Archive's determinand 0076 (water temperature) at sampling points
inside or on a WFD lake, as the lake temperature test (#419, scripts/lake_temperature_eval) matched them, one value a
point a day. They are measurements at a sampling point on the dates the EA visited, not live readings and not readings
at a swim entry. Each listed lake spot is tied to the WFD lake its point lies in (or within 150 m of).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "water-temperature" / "lake-test" / "work"
OUT = ROOT / "data" / "research" / "lake_temperature_obs.v1.json"
SCHEMA, VERSION = "swimsignal.lake-temperature-obs", "1.0.0"
MONTHS = (5, 6, 7, 8, 9)
NEAR_M = 150.0
RECENT = 12
CLAIM = {
    "public_wording": "Water temperatures the Environment Agency measured in this lake, at its sampling points, on the "
                      "days it visited between May and September. A record of past measurements, not today's "
                      "temperature, and not measured where you get in: shallow edges can be warmer or colder.",
    "not_claimed": ["the temperature now", "the temperature at the swim spot", "a forecast", "that water is safe to swim"],
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def spot_lakes(spots: pd.DataFrame, geojson: Path) -> dict[str, tuple[str, float]]:
    """spot id -> (WFD water body id, metres outside it; 0 when inside), for spots inside or within NEAR_M of a lake."""
    from pyproj import Transformer
    from shapely.geometry import Point, shape
    from shapely.ops import transform
    to_bng = Transformer.from_crs(4326, 27700, always_xy=True).transform
    lakes = [(f["properties"]["WB_ID"], transform(to_bng, shape(f["geometry"])))
             for f in json.loads(geojson.read_text())["features"]]
    out = {}
    for s in spots.itertuples():
        pt = Point(to_bng(s.lon, s.lat))
        best = min(((pt.distance(g), wb) for wb, g in lakes), default=(np.inf, None))
        if best[0] <= NEAR_M:
            out[s.id] = (best[1], round(float(best[0]), 1))
    return out


def build(work: Path) -> dict:
    from pyproj import Transformer

    from dipcast import config
    geo = config.RAW / "wfd_lakes_cycle3.geojson"
    inputs = [work / "features.parquet", work / "points.parquet", ROOT / "spots.csv", geo]
    before = {p.name: sha256(p) for p in inputs}
    f = pd.read_parquet(work / "features.parquet", columns=["point", "wb_id", "lake_name", "label", "date", "temp",
                                                             "lake_area_km2", "depth_m", "reservoir", "how"])
    no_lake = int(f["wb_id"].isna().sum())   # matched to water with no WFD lake id: not attributable to one lake
    f = f[f["wb_id"].notna()].copy()
    f["date"] = pd.to_datetime(f["date"]).dt.strftime("%Y-%m-%d")
    pts = pd.read_parquet(work / "points.parquet").set_index("point")
    spots = pd.read_csv(ROOT / "spots.csv")
    links = spot_lakes(spots, geo)
    to_bng = Transformer.from_crs(4326, 27700, always_xy=True).transform
    lakes = []
    for wb, g in f.sort_values(["date", "point"]).groupby("wb_id"):
        p_ids = sorted(g["point"].unique())
        points = [{"point": pid, "label": g.loc[g["point"] == pid, "label"].iloc[0],
                   "lat": round(float(pts.loc[pid, "lat"]), 5), "lon": round(float(pts.loc[pid, "lon"]), 5),
                   "readings": int((g["point"] == pid).sum()), "last": g.loc[g["point"] == pid, "date"].max()}
                  for pid in p_ids]
        month = pd.to_datetime(g["date"]).dt.month
        monthly = []
        for mth in MONTHS:
            t = g.loc[month == mth, "temp"]
            monthly.append({"month": mth, "n": int(len(t)), "median": round(float(t.median()), 1) if len(t) else None,
                            "p25": round(float(t.quantile(0.25)), 1) if len(t) >= 4 else None,
                            "p75": round(float(t.quantile(0.75)), 1) if len(t) >= 4 else None})
        idx = {pid: i for i, pid in enumerate(p_ids)}
        spot_rows = []
        for sid, (lwb, outside) in links.items():
            if lwb != wb:
                continue
            s = spots.set_index("id").loc[sid]
            sx, sy = to_bng(s.lon, s.lat)
            dist = min(np.hypot(*(np.array(to_bng(pts.loc[pid, "lon"], pts.loc[pid, "lat"])) - (sx, sy))) for pid in p_ids)
            spot_rows.append({"spot_id": sid, "name": s["name"], "outside_lake_m": outside,
                              "nearest_point_m": int(round(dist))})
        lakes.append({
            "wb_id": wb, "name": g["lake_name"].iloc[0], "area_km2": round(float(g["lake_area_km2"].iloc[0]), 3),
            "depth_m": None if pd.isna(g["depth_m"].iloc[0]) else float(g["depth_m"].iloc[0]),
            "reservoir": bool(g["reservoir"].iloc[0]), "points": points, "spots": sorted(spot_rows, key=lambda x: x["spot_id"]),
            "summary": {"readings": int(len(g)), "first": g["date"].min(), "last": g["date"].max(),
                        "years": int(pd.to_datetime(g["date"]).dt.year.nunique())},
            "monthly": monthly,
            "readings": {"date": g["date"].tolist(), "temp": [round(float(x), 1) for x in g["temp"]],
                         "point": [idx[p] for p in g["point"]]},
        })
    after = {p.name: sha256(p) for p in inputs}
    if after != before:
        raise SystemExit("an input changed during the export")
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "period": {"from": f["date"].min(), "to": f["date"].max(), "months": list(MONTHS)},
            "method": {"source": "EA Water Quality Archive, determinand 0076 (temperature of water), fresh water, "
                                 "fetched May-September only by the lake temperature test (#419)",
                       "matching": "sampling points inside a WFD lake polygon, on the lake's own water, or on an OS "
                                   "lake link (#419's rows); one value per point per day",
                       "spot_link_m": NEAR_M,
                       "code_sha256": {"scripts/export_lake_temperature_obs.py": sha256(ROOT / "scripts" / "export_lake_temperature_obs.py")}},
            "sources": [{"file": k, "sha256": v} for k, v in before.items()],
            "attribution": ["Environment Agency Water Quality Archive, Open Government Licence v3.0",
                            "WFD lake outlines: Environment Agency, Open Government Licence v3.0",
                            "Lake depths: HydroLAKES (Messager et al. 2016), CC BY 4.0"],
            "claim": CLAIM, "lakes": lakes,
            "coverage": {"lakes": len(lakes), "readings": int(len(f)), "readings_without_lake_id": no_lake,
                         "points": int(f["point"].nunique()),
                         "lakes_with_spots": sum(bool(lk["spots"]) for lk in lakes),
                         "spots_linked": sum(len(lk["spots"]) for lk in lakes)}}


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("generated_at", "period", "method", "sources", "attribution", "claim", "lakes", "coverage"):
        if k not in doc:
            err.append(f"missing {k}")
    if "not today's temperature" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not today's temperature")
    for lk in doc.get("lakes", []):
        r = lk["readings"]
        if not (len(r["date"]) == len(r["temp"]) == len(r["point"]) == lk["summary"]["readings"]):
            err.append(f"{lk['wb_id']}: reading columns or count disagree")
        if r["date"] != sorted(r["date"]):
            err.append(f"{lk['wb_id']}: readings not in date order")
        if any(not 0 <= t <= 35 for t in r["temp"]):
            err.append(f"{lk['wb_id']}: a temperature outside 0-35 C")
        if any(int(d[5:7]) not in MONTHS for d in r["date"]):
            err.append(f"{lk['wb_id']}: a reading outside May-September")
        if r["point"] and max(r["point"]) >= len(lk["points"]):
            err.append(f"{lk['wb_id']}: a point index with no point")
        for m in lk["monthly"]:
            if m["p25"] is not None and not m["p25"] <= m["median"] <= m["p75"]:
                err.append(f"{lk['wb_id']}: month {m['month']} quartiles out of order")
    if doc.get("coverage", {}).get("readings") != sum(lk["summary"]["readings"] for lk in doc.get("lakes", [])):
        err.append("coverage count does not match")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.work)
        problems = check(doc)
        if problems:
            raise SystemExit("\n".join(problems[:20]))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(json.dumps(doc["coverage"]))
        print(f"wrote {a.out} ({a.out.stat().st_size:,} bytes)")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
