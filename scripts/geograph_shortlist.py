"""Photo candidates for each spot from Geograph's free bulk dumps, without the API (guides/photo-candidates/README.md).

    uv run python scripts/geograph_shortlist.py BASE.tsv.gz GEO.tsv.gz SPOTS.json OUT.tsv

BASE and GEO are gridimage_base.tsv.gz and gridimage_geo.tsv.gz from https://data.geograph.org.uk/dumps/ (about 250
and 115 MB; download each once, into a folder of their own). SPOTS is a site's data/spots.json. Keeps accepted photos
whose subject is within 300 m of a river spot's pin or 600 m of a lake spot's (100 m more for a six-figure grid
reference), with the water or the spot's name in the title, and writes up to 12 a spot, best first. A shortlist only:
each photo still has to be looked at, and its place checked, before a guide uses it.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import re
import sys
from collections import defaultdict

from pyproj import Transformer

STOP = {"river", "lake", "water", "the", "at", "of", "and", "on", "near", "beach", "bridge", "park", "loch", "s", "n",
        "basin", "lido", "meadow", "meadows", "green"}
WATERWORDS = re.compile(r"\b(river|lake|water|beck|falls?|force|foss|tarn|pond|pool|weir|shore|beach|bay|ford|stream|"
                        r"reservoir|loch|lido|swim|bathing|riverside|lakeside|bank|backwater|mere)\b", re.I)
PRECISION_M = {"10": 1, "8": 10, "6": 100}   # Geograph's grid reference length, as metres


def rows(path: str):
    with gzip.open(path, "rb") as fh:
        text = io.TextIOWrapper(fh, encoding="latin-1")   # the dumps' tables are latin1
        cols = text.readline().rstrip("\n").split("\t")
        for line in text:
            yield dict(zip(cols, line.rstrip("\n").split("\t")))


def main(base: str, geo: str, spots_path: str, out: str) -> None:
    spots = {s["id"]: s for s in json.load(open(spots_path))["spots"]}
    to_grid = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    pins = {sid: to_grid.transform(s["lon"], s["lat"]) for sid, s in spots.items()}
    cells = defaultdict(list)
    for sid, (e, n) in pins.items():
        cells[(int(e // 1000), int(n // 1000))].append(sid)
    names = {}
    for sid, s in spots.items():
        words = set()
        for part in (s["name"], (s.get("location") or {}).get("watercourse") or "", s.get("river") or ""):
            words |= {t.lower().strip("'") for t in re.findall(r"[A-Za-z']{3,}", part) if t.lower() not in STOP}
        names[sid] = words
    near = {}
    for r in rows(base):
        if r.get("moderation_status") in ("geograph", "accepted"):
            near[r["gridimage_id"]] = r
    found = defaultdict(list)
    for g in rows(geo):
        r = near.get(g["gridimage_id"])
        if not r or g["natgrlen"] not in PRECISION_M or not g["nateastings"]:
            continue
        e, n = int(g["nateastings"]), int(g["natnorthings"])
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for sid in cells.get((e // 1000 + di, n // 1000 + dj), ()):
                    pe, pn = pins[sid]
                    d = math.hypot(e - pe, n - pn)
                    lim = (600 if spots[sid].get("kind") == "lake" else 300) + (100 if g["natgrlen"] == "6" else 0)
                    if d > lim:
                        continue
                    title = r["title"]
                    hits = sum(1 for w in names[sid] if re.search(r"\b" + re.escape(w), title, re.I))
                    ww = bool(WATERWORDS.search(title))
                    if not (hits or ww):
                        continue
                    cam = ""
                    if g["viewpoint_grlen"] not in ("0", "") and g["viewpoint_eastings"] not in ("0", ""):
                        cam = f"{math.hypot(int(g['viewpoint_eastings']) - pe, int(g['viewpoint_northings']) - pn):.0f}"
                    year = r["imagetaken"][:4]
                    score = hits * 3 + ww * 2 - d / 150 + ((int(year) - 2000) / 10 if year.isdigit() and year != "0000" else 0)
                    found[sid].append((score, r, g, d, cam))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["spot_id", "rank", "geograph_id", "page", "title", "photographer", "taken", "subject_m_from_pin",
                    "subject_precision_m", "camera_m_from_pin", "view_direction_deg", "flags"])
        for sid in spots:
            for i, (_, r, g, d, cam) in enumerate(sorted(found.get(sid, []), key=lambda x: -x[0])[:12], 1):
                flags = [f for f, on in (("flood in title", re.search(r"\bflood", r["title"], re.I)),
                                         ("before 2010", r["imagetaken"][:4].isdigit() and int(r["imagetaken"][:4]) < 2010),
                                         ("no camera position", not cam)) if on]
                w.writerow([sid, i, r["gridimage_id"], f"https://www.geograph.org.uk/photo/{r['gridimage_id']}", r["title"],
                            r["realname"], r["imagetaken"], f"{d:.0f}", PRECISION_M[g["natgrlen"]], cam,
                            "" if g["view_direction"] in ("-1", "") else g["view_direction"], "; ".join(flags)])


if __name__ == "__main__":
    main(*sys.argv[1:5])
