"""How often each river gauge rose quickly, by calendar month, 21 November 2024 to 24 October 2026: a dated
observation file for the site (docs/RIVER-RISE-HISTORY-CONTRACT-v1.md), from the river-rises C3 record's committed
table. Offline, from committed files only:

    uv run python scripts/export_river_rise_history.py export [--out PATH]
    uv run python scripts/export_river_rise_history.py check [PATH]

The table (docs/RIVER-RISES-C3-2026-11-base-rates.csv) is the C3 outcome map's deliverable for "C3 not shown better
than the gauge-month base rate" (docs/RIVER-RISES-C3-2026-11.md, "Continuation"); the gauge-to-spot mapping is the
run's own (docs/RIVER-RISES-SCOPE-2026-10-gauges.csv, `spots`). This file is history, not a forecast or a warning.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "river_rise_history.v1.json"
SCHEMA, VERSION = "swimsignal.river-rise-history", "1.0.0"
RECORD = "docs/RIVER-RISES-C3-2026-11.md"
TABLE = "docs/RIVER-RISES-C3-2026-11-base-rates.csv"
GAUGES = "docs/RIVER-RISES-SCOPE-2026-10-gauges.csv"
SPOT_LISTS = ("spots.csv", "spots-osm.csv")
FIRST, LAST = "2024-11-21", "2026-10-24"   # the record's period: every issue hour from 21 Nov 2024 to 24 Oct 2026
RISE_SHARE, HORIZON_H, DELAY_H = 0.2, 3, 1.0   # the record's label (protocol.SHARE, PRIMARY_H, DELAY_H)
# The display rule, fixed on 6 November 2026 before any page line was written, having seen only how many hours each
# gauge-month counts (127 to 1,488), not which spots or months it would drop: a month is shown only with at least
# MIN_HOURS hours counted (20 days of hours, so one or two rises cannot make a figure on their own) and readings in
# both of its years, so "2024 and 2025" is true of it.
MIN_HOURS, MIN_YEARS = 480, 2
WORDS = "rose by more than a fifth of its usual range within 3 hours"
CLAIM = {
    "public_wording": "How often, in each calendar month from 21 November 2024 to 24 October 2026, an hour at this "
                      "gauge was followed within 3 hours by a rise of more than a fifth of its usual range. History "
                      "from the Environment Agency's archived readings, not a forecast of what the river will do.",
    "not_claimed": ["a forecast or a warning of a rise", "anything about swimming safety or water quality",
                    "the river's level now or at the swim spot", "that a month with no rise recorded will have none",
                    "anything about months or years outside the period"],
}
LIMITS = [
    "Two years at most behind each month: November and December are 2024 and 2025 (November 2024 from the 21st); "
    "January to October are 2025 and 2026 (October 2026 to the 24th). Two winters are not a climate.",
    "The readings are the Environment Agency's archived 15-minute series (Hydrology API), checked and corrected after "
    "the fact, not what the live feed showed at the time.",
    "Hours when the river was already high, or already rising fast as the site's River level tile says it, are not "
    "counted, nor hours with no reading at most 24 hours old (read 1 hour late, as the site would have had it).",
    "A fifth of the usual range is a different rise in metres at each gauge, and a lock or weir reach can rise with "
    "the weir's setting rather than the river (Trowlock Island on the Thames: the record's 5.4% is the lock pair).",
    "The gauge can be some way from the swim spot; the figure is the gauge's, not the spot's.",
    "Not a forecast: the record's model using this history, radar and upstream gauges (C3) was not shown better than "
    "this history alone, and nothing here says what the river will do tomorrow.",
]
ATTRIBUTION = ["Environment Agency Hydrology data (15-minute river levels), Open Government Licence v3.0",
               "This uses Environment Agency flood and river level data from the real-time data API (Beta): each "
               "gauge's usual range"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def month_years(month: int) -> list[int]:
    """The two years the period holds of a calendar month: November and December 2024 and 2025, else 2025 and 2026."""
    return [2024, 2025] if month >= 11 else [2025, 2026]


def last_commit(path: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--", path], capture_output=True,
                           text=True, timeout=20, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None


def listed_spots(root: Path = ROOT) -> set[str]:
    out = set()
    for f in SPOT_LISTS:
        with (root / f).open(newline="") as fh:
            out |= {r["id"] for r in csv.DictReader(fh)}
    return out


def build(root: Path = ROOT) -> dict:
    with (root / TABLE).open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    with (root / GAUGES).open(newline="") as fh:
        gauges = {r["gauge"]: r for r in csv.DictReader(fh)}
    spots_known = listed_spots(root)
    out, seen_spots = [], set()
    for ref in sorted({r["gauge"] for r in rows}, key=lambda g: (gauges[g]["river"], gauges[g]["label"])):
        g = gauges[ref]
        spots = [s for s in g["spots"].split(";") if s]
        missing = [s for s in spots if s not in spots_known]
        if missing:
            raise SystemExit(f"{ref}: spots not in {', '.join(SPOT_LISTS)}: {', '.join(missing)}")
        seen_spots |= set(spots)
        months = []
        for r in sorted((r for r in rows if r["gauge"] == ref), key=lambda r: int(r["month"])):
            m, n, k = int(r["month"]), int(r["hours"]), int(r["rise_hours"])
            yrs = int(r["years_in_month"])
            months.append({"month": m, "hours": n, "rise_hours": k, "rises": int(r["episodes"]),
                           "share": float(r["share"]), "years_in_month": yrs,
                           "years": month_years(m) if yrs == 2 else None})
        out.append({"gauge": ref, "label": g["label"], "river": g["river"], "typical_low_m": float(g["low"]),
                    "typical_high_m": float(g["high"]), "has_upstream_gauge": r_bool(rows, ref), "spots": spots,
                    "months": months})
    shown = sum(shown_month(m) for g in out for m in g["months"])
    return {"schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "period": {"first": FIRST, "last": LAST,
                       "years_by_month": "November and December: 2024 and 2025 (November 2024 from the 21st); "
                                         "January to October: 2025 and 2026 (October 2026 to the 24th)"},
            "definition": {"words": WORDS, "rise_share": RISE_SHARE, "horizon_h": HORIZON_H, "delay_h": DELAY_H,
                           "usual_range": "The Environment Agency's usual range for the gauge (typicalRangeLow to "
                                          "typicalRangeHigh on its stage scale, from the flood-monitoring API), the "
                                          "range the site's River level tile draws. `typical_low_m` and "
                                          "`typical_high_m` are the values the run used.",
                           "hours": "Whole hours when the gauge had a reading at most 24 hours old, published 1 hour "
                                    "before (as the site would have had it), and the site would have shown no word: "
                                    "the level not above its usual range and not already rising fast",
                           "rise_hours": "Of those hours, how many were followed within 3 hours by a reading more "
                                         "than a fifth of the usual range above the hour's reading",
                           "rises": "Runs of consecutive rise hours at the gauge: about one for each separate rise",
                           "share": "rise_hours / hours, five places"},
            "display": {"min_hours": MIN_HOURS, "min_years": MIN_YEARS,
                        "rule": f"A month is shown only with at least {MIN_HOURS} hours counted and readings in both "
                                "of its years; otherwise the page says nothing for that month. Fixed on 6 November "
                                "2026 from the spread of hours counted, before any page line was written."},
            "claim": CLAIM, "limits": LIMITS, "attribution": ATTRIBUTION,
            "sources": {"record": RECORD, "table": {"file": TABLE, "sha256": sha256(root / TABLE)},
                        "gauges": {"file": GAUGES, "sha256": sha256(root / GAUGES)},
                        "table_commit": last_commit(TABLE), "record_commit": last_commit(RECORD),
                        "code_sha256": sha256(Path(__file__))},
            "gauges": out,
            "coverage": {"gauges": len(out), "gauge_months": sum(len(g["months"]) for g in out),
                         "gauge_months_shown": shown, "spots": len(seen_spots)}}


def r_bool(rows: list[dict], ref: str) -> bool:
    return next(r for r in rows if r["gauge"] == ref)["has_upstream_gauge"] == "True"


def shown_month(m: dict | None, min_hours: int = MIN_HOURS, min_years: int = MIN_YEARS) -> bool:
    """The display rule: enough hours counted, and readings in both of the month's years."""
    return bool(m) and m.get("hours", 0) >= min_hours and (m.get("years_in_month") or 0) >= min_years \
        and isinstance(m.get("years"), list)


def check(doc: dict) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("generated_at", "period", "definition", "display", "claim", "limits", "attribution", "sources", "gauges",
              "coverage"):
        if k not in doc:
            err.append(f"missing {k}")
    if "not a forecast" not in doc.get("claim", {}).get("public_wording", ""):
        err.append("the claim must say it is not a forecast")
    d = doc.get("definition", {})
    if d.get("rise_share") != RISE_SHARE or d.get("horizon_h") != HORIZON_H or d.get("words") != WORDS:
        err.append("definition is not the record's (a fifth of the usual range within 3 hours)")
    disp = doc.get("display", {})
    if not (isinstance(disp.get("min_hours"), int) and disp["min_hours"] > 0 and disp.get("min_years") == 2):
        err.append("display rule needs a positive min_hours and min_years 2")
    if doc.get("period", {}).get("first") != FIRST or doc.get("period", {}).get("last") != LAST:
        err.append("period is not the record's")
    for k in ("table", "gauges"):
        s = doc.get("sources", {}).get(k, {})
        if not (isinstance(s.get("sha256"), str) and len(s["sha256"]) == 64):
            err.append(f"sources.{k} needs a SHA-256")
    refs, spots = [], []
    for g in doc.get("gauges", []):
        ref = g.get("gauge")
        refs.append(ref)
        spots += g.get("spots") or []
        if not g.get("spots"):
            err.append(f"{ref}: serves no spot")
        if not (isinstance(g.get("typical_low_m"), float) and isinstance(g.get("typical_high_m"), float)
                and g["typical_high_m"] > g["typical_low_m"]):
            err.append(f"{ref}: usual range missing or empty")
        ms = [m.get("month") for m in g.get("months", [])]
        if ms != sorted(set(ms)) or not all(isinstance(m, int) and 1 <= m <= 12 for m in ms):
            err.append(f"{ref}: months not 1 to 12 in order, once each")
        for m in g.get("months", []):
            n, k, e = m.get("hours"), m.get("rise_hours"), m.get("rises")
            if not (isinstance(n, int) and isinstance(k, int) and isinstance(e, int) and 0 <= e <= k <= n and n > 0):
                err.append(f"{ref} month {m.get('month')}: counts out of order (rises <= rise hours <= hours)")
                continue
            if (k > 0) != (e > 0):
                err.append(f"{ref} month {m['month']}: rise hours without a rise, or a rise without hours")
            if abs(m.get("share", -1) - round(k / n, 5)) > 1e-9:
                err.append(f"{ref} month {m['month']}: share is not rise_hours / hours")
            y = m.get("years_in_month")
            if y not in (1, 2) or (y == 2 and m.get("years") != month_years(m["month"])) or (y == 1 and m.get("years") is not None):
                err.append(f"{ref} month {m['month']}: years do not match the period")
    if len(refs) != len(set(refs)):
        err.append("a gauge is listed twice")
    if len(spots) != len(set(spots)):
        err.append("a spot is served by two gauges")
    cov = doc.get("coverage", {})
    if cov.get("gauges") != len(refs) or cov.get("spots") != len(set(spots)) \
            or cov.get("gauge_months") != sum(len(g.get("months", [])) for g in doc.get("gauges", [])):
        err.append("coverage counts do not match")
    elif cov.get("gauge_months_shown") != sum(shown_month(m, disp.get("min_hours", MIN_HOURS))
                                              for g in doc.get("gauges", []) for m in g.get("months", [])):
        err.append("coverage counts do not match the display rule")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build()
        problems = check(doc)
        if problems:
            raise SystemExit("\n".join(problems))
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
