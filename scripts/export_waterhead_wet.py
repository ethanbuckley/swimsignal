"""Waterhead bacteria samples, 2025 and 2026, for the site's research pages (docs/WATERHEAD-WET-CONTRACT-v1.md). From
Ambleside Action for a Future's sheet as Tim Boden sent it on 25 Oct 2026, kept outside the repository:

    uv run --group dev python scripts/export_waterhead_wet.py export [--xlsx PATH] [--out PATH]
    uv run python scripts/export_waterhead_wet.py check [PATH]

The counts are the Waterhead E. coli Testing (WET) project's weekly samples at Waterhead, Windermere: E. coli and
intestinal enterococci per 100 ml as the sheet records them. Tim's email of 25 Oct 2026 makes the counts public domain
and lets them be forwarded with credit to Ambleside Action for a Future. The sheet's total coliform column is left out:
the permission names the E. coli and enterococci counts. Not Environment Agency samples; Waterhead is not a designated
bathing water. Nothing here is compared with a forecast.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = (Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "tim-boden-aafaf" / "originals-2026-10-25"
        / "25-26 Bacteria Levels.xlsx")
XLSX_SHA = "c9f229c832eea9782b6d8874e79c8feaa430f8443549669b52778b647516d3b5"   # as received 25 Oct 2026
OUT = ROOT / "data" / "research" / "waterhead_wet.v1.json"
SCHEMA, VERSION = "swimsignal.waterhead-wet", "1.1.0"
COLS = {"Date": "date", "E-Coli (cfu/100ml)": "ecoli", "Intestinal Enterococci (cfu/100ml)": "ie"}
CLAIM = {
    "public_wording": "Weekly water samples taken at Waterhead, Windermere, by Ambleside Action for a Future's Waterhead "
                      "E. coli Testing project, and the E. coli and intestinal enterococci counted in each. A sample is "
                      "the water at that place at the time it was taken: not today's water, and not the rest of the lake.",
    "not_claimed": ["the water now", "the water elsewhere in Windermere", "a forecast", "a bathing water rating",
                    "that water is safe to swim", "a check of SwimSignal's forecast"],
}
# What the sheet and the report say about each season, and what is not yet known (asked of Tim, not yet answered).
SEASONS = {
    2025: "Mostly on Thursday mornings, analysed by Simplex Health's laboratory (the WET technical report, 17 Nov 2025).",
    2026: "Mondays and Tuesdays. The laboratory, method and time of day are not yet confirmed.",
}
# The SwimSignal spots these samples are linked from (1.1): the spot's page says where its local samples are.
SPOTS = ["osm-windermere-waterhead"]
OPEN = [
    "The exact sampling point at Waterhead: the sheet has no site column, and the email names Waterhead.",
    "Whether 2026 used the same laboratory and method as 2025.",
    "What a recorded 0 means: most likely below the method's detection limit, not a true zero.",
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(xlsx: Path) -> list[dict]:
    """The sheet's samples in date order, E. coli and enterococci only. Stops if the file is not the one received."""
    import openpyxl
    if (got := sha256(xlsx)) != XLSX_SHA:
        raise SystemExit(f"{xlsx} is not the sheet received on 25 Oct 2026 (sha256 {got})")
    rows = list(openpyxl.load_workbook(xlsx, data_only=True).worksheets[0].iter_rows(values_only=True))
    head = [COLS.get(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {k: v for k, v in zip(head, r) if k}
        if d.get("date") is None:
            continue   # the blank rows between the header and each season
        out.append({"date": d["date"].date().isoformat() if isinstance(d["date"], datetime) else str(d["date"]),
                    "ecoli": int(d["ecoli"]), "ie": int(d["ie"])})
    return sorted(out, key=lambda s: s["date"])


def season(year: int, samples: list[dict]) -> dict:
    s = [x for x in samples if x["date"].startswith(str(year))]
    figs = lambda k: {"median": statistics.median(x[k] for x in s), "max": max(x[k] for x in s)}
    return {"season": year, "first": s[0]["date"], "last": s[-1]["date"], "samples": len(s),
            "ecoli": figs("ecoli"), "ie": figs("ie"), "how": SEASONS[year]}


def build(xlsx: Path) -> dict:
    samples = read(xlsx)
    return {
        "schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "site": {"name": "Waterhead, Windermere", "confirmed": False,
                 "note": "Named in Tim Boden's email of 25 Oct 2026; the sheet itself has no site column."},
        "units": "per 100 ml, as the sheet records them (its headings say cfu/100ml)",
        "claim": CLAIM,
        "seasons": [season(y, samples) for y in sorted(SEASONS)],
        "open_questions": OPEN,
        "spots": SPOTS,
        "attribution": "Bacteria counts: Ambleside Action for a Future, Waterhead E. coli Testing (WET) project.",
        "permission": "Public domain (Tim Boden, 25 Oct 2026): may be used and forwarded with credit to Ambleside "
                      "Action for a Future.",
        "report": {"title": "Waterhead E.coli Testing (WET) Project Technical Report", "author": "Tim Boden",
                   "date": "2025-11-17"},
        "sources": {"sheet": "25-26 Bacteria Levels.xlsx", "sheet_sha256": XLSX_SHA, "received": "2026-10-25",
                    "code_sha256": {"scripts/export_waterhead_wet.py": sha256(Path(__file__))}},
        "samples": samples,
    }


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("site", "units", "claim", "seasons", "attribution", "permission", "sources", "samples"):
        if k not in doc:
            err.append(f"missing {k}")
    if "not today's water" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not today's water")
    s = doc.get("samples", [])
    dates = [x["date"] for x in s]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        err.append("samples not in date order, or a date twice")
    for x in s:
        date.fromisoformat(x["date"])
        if set(x) != {"date", "ecoli", "ie"}:
            err.append(f"{x['date']}: fields {sorted(x)}, not date, ecoli and ie")
        elif any(not isinstance(x[k], int) or x[k] < 0 for k in ("ecoli", "ie")):
            err.append(f"{x['date']}: a count that is not a whole number of 0 or more")
    if sum(z["samples"] for z in doc.get("seasons", [])) != len(s):
        err.append("season counts do not add up to the samples")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--xlsx", type=Path, default=XLSX)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.xlsx)
        if problems := check(doc):
            raise SystemExit("\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {a.out}: {len(doc['samples'])} samples")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
