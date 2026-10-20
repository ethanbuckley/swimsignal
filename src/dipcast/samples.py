"""Lab results an organisation sends: water samples it had taken at a spot and tested by a lab, kept
apart from every forecast and estimate (samples/README.md has the format and how to add them).

An outside review of 20 Oct 2026 asked for it for the paid pilots: where an organiser already pays
for lab tests, a way to attach its results to the right spot and sampling time, measured results kept
distinct from predictions, who supplied them kept with them, and permission to use them for testing
the forecast agreed separately from permission to publish them.

One row a sample, in two places:

- **private**: every row, with both permissions, in ``~/Documents/GitHub/swimsignal-private/samples/``
  (or DIPCAST_SAMPLES_PRIVATE), one CSV a supplier. Never in this repository.
- **public**: ``samples/<supplier>.csv`` here, the rows with ``publish = true`` and only the columns
  the page shows. scripts/add_samples.py writes it from the private file, whole, every time, so a
  permission taken back in the private file takes the row out of the public one on the next run.

The build reads only the public folder (attach_measured): each spot's samples from the last
WINDOW_DAYS, newest first, go on the spot in spots.json as ``measured``, and the spot's page draws them
in a tile of their own (src/dipcast/site/measured.js). They are not part of the level. A row that
breaks these rules is left out with a warning, and the forecasts still publish.
"""

from __future__ import annotations

import csv
import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dipcast import config

log = logging.getLogger(__name__)

PUBLIC = config.ROOT / "samples"
PRIVATE_ENV = "DIPCAST_SAMPLES_PRIVATE"
PRIVATE_DEFAULT = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "samples"
UK = ZoneInfo("Europe/London")

# The private file's columns, in order; the public file's are the same less the three that are not
# for publishing: the lab's own reference, which links a row to the report in the supplier's email,
# and the two permissions (every public row has publish = true; evaluate is not the page's business).
COLUMNS = ("spot_id", "sampled_at", "timezone", "ecoli_per_100ml", "enterococci_per_100ml", "lab", "ukas_accredited",
           "method", "lab_ref", "supplier", "received", "publish", "evaluate")
PRIVATE_ONLY = ("lab_ref", "publish", "evaluate")
PUBLIC_COLUMNS = tuple(c for c in COLUMNS if c not in PRIVATE_ONLY)
# The zone a supplier's times are in: UK clock time, or GMT all year, as some lab systems record it.
# Anything else is refused rather than guessed ("BST" is not a zone: it is Europe/London in summer).
ZONES = ("Europe/London", "UTC", "GMT")
# The page shows a spot's samples from the last 30 days (measured.js keeps the same number). A count
# is for the moment it was taken and can change within hours after rain, so an old one says little
# about the water now; the EA's own sample counts in the level for 14 days only (levels.js,
# SAMPLE_DAYS). 30 rather than 14 so the latest of a monthly schedule, which British Triathlon's
# guidance suggests before an event (a month, two weeks and a week ahead), stays shown until the
# next. At most SHOW_MAX a spot, so spots.json stays small whatever a supplier sends.
WINDOW_DAYS = 30
SHOW_MAX = 10
# A sample received more than this long after it was taken is refused unless asked for (allow_old):
# a lab reports within days, so a gap of months is more often a wrong year or a day and month swapped.
MAX_DELAY_DAYS = 120
EARLIEST = date(2020, 1, 1)
MAX_COUNT = 10_000_000   # per 100 ml; more is a typing slip (an extra nought, or the wrong unit)
MAX_TEXT = 80
SPOT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")   # the site's rule for a spot's id, as guides.py's
COUNT = re.compile(r"([<>])?\s*(\d[\d,]*(?:\.\d+)?)")
YES, NO = ("true", "yes", "y", "1"), ("false", "no", "n", "0", "")


class SampleError(ValueError):
    pass


def private_dir(given: str | Path | None = None) -> Path:
    """Where the full set is kept: given, else DIPCAST_SAMPLES_PRIVATE, else the private repository's
    samples/. Refused inside this repository, where it would be one `git add` from public."""
    p = Path(given or os.environ.get(PRIVATE_ENV) or PRIVATE_DEFAULT).expanduser().resolve()
    if p == config.ROOT.resolve() or config.ROOT.resolve() in p.parents:
        raise SampleError(f"{p} is inside the public repository; keep the full set outside it")
    return p


def slug(supplier: str) -> str:
    """A supplier's file name: 'Example Swim Club' -> 'example-swim-club'."""
    s = re.sub(r"[^a-z0-9]+", "-", supplier.lower()).strip("-")[:60].strip("-")
    if not s:
        raise SampleError(f"supplier {supplier!r} has no letters or digits to name its file by")
    return s


def _text(v, what: str, required: bool = False) -> str:
    v = " ".join(str(v or "").split())
    if required and not v:
        raise SampleError(f"{what} is missing")
    if len(v) > MAX_TEXT:
        raise SampleError(f"{what} is {len(v)} characters; keep it under {MAX_TEXT}")
    return v


def _flag(v, what: str) -> str:
    s = str(v or "").strip().lower()
    if s in YES:
        return "true"
    if s in NO:
        return "false"
    raise SampleError(f"{what} must be true or false, not {v!r}")


def _day(v, what: str) -> date:
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise SampleError(f"{what} must be a date written 2026-10-17 or 17/10/2026, not {v!r}")


def _when(v, zone: str) -> datetime:
    """The sampling time, as the supplier wrote it, in its zone. A UK clock time in the hour the clocks
    go back happens twice, and one in the hour they go forward never: both are refused, so the offset
    has to be written (2026-10-25 01:30+01:00) rather than guessed."""
    s = str(v or "").strip().replace("T", " ")
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}) (\d{1,2}:\d{2})(?::\d{2})?\s*([+-]\d{2}:?\d{2}|Z)?", s)
    if not m:
        raise SampleError(f"sampled_at must be a date and a time, 2026-10-17 08:30 or 17/10/2026 08:30, not {v!r}")
    day = _day(m[1], "sampled_at's date")
    try:
        hh, mm = (int(x) for x in m[2].split(":"))
        naive = datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm)
    except ValueError:
        raise SampleError(f"sampled_at's time {m[2]!r} is not a time of day") from None
    tz = ZoneInfo(zone)
    if m[3]:
        off = m[3].replace("Z", "+00:00")
        off = off if ":" in off else off[:3] + ":" + off[3:]
        t = datetime.fromisoformat(f"{naive.isoformat()}{off}")
        if t.utcoffset() not in {naive.replace(tzinfo=tz, fold=f).utcoffset() for f in (0, 1)}:
            raise SampleError(f"sampled_at's offset {m[3]} is not {zone}'s on {day}")
        return t
    a, b = naive.replace(tzinfo=tz, fold=0), naive.replace(tzinfo=tz, fold=1)
    if a.utcoffset() != b.utcoffset():
        if a.astimezone(ZoneInfo("UTC")).astimezone(tz).replace(tzinfo=None) != naive:
            raise SampleError(f"sampled_at {s} does not exist in {zone}: the clocks went forward over it")
        raise SampleError(f"sampled_at {s} is in the hour the clocks go back, so it happened twice: add the offset, "
                          "+01:00 for the first or +00:00 for the second")
    return a


def _count(v, what: str) -> tuple[float, str] | None:
    """'1200', '1,200', '<10', '> 24196': the count and its qualifier ('<', '>' or ''). None if blank."""
    s = str(v or "").strip()
    if not s:
        return None
    m = COUNT.fullmatch(s)
    if not m:
        raise SampleError(f"{what} must be a count per 100 ml, such as 1200, <10 or >24196, not {v!r}")
    n = float(m[2].replace(",", ""))
    if n > MAX_COUNT:
        raise SampleError(f"{what} is {n:,.0f} per 100 ml, over {MAX_COUNT:,}: check for an extra nought or another unit")
    if m[1] == "<" and n <= 0:
        raise SampleError(f"{what}: under {n:g} is not a count")
    return n, m[1] or ""


def _num(n: float) -> int | float:
    return int(n) if n == int(n) else round(n, 1)


def _fmt_count(c: tuple[float, str] | None) -> str:
    return "" if c is None else f"{c[1]}{_num(c[0])}"


def parse_row(raw: dict, spot_ids: set[str] | None, now: datetime | None = None, public: bool = False,
              allow_old: bool = False) -> dict:
    """One sample, checked: the row as it is written to a file (strings, in COLUMNS order, the time with
    its offset), with `_at` (the time, aware) and `_ecoli`, `_ent` (count and qualifier, or None).
    public: a row of a public file, which has no lab_ref and no permissions, and must be publishable.
    Raises SampleError."""
    now = now or datetime.now(UK)
    cols = PUBLIC_COLUMNS if public else COLUMNS
    extra = set(raw) - set(cols)
    if extra:
        raise SampleError(f"unknown column(s): {', '.join(sorted(map(str, extra)))}")
    sid = str(raw.get("spot_id") or "").strip()
    if not SPOT_ID.fullmatch(sid):
        raise SampleError(f"spot_id {sid!r} is not a spot id")
    if spot_ids is not None and sid not in spot_ids:
        raise SampleError(f"no spot has the id {sid!r} (spots.csv, spots-osm.csv)")
    zone = str(raw.get("timezone") or "").strip()
    if zone not in ZONES:
        raise SampleError(f"timezone must be one of {', '.join(ZONES)}, not {zone!r}")
    at = _when(raw.get("sampled_at"), zone)
    if at > now:
        raise SampleError(f"sampled_at {at.isoformat(timespec='minutes')} is in the future")
    local_day = at.astimezone(UK).date()
    if local_day < EARLIEST:
        raise SampleError(f"sampled_at {local_day} is before {EARLIEST}")
    ecoli = _count(raw.get("ecoli_per_100ml"), "ecoli_per_100ml")
    ent = _count(raw.get("enterococci_per_100ml"), "enterococci_per_100ml")
    if ecoli is None and ent is None:
        raise SampleError("neither ecoli_per_100ml nor enterococci_per_100ml is given")
    ukas = str(raw.get("ukas_accredited") or "").strip().lower()
    if ukas not in ("yes", "no", ""):
        raise SampleError(f"ukas_accredited must be yes, no or blank (what the supplier says), not {raw.get('ukas_accredited')!r}")
    supplier = _text(raw.get("supplier"), "supplier (the organisation that sent it)", required=True)
    received = _day(raw.get("received"), "received")
    if received > now.astimezone(UK).date():
        raise SampleError(f"received {received} is in the future")
    if received < local_day:
        raise SampleError(f"received {received} is before the sample was taken ({local_day})")
    if not allow_old and (received - local_day).days > MAX_DELAY_DAYS:
        raise SampleError(f"taken {local_day}, {(received - local_day).days} days before it was received: check the year "
                          "and the order of day and month (older results need --allow-old)")
    row = {"spot_id": sid, "sampled_at": at.isoformat(timespec="minutes"), "timezone": zone,
           "ecoli_per_100ml": _fmt_count(ecoli), "enterococci_per_100ml": _fmt_count(ent),
           "lab": _text(raw.get("lab"), "lab"), "ukas_accredited": ukas, "method": _text(raw.get("method"), "method"),
           "supplier": supplier, "received": received.isoformat()}
    if not public:
        row |= {"lab_ref": _text(raw.get("lab_ref"), "lab_ref"), "publish": _flag(raw.get("publish"), "publish"),
                "evaluate": _flag(raw.get("evaluate"), "evaluate")}
    out = {c: row[c] for c in cols}
    out |= {"_at": at, "_ecoli": ecoli, "_ent": ent}
    return out


def key(row: dict) -> tuple:
    """One sample: the same spot, time and supplier is the same sample entered twice."""
    return row["spot_id"], row["_at"], row["supplier"].lower()


def _read(path: Path, cols: tuple[str, ...]) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        if tuple(r.fieldnames or ()) != cols:
            raise SampleError(f"{path.name}: the columns must be {', '.join(cols)}")
        return list(r)


def _write(path: Path, rows: list[dict], cols: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["_at"], r["spot_id"]))
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_private(root: Path, spot_ids: set[str] | None = None, now: datetime | None = None) -> dict[str, list[dict]]:
    """Every supplier's rows in the private folder, checked, by file slug. A bad row stops it: this is
    the copy everything else is made from, so it is fixed by hand rather than skipped."""
    out = {}
    for path in sorted(root.glob("*.csv")) if root.is_dir() else []:
        rows = []
        for i, raw in enumerate(_read(path, COLUMNS), 2):
            try:
                rows.append(parse_row(raw, spot_ids, now, allow_old=True))
            except SampleError as e:
                raise SampleError(f"{path.name}, line {i}: {e}") from None
        out[path.stem] = rows
    return out


def write_supplier(private: Path, public: Path, name: str, rows: list[dict]) -> int:
    """A supplier's private file, every row, and its public file, the rows that may be published and
    only their public columns; no public file when none may be. Returns the public row count."""
    _write(private / f"{name}.csv", rows, COLUMNS)
    shown = [r for r in rows if r["publish"] == "true"]
    out = public / f"{name}.csv"
    if shown:
        _write(out, shown, PUBLIC_COLUMNS)
    elif out.exists():
        out.unlink()
    return len(shown)


def sync_public(private: Path, public: Path, spot_ids: set[str] | None = None, now: datetime | None = None) -> dict[str, int]:
    """Every public file written again from the private folder: after a permission is changed there by
    hand. Returns each supplier's public row count. A public file with no private one is left alone
    and reported, since the private folder may not be this machine's."""
    if not private.is_dir():
        raise SampleError(f"no private folder at {private}")
    counts = {name: write_supplier(private, public, name, rows) for name, rows in read_private(private, spot_ids, now).items()}
    for p in sorted(public.glob("*.csv")) if public.is_dir() else []:
        if p.stem not in counts:
            log.warning("%s has no private file in %s: left as it is", p.name, private)
    return counts


def _page(row: dict) -> dict:
    """A public row in the shape the page draws (measured.js)."""
    out = {"sampled_at": row["sampled_at"]}
    for name, c in (("ecoli", row["_ecoli"]), ("enterococci", row["_ent"])):
        if c is not None:
            out[name] = _num(c[0])
            if c[1]:
                out[f"{name}_qualifier"] = c[1]
    if row["lab"]:
        out["lab"] = row["lab"]
    if row["ukas_accredited"]:
        out["ukas"] = row["ukas_accredited"] == "yes"
    if row["method"]:
        out["method"] = row["method"]
    return out | {"supplier": row["supplier"], "received": row["received"]}


def load_published(spot_ids: set[str] | None = None, root: Path = PUBLIC, now: datetime | None = None) -> tuple[dict[str, list[dict]], list[str]]:
    """Every published sample in samples/, checked, by spot id, newest first; and a warning for each
    row or file left out."""
    by, warnings, seen = {}, [], set()
    for path in sorted(root.glob("*.csv")) if root.is_dir() else []:
        try:
            raws = _read(path, PUBLIC_COLUMNS)
        except (SampleError, csv.Error, UnicodeDecodeError) as e:
            warnings.append(f"samples {path.name} left out: {e}")
            continue
        for i, raw in enumerate(raws, 2):
            try:
                row = parse_row(raw, spot_ids, now, public=True, allow_old=True)
                if slug(row["supplier"]) != path.stem:
                    raise SampleError(f"the supplier {row['supplier']!r} is not this file's ({path.stem})")
                if key(row) in seen:
                    raise SampleError("the same spot, time and supplier as an earlier row")
            except SampleError as e:
                warnings.append(f"samples {path.name}, line {i} left out: {e}")
                continue
            seen.add(key(row))
            by.setdefault(row["spot_id"], []).append(row)
    for rows in by.values():
        rows.sort(key=lambda r: r["_at"], reverse=True)
    return by, warnings


def attach_measured(results: list[dict], root: Path = PUBLIC, now: datetime | None = None) -> dict:
    """Each spot's published samples from the last WINDOW_DAYS onto its forecast, as `measured`, newest
    first, at most SHOW_MAX. Returns how many spots and samples, and any warnings."""
    now = now or datetime.now(UK)
    by, warnings = load_published({r["id"] for r in results}, root, now)
    since = now - timedelta(days=WINDOW_DAYS)
    n_spots = n = 0
    for r in results:
        rows = [x for x in by.get(r["id"], []) if x["_at"] >= since][:SHOW_MAX]
        if rows:
            r["measured"] = [_page(x) for x in rows]
            n_spots, n = n_spots + 1, n + len(rows)
    for w in warnings:
        log.warning("%s", w)
    return {"spots": n_spots, "samples": n, "warnings": warnings}
