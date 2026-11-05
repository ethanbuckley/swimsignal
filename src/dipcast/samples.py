"""Lab results an organisation sends: water samples it had taken at a spot and tested by a lab, kept
apart from every forecast and estimate (samples/README.md has the format and how to add them).

It serves the paid pilots: where an organiser already pays for lab tests, its results are attached to
the right spot and sampling time, kept distinct from predictions, with who supplied them, and
permission to use them for testing the forecast is agreed separately from permission to publish them.

One row a sample, in two places:

- **private**: every row, with both permissions, in ``~/Documents/GitHub/swimsignal-private/samples/``
  (or DIPCAST_SAMPLES_PRIVATE), one CSV a supplier. Never in this repository.
- **public**: ``samples/<supplier>.csv`` here, the rows with ``publish = true`` and only the columns
  the page shows. scripts/add_samples.py writes it from the private file, whole, every time, so a
  permission taken back in the private file takes the row out of the public one on the next run.

Version 2 (31 Oct 2026, docs/PARTNER-SAMPLES-CONTRACT-v1.md) adds what a sampling partner's results need, as columns
after the first thirteen, every one optional so a version 1 file still reads: the sampling point where it is not the
spot's pin, whether the time is known, each count's basis (cfu or MPN) and the method's limits, how out-of-limit values
are written, the sampler as a role, the licence and credit, and when each permission was agreed, with the kind of test
use (holdout or exploratory). A holdout result must have been agreed before it was sampled.

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
V1_COLUMNS = ("spot_id", "sampled_at", "timezone", "ecoli_per_100ml", "enterococci_per_100ml", "lab", "ukas_accredited",
              "method", "lab_ref", "supplier", "received", "publish", "evaluate")
# Version 2's columns, after version 1's (docs/PARTNER-SAMPLES-CONTRACT-v1.md has each). Blank is always allowed and
# means "not stated"; the checks below say where a value needs another.
V2_COLUMNS = ("time_known", "site_name", "site_lat", "site_lon", "site_confirmed", "ecoli_basis", "enterococci_basis",
              "ecoli_lower_limit", "ecoli_upper_limit", "enterococci_lower_limit", "enterococci_upper_limit", "limits_written",
              "sampler", "licence", "attribution", "publish_agreed", "evaluate_use", "evaluate_agreed")
COLUMNS = V1_COLUMNS + V2_COLUMNS
# Kept private as well: who took it (a role, but still the partner's business) and the dates and kind of each agreement.
PRIVATE_ONLY = ("lab_ref", "publish", "evaluate", "sampler", "publish_agreed", "evaluate_use", "evaluate_agreed")
V1_PUBLIC = tuple(c for c in V1_COLUMNS if c not in PRIVATE_ONLY)
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
BASES = ("cfu", "mpn")                       # colony-forming units (a plate count) or most probable number
LIMITS_WRITTEN = ("qualifier", "zero")       # below a limit written as <10, or as 0 (then the lower limit is needed)
LICENCES = ("public-domain", "CC-BY-4.0", "OGL-3.0")
CREDIT = ("CC-BY-4.0", "OGL-3.0")            # licences that need an attribution
USES = ("holdout", "exploratory")            # evaluate_use; blank with evaluate = true is exploratory
LAT, LON = (49.8, 61.0), (-10.7, 2.0)        # Great Britain and Ireland, loosely: a swapped or unsigned position falls outside


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


def _when_day(v, zone: str) -> datetime:
    """A sampling day with no time (time_known = no): noon on that day in its zone, for ordering only. Such a sample can
    be matched to a forecast day, never to the forecast live at the moment it was taken."""
    s = str(v or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", s):
        raise SampleError(f"with time_known no, sampled_at is the day alone, 2026-10-17 or 17/10/2026, not {v!r}")
    return datetime.combine(_day(s, "sampled_at"), datetime.min.time()).replace(hour=12, tzinfo=ZoneInfo(zone))


def _limit(v, what: str) -> float | None:
    s = str(v or "").strip().replace(",", "")
    if not s:
        return None
    try:
        n = float(s)
    except ValueError:
        raise SampleError(f"{what} must be a number per 100 ml, or blank, not {v!r}") from None
    if not 0 <= n <= MAX_COUNT:
        raise SampleError(f"{what} {n:g} is not a limit per 100 ml")
    return n


def _choice(v, what: str, ok: tuple[str, ...]) -> str:
    s = str(v or "").strip()
    if s and s not in ok:
        raise SampleError(f"{what} must be {', '.join(ok)} or blank, not {v!r}")
    return s


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
    time_known = _choice(raw.get("time_known"), "time_known", ("yes", "no"))
    at = _when_day(raw.get("sampled_at"), zone) if time_known == "no" else _when(raw.get("sampled_at"), zone)
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
    row = {"spot_id": sid, "sampled_at": at.date().isoformat() if time_known == "no" else at.isoformat(timespec="minutes"), "timezone": zone,
           "ecoli_per_100ml": _fmt_count(ecoli), "enterococci_per_100ml": _fmt_count(ent),
           "lab": _text(raw.get("lab"), "lab"), "ukas_accredited": ukas, "method": _text(raw.get("method"), "method"),
           "supplier": supplier, "received": received.isoformat()}
    row |= _v2(raw, row, local_day, time_known, ecoli, ent, now)
    if not public:
        row |= {"lab_ref": _text(raw.get("lab_ref"), "lab_ref"), "publish": _flag(raw.get("publish"), "publish"),
                "evaluate": _flag(raw.get("evaluate"), "evaluate")}
        _agreements(raw, row, local_day, now)
    out = {c: row[c] for c in cols}
    out |= {"_at": at, "_ecoli": ecoli, "_ent": ent, "_time_known": time_known != "no"}
    return out


def _v2(raw: dict, row: dict, day: date, time_known: str, ecoli, ent, now: datetime) -> dict:
    """Version 2's public columns, checked: the point, each count's basis and limits, how limits are written, licence."""
    out = {"time_known": time_known, "site_name": _text(raw.get("site_name"), "site_name")}
    lat, lon = (str(raw.get(k) or "").strip() for k in ("site_lat", "site_lon"))
    if lat or lon:
        try:
            y, x = float(lat), float(lon)
        except ValueError:
            raise SampleError("site_lat and site_lon must both be decimal degrees (WGS84), or both blank") from None
        if not (LAT[0] <= y <= LAT[1] and LON[0] <= x <= LON[1]):
            raise SampleError(f"site_lat {lat}, site_lon {lon} is not in Great Britain or Ireland: check the order and the minus sign")
        lat, lon = f"{y:.5f}", f"{x:.5f}"
    out |= {"site_lat": lat, "site_lon": lon, "site_confirmed": _choice(raw.get("site_confirmed"), "site_confirmed", ("yes", "no"))}
    written = _choice(raw.get("limits_written"), "limits_written", LIMITS_WRITTEN)
    for name, c in (("ecoli", ecoli), ("enterococci", ent)):
        lo, hi = _limit(raw.get(f"{name}_lower_limit"), f"{name}_lower_limit"), _limit(raw.get(f"{name}_upper_limit"), f"{name}_upper_limit")
        if lo is not None and hi is not None and lo > hi:
            raise SampleError(f"{name}_lower_limit {lo:g} is above {name}_upper_limit {hi:g}")
        if c is not None and c[0] == 0 and not c[1]:
            if written == "qualifier" and (lo or 0) > 0:
                raise SampleError(f"{name} is 0 where below-limit values are written with <: write <{lo:g}")
            if written == "zero" and lo is None:
                raise SampleError(f"limits_written zero needs {name}_lower_limit, the limit a 0 stands for")
        out |= {f"{name}_basis": _choice(raw.get(f"{name}_basis"), f"{name}_basis", BASES),
                f"{name}_lower_limit": "" if lo is None else f"{_num(lo)}", f"{name}_upper_limit": "" if hi is None else f"{_num(hi)}"}
    licence = _choice(raw.get("licence"), "licence", LICENCES)
    attribution = _text(raw.get("attribution"), "attribution")
    if licence in CREDIT and not attribution:
        raise SampleError(f"licence {licence} needs an attribution, the credit shown beside the result")
    return out | {"limits_written": written, "sampler": _text(raw.get("sampler"), "sampler"), "licence": licence, "attribution": attribution}


def _agreements(raw: dict, row: dict, day: date, now: datetime) -> None:
    """When each permission was agreed, and the kind of test use. A holdout needs an agreement made before the sample
    was taken, and a time: nobody could then have chosen it after seeing the result, and it can be matched to the
    forecast live when it was taken (docs/PARTNER-SAMPLES-CONTRACT-v1.md says why)."""
    today = now.astimezone(UK).date()
    for k in ("publish_agreed", "evaluate_agreed"):
        v = str(raw.get(k) or "").strip()
        if v and (d := _day(v, k)) > today:
            raise SampleError(f"{k} {d} is in the future")
        row[k] = _day(v, k).isoformat() if v else ""
    use = _choice(raw.get("evaluate_use"), "evaluate_use", USES)
    if use and row["evaluate"] != "true":
        raise SampleError(f"evaluate_use {use} with evaluate false: the result is not to be used in a test")
    if use == "holdout":
        if not row["evaluate_agreed"]:
            raise SampleError("a holdout needs evaluate_agreed, the day the test use was agreed in writing")
        if date.fromisoformat(row["evaluate_agreed"]) >= day:
            raise SampleError(f"holdout agreed {row['evaluate_agreed']}, on or after the sample ({day}): only an agreement made "
                              "before sampling keeps a result held out; use exploratory")
        if row["time_known"] == "no":
            raise SampleError("a holdout needs the sampling time, to match it to the forecast live when it was taken")
    row["evaluate_use"] = use


def notes(row: dict) -> list[str]:
    """What a checked row leaves unknown, for the person adding it to read with the sender: none of these stops a row."""
    out = []
    for name, c in (("E. coli", row["_ecoli"]), ("enterococci", row["_ent"])):
        key = "ecoli" if name == "E. coli" else "enterococci"
        if c is not None and c[0] == 0 and not c[1] and not row["limits_written"]:
            out.append(f"{name} 0 with limits_written blank: it may be a below-limit result, not none")
        lo, hi = row[f"{key}_lower_limit"], row[f"{key}_upper_limit"]
        if c is not None and ((c[1] == "<" and lo and float(lo) != c[0]) or (c[1] == ">" and hi and float(hi) != c[0])):
            out.append(f"{name} {c[1]}{_num(c[0])} is not the stated limit")
    if row["site_confirmed"] == "no":
        out.append("site_confirmed no: the point is approximate")
    if not row["_time_known"]:
        out.append("no sampling time: it can be matched to a forecast day, not to the forecast live when it was taken")
    if row.get("publish") == "true" and not row["licence"]:
        out.append("publish true with no licence: agree one before the result reaches the open data files")
    return out


def key(row: dict) -> tuple:
    """One sample: the same spot, time and supplier is the same sample entered twice."""
    return row["spot_id"], row["_at"], row["supplier"].lower()


def _read(path: Path, cols: tuple[str, ...]) -> list[dict]:
    """A file's rows. A version 1 file (the first thirteen columns, or the public ten) reads with the new columns blank."""
    old = V1_COLUMNS if cols == COLUMNS else V1_PUBLIC
    with path.open(newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        got = tuple(r.fieldnames or ())
        if got not in (cols, old):
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
    if not row["_time_known"]:
        out["time_known"] = False   # sampled_at is a day alone
    for name, c in (("ecoli", row["_ecoli"]), ("enterococci", row["_ent"])):
        if c is not None:
            out[name] = _num(c[0])
            if c[1]:
                out[f"{name}_qualifier"] = c[1]
            if row[f"{name}_basis"]:
                out[f"{name}_basis"] = row[f"{name}_basis"]
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
