"""How many listed lake spots have a confirmed or plausible Bloomin' Algae record within 1 km
(docs/NEXT-RESEARCH-SHORTLIST-2026-11.md). Counts only; the CSV has no stated licence and is not kept.

    python -I scripts/next_research/ba_cover.py <BA_records.csv> <a copy of the site's spots-lite.json>"""

import collections
import csv
import json
import math
import sys

KM = 1.0


def km(a: float, b: float, c: float, d: float) -> float:
    p = math.pi / 180
    return 6371 * math.hypot((d - b) * p * math.cos((a + c) / 2 * p), (c - a) * p)


def main(records: str, spots_file: str) -> None:
    rows = list(csv.DictReader(open(records, encoding="utf-8", errors="replace")))
    spots = [s for s in json.load(open(spots_file))["spots"] if s["kind"] == "lake"]
    status = collections.Counter(r["verification_substatus_text"] for r in rows)
    ok = [r for r in rows if r["verification_substatus_text"] in ("confirmed bloom", "plausible")]
    hit = collections.defaultdict(list)
    for r in ok:
        try:
            la, lo = float(r["lat"]), float(r["lon"])
        except ValueError:
            continue
        for s in spots:
            if abs(la - s["lat"]) < 0.03 and km(la, lo, s["lat"], s["lon"]) <= KM:
                hit[s["name"]].append(r["sample_date"][:10])
    checked = {s["name"] for s in spots if s.get("algae")}
    print("records", len(rows), dict(status))
    print("lake spots", len(spots), "| with a confirmed or plausible record within 1 km", len(hit),
          "| records", sum(len(v) for v in hit.values()))
    print("by year", sorted(collections.Counter(d[:4] for v in hit.values() for d in v).items()))
    print("of those spots, with no EA algae check on the page", len([n for n in hit if n not in checked]),
          "| lake spots with an EA check", len(checked))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
