"""The places "Plan a swim" can start from: data/raw/places.json, from Ordnance Survey's OS Open
Names. The build copies it to site/data/places.json, which the plan page fetches the first time
someone types a starting point, so a town's name never leaves the device.

    uv run python scripts/make_places.py                      # downloads OS Open Names (103 MB)
    uv run python scripts/make_places.py opname_csv_gb.zip    # or reads a copy already downloaded

Kept: every city, town, village, suburban area (Headingley, Didsbury) and "other settlement" in
England and Wales, about 26,000 names. OS files London's districts (Hackney, Hampstead) and many
Lake District places (Nether Wasdale, Loweswater) as other settlements. Hamlets are left out: there
are 11,000 of them and few people plan a trip from one. Wales is in because the Wye and the Severn
run out of it to spots in England. A Welsh place with both names gets both, each its own entry.

Each place is [name, latitude, longitude], to two decimal places (about a kilometre), which is close
enough for "within 20 miles". A name used by more than one place keeps it bare for the biggest, if
it is bigger than the rest (Oxford the city), and the others get their district or county after a
comma ("Oxford, City of Stoke-on-Trent", "Newport, Isle of Wight"); two places left with the same name
and area keep the bigger. The list runs from cities to villages, so the first matches the page
offers are the likelier ones.

OS Open Names is OS OpenData under the Open Government Licence v3.0; the file carries the credit.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import httpx
from pyproj import Transformer

from dipcast import config

OUT = config.RAW / "places.json"
URL = "https://api.os.uk/downloads/v1/products/OpenNames/downloads?area=GB&format=CSV&redirect"
KINDS = {"City": 0, "Town": 1, "Suburban Area": 2, "Other Settlement": 2, "Village": 3}   # the order the list runs in
COUNTRIES = {"England", "Wales"}
CREDIT = "Contains OS data © Crown copyright and database right 2026"


def download(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", URL, follow_redirects=True, timeout=600) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest


def rows(zf: zipfile.ZipFile):
    """Every populated place in the archive, as a dict by the header's column names."""
    header = next(n for n in zf.namelist() if n.lower().endswith("os_open_names_header.csv"))
    cols = zf.read(header).decode("utf-8-sig").strip().split(",")
    for name in zf.namelist():
        if not (name.startswith("Data/") and name.endswith(".csv")):
            continue
        for r in csv.reader(io.TextIOWrapper(zf.open(name), encoding="utf-8")):
            if len(r) == len(cols) and r[6] == "populatedPlace":
                yield dict(zip(cols, r))


def places(zf: zipfile.ZipFile) -> list[list]:
    to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    found = []
    for d in rows(zf):
        if d["COUNTRY"] not in COUNTRIES or d["LOCAL_TYPE"] not in KINDS:
            continue
        lon, lat = to_wgs84.transform(float(d["GEOMETRY_X"]), float(d["GEOMETRY_Y"]))
        # Welsh areas come in both languages ("Sir Benfro - Pembrokeshire"): the English, as the page is.
        areas = [a.split(" - ")[-1] for a in (d["DISTRICT_BOROUGH"], d["COUNTY_UNITARY"], d["REGION"]) if a]
        for name in {d["NAME1"], d["NAME2"]} - {""}:
            area = next((a for a in areas if a != name), "")   # never "Bradford, Bradford"
            found.append((KINDS[d["LOCAL_TYPE"]], name, area, round(lat, 2), round(lon, 2)))
    found.sort(key=lambda p: (p[0], p[1]))
    ranks: dict[str, list[int]] = {}
    for kind, name, *_ in found:
        ranks.setdefault(name, []).append(kind)
    out, seen = [], set()
    for kind, name, area, lat, lon in found:
        r = ranks[name]   # every place of this name, biggest first
        bare = len(r) == 1 or (kind == r[0] and r[0] < r[1] and name not in seen)
        shown = name if bare or not area else f"{name}, {area}"
        if shown in seen:   # the same name and area twice: the bigger place came first
            continue
        seen.add(shown)
        out.append([shown, lat, lon])
    return out


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else config.CACHE / "os_open_names" / "opname_csv_gb.zip"
    if not src.exists():
        print(f"Downloading OS Open Names to {src}")
        download(src)
    with zipfile.ZipFile(src) as zf:
        found = places(zf)
    doc = {"source": "Ordnance Survey, OS Open Names (https://www.ordnancesurvey.co.uk/products/os-open-names)",
           "licence": "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)",
           "credit": CREDIT,
           "fields": ["name", "lat", "lon"],
           "places": found}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{len(found):,} places, {OUT.stat().st_size / 1e3:,.0f} kB: {OUT}")


if __name__ == "__main__":
    main()
