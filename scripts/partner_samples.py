"""Partner water samples (docs/PARTNER-SAMPLES-CONTRACT-v1.md): check a file a partner sends, and write the first
conforming partner, Ambleside Action for a Future's Waterhead samples, from their published export.

    uv run python scripts/partner_samples.py check FILE.csv [FILE.csv ...]
    uv run python scripts/partner_samples.py waterhead [--out PATH]
    uv run python scripts/partner_samples.py check-waterhead

`check` prints each error and warning with its row, and exits 1 on any error. `waterhead` reads only
data/research/waterhead_wet.v1.json, so every value is the published one. `check-waterhead` writes it again in memory
and fails if the committed file or any result differs from the export. Standard library only: a partner's file is
checked before anything else touches it.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "partner-samples-template-v1.csv"
WET = ROOT / "data" / "research" / "waterhead_wet.v1.json"
WATERHEAD = ROOT / "data" / "research" / "partners" / "aafaf-waterhead.partner-v1.csv"
# The columns are the template's header, so the template and the checker cannot drift apart.
COLUMNS = tuple(next(csv.reader(TEMPLATE.open(newline=""))))
# Blank allowed; the conditional ones are checked by rule below.
OPTIONAL = {"sampled_time", "timezone", "qualifier", "method", "lower_limit", "upper_limit", "attribution",
            "publish_consent_on", "test_consent_on", "consent_ref", "notes"}
BACTERIA = {"ecoli", "intestinal_enterococci", "total_coliforms"}
OTHER = re.compile(r"other:[a-z0-9_ -]{1,40}")
UNITS = {"cfu/100ml": "plate_count", "mpn/100ml": "mpn"}   # each bacteria unit and the method type it belongs to
CHOICES = {
    "site_confirmed": {"yes", "no"},
    "timezone": {"", "Europe/London", "UTC"},
    "qualifier": {"", "<", ">"},
    "method_type": {"plate_count", "mpn", "other", "not_stated"},
    "limits_written": {"qualifier", "zero", "not_stated"},
    "lab_accredited": {"yes", "no", "not_stated"},
    "licence": {"public-domain", "CC-BY-4.0", "OGL-3.0", "none"},
    "publish_consent": {"yes", "no"},
    "test_use": {"holdout", "exploratory", "none"},
}
CREDIT = {"CC-BY-4.0", "OGL-3.0"}   # licences that need an attribution
PARTNER_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
# Great Britain, Ireland and their islands, loosely: a swapped latitude and longitude, or a dropped minus sign, falls outside.
LAT, LON = (49.8, 61.0), (-10.7, 2.0)


def _day(v: str) -> date | None:
    try:
        return date.fromisoformat(v) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None
    except ValueError:
        return None


def _num(v: str) -> float | None:
    try:
        x = float(v)
    except ValueError:
        return None
    return x if x == x and abs(x) != float("inf") else None


def check_rows(rows: list[dict], today: date | None = None) -> tuple[list[str], list[str]]:
    """Errors and warnings for one partner's rows, each naming its row (2 is the first after the header)."""
    today = today or date.today()
    errors, warnings, seen, samples = [], [], set(), {}
    if not rows:
        return ["the file has no rows"], []
    missing, extra = set(COLUMNS) - set(rows[0]), set(rows[0]) - set(COLUMNS)
    if missing or extra:
        return [f"columns: missing {sorted(missing)}, unknown {sorted(extra)}"], []
    partners = {r["partner_id"] for r in rows}
    if len(partners) != 1:
        errors.append(f"one partner per file, not {sorted(partners)}")
    for n, r in enumerate(rows, start=2):
        r = {k: (v or "").strip() for k, v in r.items()}
        e = lambda msg: errors.append(f"row {n}: {msg}")
        w = lambda msg: warnings.append(f"row {n}: {msg}")
        for k in COLUMNS:
            if k not in OPTIONAL and not r[k]:
                e(f"{k} is blank")
        for k, ok in CHOICES.items():
            if r[k] not in ok:
                e(f"{k} {r[k]!r} is not one of {sorted(x for x in ok if x)}")
        if r["partner_id"] and not PARTNER_ID.fullmatch(r["partner_id"]):
            e("partner_id must be lower case letters, digits and hyphens")
        lat, lon = _num(r["site_lat"]), _num(r["site_lon"])
        if lat is None or lon is None or not (LAT[0] <= lat <= LAT[1] and LON[0] <= lon <= LON[1]):
            e("site_lat and site_lon must be a point in Great Britain or Ireland (WGS84 decimal degrees)")
        sampled, received = _day(r["sampled_on"]), _day(r["received_on"])
        if not sampled:
            e("sampled_on is not a real YYYY-MM-DD date")
        if not received:
            e("received_on is not a real YYYY-MM-DD date")
        elif received > today:
            e("received_on is in the future")
        if sampled and received and sampled > received:
            e("sampled after it was received")
        if r["sampled_time"]:
            if not TIME.fullmatch(r["sampled_time"]):
                e("sampled_time must be HH:MM")
            if not r["timezone"]:
                e("a sampled_time needs a timezone (Europe/London or UTC)")
        else:
            w("no sampled_time: it can be matched to a forecast day, not an issue time")
        det, unit, mt = r["determinand"], r["unit"], r["method_type"]
        if det not in BACTERIA and not OTHER.fullmatch(det):
            e(f"determinand {det!r} is not ecoli, intestinal_enterococci, total_coliforms or other:<name>")
        if det in BACTERIA:
            if unit not in UNITS:
                e(f"unit {unit!r}: bacteria are cfu/100ml or mpn/100ml")
            elif mt in ("plate_count", "mpn") and UNITS[unit] != mt:
                e(f"method_type {mt} does not give {unit}")
        result = _num(r["result"])
        if result is None or result < 0:
            e("result must be a number of 0 or more")
        lo, hi = (_num(r[k]) if r[k] else None for k in ("lower_limit", "upper_limit"))
        for k, v in (("lower_limit", lo), ("upper_limit", hi)):
            if r[k] and (v is None or v < 0):
                e(f"{k} must be a number of 0 or more, or blank")
        if result is not None:
            q, lw = r["qualifier"], r["limits_written"]
            if q == "<" and lo is not None and result != lo:
                w(f"below-limit value {result:g} is not the stated lower_limit {lo:g}")
            if q == ">" and hi is not None and result != hi:
                w(f"above-limit value {result:g} is not the stated upper_limit {hi:g}")
            if result == 0 and not q:
                if lw == "not_stated":
                    w("a 0 with limits_written not_stated: it may be a below-limit result, not no bacteria")
                elif lw == "qualifier" and (lo or 0) > 0:
                    e("a 0 where below-limit values are written with <: write <limit instead")
            if lw == "zero" and lo is None:
                e("limits_written zero needs the lower_limit that 0 stands for")
        if r["site_confirmed"] == "no":
            w("site_confirmed no: the point is approximate")
        if r["licence"] in CREDIT and not r["attribution"]:
            e(f"licence {r['licence']} needs an attribution")
        for flag, on, k in (("publish_consent", "yes", "publish_consent_on"), ("test_use", None, "test_consent_on")):
            given = r[flag] == on if on else r[flag] in ("holdout", "exploratory")
            if given:
                d = _day(r[k])
                if not d:
                    e(f"{k} must be the real date the agreement was given")
                elif d > today:
                    e(f"{k} is in the future")
        if r["publish_consent"] == "yes" and r["licence"] == "none":
            e("publish_consent yes needs a licence other than none")
        if (r["publish_consent"] == "yes" or r["test_use"] != "none") and not r["consent_ref"]:
            e("a permission needs consent_ref: where the written agreement is kept")
        # The held-out rule: agreed before the sample existed, so nobody chose it after seeing the result.
        agreed = _day(r["test_consent_on"])
        if r["test_use"] == "holdout" and sampled and agreed and agreed >= sampled:
            e("holdout agreed on or after the sampling day: only an agreement made before sampling keeps a result held out; use exploratory")
        key = (r["partner_id"], r["sample_id"], det)
        if key in seen:
            e(f"sample {r['sample_id']} has {det} twice")
        seen.add(key)
        where = (r["site_name"], r["site_lat"], r["site_lon"], r["sampled_on"], r["sampled_time"])
        if samples.setdefault(r["sample_id"], where) != where:
            e(f"sample {r['sample_id']} has two sites, days or times")
    return errors, warnings


def read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:   # a spreadsheet's CSV often starts with a byte-order mark
        return list(csv.DictReader(f))


# ---- Waterhead, from its published export (docs/WATERHEAD-WET-CONTRACT-v1.md) ----

# The spot whose page links the samples (the export's `spots`), placed by OpenStreetMap: the sheet has no site column.
WATERHEAD_POINT = (54.41897, -2.96235)
WATERHEAD_LAB = {"2025": "Simplex Health", "2026": "not_stated"}   # the WET technical report, p. 6; 2026 is unconfirmed
CONSENT = "Tim Boden email 25 Oct 2026 (swimsignal-private/tim-boden-aafaf/)"


def waterhead_rows(doc: dict) -> list[dict]:
    """Two rows a sample, E. coli then enterococci, every count as the export publishes it."""
    received = doc["sources"]["received"]
    out = []
    for s in doc["samples"]:
        for det, k in (("ecoli", "ecoli"), ("intestinal_enterococci", "ie")):
            out.append({
                "partner_id": "aafaf", "sample_id": f"wet-{s['date']}", "site_name": doc["site"]["name"],
                "site_lat": f"{WATERHEAD_POINT[0]:.5f}", "site_lon": f"{WATERHEAD_POINT[1]:.5f}",
                "site_confirmed": "yes" if doc["site"]["confirmed"] else "no",
                "sampled_on": s["date"], "sampled_time": "", "timezone": "",
                "determinand": det, "result": str(s[k]), "qualifier": "", "unit": "cfu/100ml",
                "method_type": "not_stated", "method": "", "lower_limit": "", "upper_limit": "", "limits_written": "not_stated",
                "lab": WATERHEAD_LAB[s["date"][:4]], "lab_accredited": "not_stated",
                "sampler": "Ambleside Action for a Future (WET project)",
                "licence": "public-domain", "attribution": doc["attribution"],
                "publish_consent": "yes", "publish_consent_on": received,
                "test_use": "exploratory", "test_consent_on": received, "consent_ref": CONSENT, "received_on": received,
                "notes": ("SwimSignal: recorded as 0; what a 0 means is not yet confirmed (WET contract, open questions)."
                          if s[k] == 0 else ""),
            })
    return out


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def check_waterhead(doc: dict, committed: str) -> list[str]:
    """Differences between the export, a fresh mapping and the committed file. Empty when they agree."""
    rows = waterhead_rows(doc)
    err = [] if to_csv(rows) == committed else [f"{WATERHEAD.name} is not what the export gives: run `partner_samples.py waterhead`"]
    got = {(r["sampled_on"], r["determinand"]): r["result"] for r in csv.DictReader(io.StringIO(committed))}
    for s in doc["samples"]:
        for det, k in (("ecoli", "ecoli"), ("intestinal_enterococci", "ie")):
            if got.get((s["date"], det)) != str(s[k]):
                err.append(f"{s['date']} {det}: file has {got.get((s['date'], det))!r}, the export {s[k]}")
    if len(got) != 2 * len(doc["samples"]):
        err.append(f"{len(got)} results, not {2 * len(doc['samples'])}")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["check", "waterhead", "check-waterhead"])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--out", type=Path, default=WATERHEAD)
    a = ap.parse_args()
    if a.step == "waterhead":
        text = to_csv(waterhead_rows(json.loads(WET.read_text())))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
        print(f"wrote {a.out}: {text.count(chr(10)) - 1} results")
    elif a.step == "check-waterhead":
        problems = check_waterhead(json.loads(WET.read_text()), WATERHEAD.read_text())
        print("\n".join(problems) or f"{WATERHEAD.name} matches the export")
        sys.exit(1 if problems else 0)
    else:
        if not a.paths:
            ap.error("check needs at least one file")
        bad = False
        for p in a.paths:
            errors, warnings = check_rows(read(p))
            print(f"{p}: {len(errors)} errors, {len(warnings)} warnings")
            for x in errors:
                print(f"  error   {x}")
            # A warning on every row (no time, an approximate point) is said once, with how many rows it is on.
            by = {}
            for x in warnings:
                row, msg = x.split(": ", 1)
                by.setdefault(msg, []).append(row.removeprefix("row "))
            for msg, rows in by.items():
                print(f"  warning {msg} (row{'s' if len(rows) > 1 else ''} {', '.join(rows) if len(rows) <= 5 else f'{rows[0]} to {rows[-1]}, {len(rows)} rows'})")
            bad = bad or bool(errors)
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
