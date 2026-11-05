"""What a bathing water's own samples have read: the middle one and the range the middle 8 in 10 fell in. Past
samples, never a forecast. The English inland bathing waters' come from the E. coli evidence export (build_site.
attach_typical_readings) and go on their spot pages; the directories' on the coverage page (the English coast, Wales,
the Republic of Ireland, Northern Ireland) from one committed file each, written off CI by
scripts/export_typical_readings.py, and go on each site's card (attach, line).
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path

MIN_SAMPLES = 20   # samples needed before a bathing water's typical readings are given
SCHEMA, MAJOR = "swimsignal.typical-readings", "1"
RESEARCH = Path(__file__).resolve().parents[2] / "data" / "research"
# One file a directory, keyed by the directory's own site ids.
FILES = {n: RESEARCH / f"typical_{n}.v1.json" for n in ("england_coast", "wales", "ireland", "northern_ireland")}
LINES = {"coast": 500, "estuary": 500, "lake": 900, "river": 900, "inland": 900}   # the "sufficient" E. coli lines


def typical_readings(samples: list[dict], line: int) -> dict | None:
    """From samples {"t": ISO time, "ecoli": number, "q": "<", ">" or None}: the middle one and the 10th and 90th in
    100 by rank, how many, their years, and how many were over `line` (900 inland, 500 coastal: the "sufficient"
    standards' E. coli lines). A value the lab gave as a limit stays one ("<10", ">10000"): a "<10" ranks below every
    count. Other values to two significant figures. None under MIN_SAMPLES samples."""
    xs = [x for x in samples or [] if isinstance(x.get("ecoli"), int | float) and x.get("t")]
    if len(xs) < MIN_SAMPLES:
        return None
    xs = sorted(xs, key=lambda x: x["ecoli"] + {"<": -0.5, ">": 0.5}.get(x.get("q"), 0.0))
    n = len(xs)

    def at(q: float):
        x = xs[max(0, math.ceil(q * n) - 1)]
        if x.get("q") in ("<", ">"):
            return f"{x['q']}{x['ecoli']:g}"
        v = float(f"{x['ecoli']:.2g}")
        return int(v) if v == int(v) else v
    years = sorted({x["t"][:4] for x in xs})
    return {"samples": n, "first_year": int(years[0]), "last_year": int(years[-1]), "low": at(0.1), "median": at(0.5),
            "high": at(0.9), "line": line, "over_line": sum(1 for x in xs if x["ecoli"] > line and x.get("q") != "<")}


def attach(snapshot: dict | None, nation: str, path: Path | None = None) -> int:
    """Each directory site's `typical` from its nation's file, and the snapshot's `typical` (period, source, credit,
    when exported). A missing file, or one of another schema or major version, adds nothing. Returns how many sites
    got one."""
    try:
        doc = json.loads(Path(path or FILES[nation]).read_text())
    except (OSError, ValueError):
        return 0
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != MAJOR or not snapshot:
        return 0
    n = 0
    for site in snapshot.get("sites") or []:
        t = (doc.get("sites") or {}).get(site.get("id"))
        if t:
            site["typical"] = t
            n += 1
    snapshot["typical"] = {k: doc.get(k) for k in ("period", "generated_at", "source", "credit")}
    return n


def _reading(v) -> str:
    """A count as the coverage page gives it: "under 10" for the lab's "<10", "over 10,000" for ">10000"."""
    if isinstance(v, str):
        return f'{"under" if v[:1] == "<" else "over"} {float(v[1:]):,.0f}'
    return f"{v:,.0f}" if v >= 10 else f"{v:g}"


def line(t: dict) -> str:
    """One line under a directory site: what its own past samples read. Never a forecast. Plain text."""
    years = f'{t["first_year"]}–{t["last_year"]}' if t["first_year"] != t["last_year"] else str(t["first_year"])
    over = f'{t["over_line"]} over {t["line"]}' if t["over_line"] else f'none over {t["line"]}'
    spread = _reading(t["low"]) if t["low"] == t["high"] else f'between {_reading(t["low"])} and {_reading(t["high"])}'
    return (f'Past samples, {t.get("months", "May–September")} {years}: the middle of {t["samples"]} read '
            f'{_reading(t["median"])} E. coli per 100 ml, the middle 8 in 10 {spread}; '
            f'{over}. Not a forecast')


def note(snapshot: dict, inland: bool = False) -> str:
    """The paragraph above a directory's list that says what "Past samples" are, or '' without them. HTML."""
    t = snapshot.get("typical") if snapshot else None
    if not t:
        return ''
    lines = ("500 is the coastal minimum standard's E. coli line and 900 the inland one" if inland
             else "500 is the coastal minimum standard's E. coli line")
    return ('<p class="small">"Past samples" are each site\'s own official samples, '
            f'{escape(t.get("period") or "")}: the middle sample and the range the middle 8 in 10 fell in, with how many '
            'were over the minimum standard\'s line. They describe past seasons, not today. For comparison, a coastal '
            'bathing water is rated Excellent when about 95 in 100 of its samples, over four seasons, are under 250 E. coli '
            f'per 100 ml (an inland one, under 500); the rating also counts intestinal enterococci. {lines}. '
            f'{escape(t.get("credit") or "")}</p>')
