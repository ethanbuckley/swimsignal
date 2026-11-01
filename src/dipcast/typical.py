"""What a bathing water's own EA samples have read: the middle one and the range the middle 8 in 10 fell in. Past
samples, never a forecast. The inland bathing waters' come from the E. coli evidence export (build_site.
attach_typical_readings), the English coastal ones' from scripts/export_coastal_typical.py.
"""

from __future__ import annotations

import math

MIN_SAMPLES = 20   # samples needed before a bathing water's typical readings are given


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
