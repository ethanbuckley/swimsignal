"""The postcodes the search and "Plan a swim" understand: data/raw/postcodes.json, from Ordnance
Survey's OS Open Names. The build copies it to site/data/postcodes.json, which the page fetches the
first time something shaped like a postcode is typed, so a postcode never leaves the device.

    uv run python scripts/make_postcodes.py                      # downloads OS Open Names (103 MB)
    uv run python scripts/make_postcodes.py opname_csv_gb.zip    # or reads a copy already downloaded

OS Open Names holds every postcode in Great Britain, about 1.7 million, far too many for a page to
fetch. Kept instead: each district ("LS29", the half before the space) and each sector ("LS29 9",
the district and the next digit), at the mean position of its postcodes, to two decimal places (about
a kilometre). A whole postcode is read as its sector. That is close enough for "within 20 miles" and
for showing the right part of the map, and it is not a house.

Great Britain only: OS Open Names has no Northern Ireland (BT) postcodes.

OS Open Names is OS OpenData under the Open Government Licence v3.0; the file carries the credit.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

from pyproj import Transformer

from dipcast import config

OUT = config.RAW / "postcodes.json"
CREDIT = ("Contains OS data © Crown copyright and database right 2026. Contains Royal Mail data © Royal Mail copyright and "
          "database right 2026. Contains National Statistics data © Crown copyright and database right 2026")
POSTCODE = re.compile(r"^([A-Z]{1,2}[0-9][0-9A-Z]?) ?([0-9])[A-Z]{2}$")


def postcodes(zf: zipfile.ZipFile):
    """Every postcode in the archive: (district, sector digit, easting, northing)."""
    header = next(n for n in zf.namelist() if n.lower().endswith("os_open_names_header.csv"))
    cols = zf.read(header).decode("utf-8-sig").strip().split(",")
    name, kind, x, y = (cols.index(c) for c in ("NAME1", "LOCAL_TYPE", "GEOMETRY_X", "GEOMETRY_Y"))
    for member in zf.namelist():
        if not (member.startswith("Data/") and member.endswith(".csv")):
            continue
        for r in csv.reader(io.TextIOWrapper(zf.open(member), encoding="utf-8")):
            if len(r) == len(cols) and r[kind] == "Postcode":
                m = POSTCODE.match(r[name].strip().upper())
                if m:
                    yield m[1], m[2], float(r[x]), float(r[y])


def centres(found) -> tuple[dict, dict, int]:
    """District and sector centres as {code: [lat, lon]}, and how many postcodes went in."""
    sums: dict[str, list[float]] = {}
    n = 0
    for district, digit, x, y in found:
        n += 1
        for code in (district, f"{district} {digit}"):
            s = sums.setdefault(code, [0.0, 0.0, 0])
            s[0] += x
            s[1] += y
            s[2] += 1
    to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    districts, sectors = {}, {}
    for code in sorted(sums):
        sx, sy, k = sums[code]
        lon, lat = to_wgs84.transform(sx / k, sy / k)
        (sectors if " " in code else districts)[code] = [round(lat, 2), round(lon, 2)]
    return districts, sectors, n


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else config.CACHE / "os_open_names" / "opname_csv_gb.zip"
    if not src.exists():
        from make_places import download
        print(f"Downloading OS Open Names to {src}")
        download(src)
    with zipfile.ZipFile(src) as zf:
        districts, sectors, n = centres(postcodes(zf))
    doc = {"source": "Ordnance Survey, OS Open Names (https://www.ordnancesurvey.co.uk/products/os-open-names)",
           "licence": "Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)",
           "credit": CREDIT,
           "fields": ["lat", "lon"],
           "postcodes": n,
           "districts": districts,
           "sectors": sectors}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{n:,} postcodes, {len(districts):,} districts, {len(sectors):,} sectors, {OUT.stat().st_size / 1e3:,.0f} kB: {OUT}")


if __name__ == "__main__":
    main()
