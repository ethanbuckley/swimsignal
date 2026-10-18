"""Reasons a water body does not reach good status, and the water body each listed spot is in:
data/raw/rnags.json, from the Environment Agency's Catchment Data Explorer. The build copies a spot's
water body into spots.json (build_site.attach_water_body), and the spot's page says, among what the
level leaves out, where the Environment Agency lists agriculture and rural land management as a
confirmed or probable reason (evidence.js, evidenceRunoff).

    uv run python scripts/make_rnags.py                         # downloads the CSV (16 MB) and ten GeoJSONs (85 MB)
    uv run python scripts/make_rnags.py rnags.csv geojson_dir/  # or reads them already downloaded

Off CI, by hand: when the Environment Agency updates the file (the review of 16 Oct 2026 says
quarterly; the publisher's page gives no date), and when a spot is added to spots.csv or
spots-osm.csv (the build warns of a spot the file does not place). The build reads only the JSON.

Source: "Reasons for not achieving good (RNAG) and reasons for deterioration (RFD)" for England,
https://environment.data.gov.uk/catchment-planning/England/rnags, one CSV row per reason: the water
body, the classification element that is below good, the sector responsible ("Category", such as
"Agriculture and rural land management"), the significant water management issue ("National Swmi
Header", such as "Pollution from rural areas") and how certain each is. The water bodies' river lines
and catchments come from the same Explorer, one GeoJSON per river basin district. Licence, as the
Explorer's footer states it (read 18 Oct 2026): "All content is available under the Open Government
Licence v3.0, except where otherwise stated". The Defra Data Services Platform's terms say the same of
the platform: "Content and data on the site is published under the Open Government Licence (OGL),
unless we indicate otherwise."

`water_bodies`: {id: {name, type, pressures: [{sector, issue, certainty, sources, activities, elements}]}}.
Kept: reasons for not achieving good status (Reason Type "RNAG"; the reasons for deterioration are left
out, as the Explorer's own tables leave them out) whose sector is "Confirmed" or "Probable" ("Category
Certainty"), the two the Explorer counts; "Suspected" and "Not applicable" are dropped. One pressure per
sector and issue: its certainty is the strongest of its rows ("confirmed" over "probable"), and the
sources ("Diffuse source", "Point source"), activities and elements are those of all its kept rows,
sorted. Each water body in the CSV is listed, with an empty list where none of its reasons is kept, so a
water body the file has is told from one it does not (a Welsh one, or an English one at good status with
no reason to give). Words are the Environment Agency's own, as the file spells them.

`spots`: {spot id: {id, by, m} or null}, the water body each listed spot is in:
- a river spot: the water body whose river line, named for the spot's river ("Wye - Bredwardine Br to
  Hampton Bishop" for the River Wye), is nearest, within RIVER_LINE_M ("river line", m its distance);
  failing that, the water body named for the river whose catchment holds the spot ("catchment", m 0),
  as near a river's source, above where its line starts. A spot on a tributary the Explorer does not
  name (Burbage Brook) gets null, not the water body of the river it joins.
- a lake spot: the WFD lake the forecast places it in (transport._locate_lake, steps 1 and 2: within
  150 m of the spot, or named in its name within 1 km; "lake", m its distance).
Checked on 18 Oct 2026, before the build used it: for 68 of the 72 river spots the nearest named line
within 500 m and the named catchment holding the spot gave the same water body. The four others: the
Itchen at Compton Lock, 0 m from the Itchen Navigation's line, in the Itchen's catchment (the line
decides); the Dane at Three Shires Head, 1,076 m above the start of its line, in its catchment; the
Ouse at Barcombe Mills and the Dee at Chester, neither (the Welsh Dee is not in England's file).
Joining through the overflows' annual returns instead (the nearest overflow upstream on the spot's
river, within 5 km) placed 34 of the 72, two of them in the next water body up (the Severn at
Ironbridge and the Wharfe at Appletreewick), and missed Symonds Yat, whose nearest such overflow is
7.7 km upstream.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import Point, shape

from dipcast import config
from dipcast.overflows import _tokens, water_body_words

OUT = config.RAW / "rnags.json"
EXPLORER = "https://environment.data.gov.uk/catchment-planning"
PAGE = f"{EXPLORER}/England/rnags"
URL = f"{EXPLORER}/England/rnags.csv"
DISTRICTS = {2: "Solway Tweed", 3: "Northumbria", 4: "Humber", 5: "Anglian", 6: "Thames", 7: "South East",
             8: "South West", 9: "Severn", 11: "Dee", 12: "North West"}   # the Explorer's river basin district ids
LICENCE = "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)"
CREDIT = "© Environment Agency copyright and/or database right. All rights reserved."
KEEP = {"Confirmed": "confirmed", "Probable": "probable"}   # the Explorer's own tables count these two
RANK = {"confirmed": 0, "probable": 1}
COLUMNS = ["Water Body ID", "Water Body", "Water Body Type", "Reason Type", "Category", "Category Certainty",
           "National Swmi Header", "Swmi", "Activity", "Classification Element"]
RIVER_LINE_M = 500.0
GROUNDWATER = re.compile(r"^GB\d{5}G")   # groundwater bodies' ids: GB40402G700500
SPOT_FILES = [config.ROOT / "spots.csv", config.ROOT / "spots-osm.csv"]


def download(url: str) -> bytes:
    for attempt in range(3):   # the Explorer answered one district's GeoJSON with a 503 on 18 Oct 2026
        r = httpx.get(url, timeout=300, follow_redirects=True)
        if r.status_code < 500 or attempt == 2:
            r.raise_for_status()
            return r.content
        time.sleep(5)
    raise AssertionError("unreachable")


def _words(values) -> list[str]:
    """The distinct values, blanks and "Not applicable" left out, sorted."""
    return sorted({str(v) for v in values if isinstance(v, str) and v.strip() and v != "Not applicable"})


def water_bodies(raw: bytes) -> tuple[dict, int, int]:
    """(water_bodies, rows read, rows kept) from the RNAG CSV."""
    d = pd.read_csv(io.BytesIO(raw), dtype=str)
    missing = [c for c in COLUMNS if c not in d.columns]
    if missing:
        raise SystemExit(f"the file has lost the column(s) {missing}: read it again before changing the script")
    names = d.drop_duplicates("Water Body ID").set_index("Water Body ID")
    keep = d[(d["Reason Type"] == "RNAG") & d["Category Certainty"].isin(KEEP)].copy()
    keep["certainty"] = keep["Category Certainty"].map(KEEP)
    pressures: dict[str, list[dict]] = {}
    for (wb, sector, issue), g in keep.groupby(["Water Body ID", "Category", "National Swmi Header"], dropna=False, sort=True):
        pressures.setdefault(wb, []).append({
            "sector": sector, "issue": issue if isinstance(issue, str) else None,
            "certainty": min(g["certainty"], key=RANK.get),
            "sources": _words(g["Swmi"]), "activities": _words(g["Activity"]), "elements": _words(g["Classification Element"])})
    bodies = {wb: {"name": names.at[wb, "Water Body"], "type": names.at[wb, "Water Body Type"],
                   "pressures": sorted(pressures.get(wb, []), key=lambda p: (RANK[p["certainty"]], p["sector"], p["issue"] or ""))}
              for wb in sorted(names.index)}
    return bodies, len(d), len(keep)


def river_words(name) -> set[str]:
    """The river words of a WFD water body name: the part before " - ", then before any "from", "to" or
    "conf" (overflows.water_body_words): "Wye - Bredwardine Br to Hampton Bishop" -> {"wye"}, "Lugg - conf R
    Arrow to conf R Wye" -> {"lugg"}, "Wharfe from Hundwith Beck to River Washburn" -> {"wharfe"}."""
    return water_body_words(name.split(" - ")[0]) if isinstance(name, str) else set()


def shapes(docs: list[dict]) -> gpd.GeoDataFrame:
    """The surface water bodies' river lines and catchments in British National Grid: id, name, kind
    ("RiverLine" or "Catchment"), geometry. Groundwater bodies' catchments are left out."""
    rows = [{"id": f["properties"]["id"], "name": f["properties"].get("name"),
             "kind": str(f["properties"].get("geometry-type", "")).rsplit("/", 1)[-1], "geometry": shape(f["geometry"])}
            for doc in docs for f in doc["features"]]
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=4326).to_crs(27700)
    return g[g["kind"].isin(["RiverLine", "Catchment"]) & ~g["id"].str.match(GROUNDWATER)].reset_index(drop=True)


def river_spot(geo: gpd.GeoDataFrame, x: float, y: float, river: str) -> dict | None:
    """A river spot's water body: the nearest river line named for its river within RIVER_LINE_M, else the
    catchment named for it that holds the spot; None with neither, or a river with no distinctive word."""
    want = _tokens(river)
    if not want:
        return None
    pt = Point(x, y)
    near = geo.iloc[geo.sindex.query(pt.buffer(RIVER_LINE_M), predicate="intersects")]
    named = lambda g: g[g["name"].map(lambda n: bool(want & river_words(n))).astype(bool)] if len(g) else g
    lines = named(near[near["kind"] == "RiverLine"])
    if len(lines):
        d = lines.geometry.distance(pt)
        return {"id": lines.at[d.idxmin(), "id"], "by": "river line", "m": round(float(d.min()))}
    holds = named(geo.iloc[geo.sindex.query(pt, predicate="within")].query("kind == 'Catchment'"))
    return {"id": holds.iloc[0]["id"], "by": "catchment", "m": 0} if len(holds) == 1 else None


def lake_spot(x: float, y: float, name: str) -> dict | None:
    """A lake spot's water body: the WFD lake the forecast places it in (transport._locate_lake)."""
    from dipcast.model.transport import _lake_polygon_at, _named_lake_polygon
    poly = _lake_polygon_at(x, y)
    if poly is None:
        poly = _named_lake_polygon(x, y, name)
    if poly is None or not isinstance(poly.get("wb_id"), str):
        return None
    return {"id": poly["wb_id"], "by": "lake", "m": round(float(poly.geometry.distance(Point(x, y))))}


def place_spots(geo: gpd.GeoDataFrame, spots: pd.DataFrame) -> dict[str, dict | None]:
    from dipcast.network.rivers import lonlat_to_bng
    out = {}
    for r in spots.itertuples(index=False):
        x, y = lonlat_to_bng(float(r.lon), float(r.lat))
        out[r.id] = lake_spot(x, y, r.name) if r.kind == "lake" else river_spot(geo, x, y, r.river)
    return out


def load_spots() -> pd.DataFrame:
    """The listed spots, as build_site.load_spots reads them: an id an earlier row has is left out."""
    s = pd.concat([pd.read_csv(p) for p in SPOT_FILES if p.exists()], ignore_index=True).fillna("")
    return s.drop_duplicates("id").reset_index(drop=True)


def make(raw: bytes, docs: list[dict], fetched: str, spots: pd.DataFrame | None = None) -> dict:
    bodies, n_rows, n_kept = water_bodies(raw)
    placed = place_spots(shapes(docs), load_spots() if spots is None else spots)
    return {"source": f"Environment Agency, Catchment Data Explorer: reasons for not achieving good status, England ({PAGE}); "
                      f"water body river lines and catchments, by river basin district ({EXPLORER}/RiverBasinDistrict/<id>.geojson)",
            "licence": LICENCE, "credit": CREDIT, "fetched": fetched, "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": n_rows, "rows_kept": n_kept,
            "made": ("Reasons for not achieving good status (Reason Type RNAG) whose sector is Confirmed or Probable, one "
                     "pressure per water body, sector and issue with the strongest certainty of its rows. Spots: a river spot "
                     f"in the water body whose river line, named for its river, is nearest within {RIVER_LINE_M:g} m, else the "
                     "named catchment holding it; a lake spot in the WFD lake the forecast places it in. By scripts/make_rnags.py"),
            "spots": placed, "water_bodies": bodies}


def write(out: dict, path: Path = OUT) -> None:
    """One water body and one spot to a line, so a quarterly update's diff can be read."""
    head = {k: v for k, v in out.items() if k not in ("spots", "water_bodies")}
    j = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    block = lambda d: "{\n" + ",\n".join(f"{j(k)}:{j(v)}" for k, v in d.items()) + "\n}"
    path.write_text("{" + j(head)[1:-1] + ',\n"spots":' + block(out["spots"]) + ',\n"water_bodies":' + block(out["water_bodies"]) + "}\n")


def main() -> None:
    raw = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else download(URL)
    if len(sys.argv) > 2:
        docs = [json.loads(p.read_text()) for p in sorted(Path(sys.argv[2]).glob("*.geojson"))]
    else:
        docs = []
        for i in DISTRICTS:
            docs.append(json.loads(download(f"{EXPLORER}/RiverBasinDistrict/{i}.geojson")))
            time.sleep(1)
    out = make(raw, docs, datetime.now(UTC).date().isoformat())
    write(out)
    json.loads(OUT.read_text())   # the hand-written layout must still be JSON
    wb, sp = out["water_bodies"], out["spots"]
    farm = sum(any((p["sector"], p["issue"]) == ("Agriculture and rural land management", "Pollution from rural areas")
                   for p in b["pressures"]) for b in wb.values())
    by = pd.Series([v["by"] if v else "none" for v in sp.values()]).value_counts().to_dict()
    print(f"{out['rows']:,} rows, {out['rows_kept']:,} kept; {len(wb):,} water bodies, "
          f"{sum(bool(b['pressures']) for b in wb.values()):,} with a confirmed or probable reason, {farm:,} with pollution "
          f"from agriculture and rural land management. {len(sp)} spots: {by}; {OUT.stat().st_size / 1e3:,.0f} kB: {OUT}")


if __name__ == "__main__":
    main()
