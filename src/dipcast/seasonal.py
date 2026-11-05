"""Past spills upstream by month: a record of the past for a spot's page, not a forecast.

For each spot, by calendar month: the share of days on which at least one monitored storm overflow
upstream of it reported a spill, over the years whose records cover those overflows. The page words it
as history and claims nothing about the water (site/seasonal.js).

Why "any overflow upstream" and not a share weighted by reach: every count here can be checked against
the event files (filter them to the spot's overflows, count the days), and a weighted share needs a
paragraph to explain, as spot_scores.py found for its own counts. The cost: an overflow near the 60 km
limit counts as much as one beside the spot, so a spot with many overflows upstream shows high shares.
The page says so.

Which years count (the event records are uneven before 2024):
- An overflow-year is covered when an event-level record is held for its company that year (RECORDS) and
  the Environment Agency's annual return for that year lists the overflow with its monitor working at
  least MIN_EDM_PCT of the year. A monitor installed or broken mid-year would undercount, so it is left out.
- A spot-year is used when at least MIN_COVERED of its upstream overflows are covered that year. The
  file keeps how many were, so the page can say it.
- Only whole calendar years: 2020 has no annual return held to show which monitors worked, and 2026 has
  no Environment Agency file yet.

A spill day is a UTC day an event touches at the overflow (model.features.spill_days, the spill model's
own label). Days are counted from the calendar, so February 2024 has 29.

The event files are held off the repo (data/processed, git-ignored), so the table is made off CI by
scripts/make_seasonal_spills.py and committed as data/raw/seasonal_spills.json. Each spot's entry keeps a
fingerprint of the overflow ids it was counted on; the build shows it only where the build's own upstream
list has the same ids (attach), so a re-traced river or a new monitor never gets another set's history.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

MIN_EDM_PCT = 90.0      # an overflow-year counts when its monitor worked this share of the year (annual return)
MIN_COVERED = 0.8       # a spot-year is used when this share of its upstream overflows are covered
YEARS = (2021, 2022, 2023, 2024, 2025)
FILE_BYTES_LIMIT = 60_000   # the committed table's limit (tests/test_seasonal.py)

# Event-level records held, by company and year, and whose they are. The EA's start/stop files (OGL v3.0)
# cover every company in England for 2024 and 2025, Welsh Water's overflows in England included. Earlier
# years come from the companies' own layers, CC BY 4.0 (docs/EARLIER-SPILL-HISTORY-2026-10.md). Left out
# on purpose: Thames Water's alert stream (it holds a snapshot before Dec 2022 and agrees with the EA file
# on about 90% of days), South West Water's monthly layer (the EA file covers 2025) and Southern's and
# Yorkshire's own event files, which carry no licence (docs/OVERFLOW-DATA-SOURCES-2026-10.md).
EA_COMPANIES = ("Anglian Water", "Dwr Cymru Welsh Water", "Northumbrian Water", "Severn Trent Water", "South West Water",
                "Southern Water", "Thames Water", "United Utilities", "Wessex Water", "Yorkshire Water")
RECORDS: dict[str, tuple[int, ...]] = {c: (2024, 2025) for c in EA_COMPANIES}
RECORDS["Northumbrian Water"] = (2021, 2022, 2023, 2024, 2025)
RECORDS["Wessex Water"] = (2021, 2022, 2023, 2024, 2025)
RECORDS["United Utilities"] = (2023, 2024, 2025)
SOURCES = {
    "ea": "Environment Agency, Event Duration Monitoring - Storm Overflow - Start/Stop Detailed Data, 2024 and 2025. "
          "© Environment Agency copyright and/or database right. Open Government Licence v3.0.",
    "northumbrian": "EDM Spill Data Northumbrian Water, 2021 to 2023, Northumbrian Water, via Stream, CC BY 4.0.",
    "wessex": "Wessex Water Event Duration Monitoring 2020-2023 © 2025 by Wessex Water, CC BY 4.0 (2021 to 2023; "
              "overflows matched to the annual returns' ids by their 2024 events).",
    "united_utilities": "United Utilities Event Duration Monitoring 2023, via Stream, CC BY 4.0.",
    "returns": "Environment Agency, Event Duration Monitoring annual returns 2021 to 2025, OGL v3.0 (which monitors worked).",
}


def fingerprint(ids) -> str:
    """A short hash of a set of overflow ids, order-free: the build compares it with its own upstream list."""
    return hashlib.sha1("\n".join(sorted({str(i) for i in ids})).encode()).hexdigest()[:12]


def month_days(year: int) -> list[int]:
    return [calendar.monthrange(year, m)[1] for m in range(1, 13)]


def covered_years(returns_rows, records: dict[str, tuple[int, ...]] = RECORDS, min_pct: float = MIN_EDM_PCT,
                  keep=None) -> set[tuple[str, int]]:
    """(site_id, year) pairs that count: a record is held for the company that year and the annual return
    lists the overflow with its monitor working at least min_pct of the year. returns_rows: iterable of
    (site_id, company, year, edm_operational_pct). keep(site_id, company, year) can drop more (the Wessex
    ids the crosswalk did not map)."""
    out = set()
    for sid, company, year, pct in returns_rows:
        if not sid or year not in records.get(company, ()) or pct is None or pct != pct or pct < min_pct:
            continue
        if keep is not None and not keep(sid, company, year):
            continue
        out.add((str(sid), int(year)))
    return out


def spot_history(ids: list[str], spill_days: dict[str, set], covered: set[tuple[str, int]],
                 years=YEARS, min_covered: float = MIN_COVERED) -> dict:
    """One spot's entry: for each used year, its monthly counts of days with a spill reported at any covered
    upstream overflow (`spill`), and how many of the spot's overflows were covered (`covered` of `overflows`).
    spill_days maps an overflow id to its set of spill days as datetime.date. Years that fall short of
    min_covered are listed in `short` with their counts, for the page's coverage line. No overflows: an
    entry saying so, with no years."""
    ids = sorted({str(i) for i in ids})
    out = {"fp": fingerprint(ids), "overflows": len(ids), "years": {}, "short": {}}
    if not ids:
        return out
    for y in years:
        cov = [i for i in ids if (i, y) in covered]
        if len(cov) < min_covered * len(ids):
            out["short"][str(y)] = len(cov)
            continue
        days = set()
        for i in cov:
            days |= {d for d in spill_days.get(i, ()) if d.year == y}
        spill = [0] * 12
        for d in days:
            spill[d.month - 1] += 1
        out["years"][str(y)] = {"covered": len(cov), "spill": spill}
    return out


def summary(entry: dict) -> dict | None:
    """What the page shows from an entry: per month, days counted (`days`) and days with a spill (`spill`)
    summed over the used years, the years, and the fewest overflows covered in any of them. None when no
    year was used."""
    ys = sorted(entry.get("years") or {}, key=int)
    if not ys:
        return None
    days, spill = [0] * 12, [0] * 12
    for y in ys:
        md = month_days(int(y))
        for m in range(12):
            days[m] += md[m]
            spill[m] += int(entry["years"][y]["spill"][m])
    return {"years": [int(y) for y in ys], "overflows": entry["overflows"],
            "covered_min": min(entry["years"][y]["covered"] for y in ys), "days": days, "spill": spill,
            "short": {int(k): v for k, v in (entry.get("short") or {}).items()}}


def read_table(path: Path) -> dict:
    t = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(t.get("spots"), dict):
        raise ValueError(f"{path.name}: no spots")
    return t


def attach(results: list[dict], upstream: dict[str, list[dict]], path: Path) -> dict:
    """`seasonal` (summary) on each spot whose entry in the table was counted on the same overflows as the
    build's upstream list, or {"none": true} on a spot with no monitored overflow upstream (the page says so).
    A spot not in the table, or whose overflows differ, gets nothing and is counted in the health. Never
    stops the build: a bad table leaves every page without the panel."""
    try:
        table = read_table(path)
    except Exception as e:  # noqa: BLE001 - history beside the forecast must not sink the build
        return {"shown": 0, "warnings": [f"seasonal history not shown: {e}"]}
    shown, none, too_few, missing, changed = 0, 0, 0, [], []
    for r in results:
        if r.get("error"):
            continue
        ids = [c.get("site_id") for c in upstream.get(r["id"], []) if c.get("site_id")]
        if not ids:
            r["seasonal"] = {"none": True}
            none += 1
            continue
        e = table["spots"].get(r["id"])
        if e is None:
            missing.append(r["id"])
            continue
        if e.get("fp") != fingerprint(ids):
            changed.append(r["id"])
            continue
        s = summary(e)
        if s is None:   # no year reached MIN_COVERED: the page says the records are too thin
            r["seasonal"] = {"too_few": True, "overflows": e["overflows"]}
            too_few += 1
            continue
        r["seasonal"] = {**s, "made": table.get("made")}
        shown += 1
    warnings = []
    if changed:
        warnings.append(f"seasonal history hidden at {len(changed)} spot(s) whose overflows changed since "
                        f"{path.name} was made: {', '.join(changed[:5])} (run scripts/make_seasonal_spills.py)")
    return {"shown": shown, "none": none, "too_few": too_few, "missing": len(missing), "changed": len(changed), "warnings": warnings}
