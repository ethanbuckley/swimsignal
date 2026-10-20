"""Pilot briefings, run by hand (docs/PILOT-SESSIONS.md; review ideas 4 and 5, 20 Oct 2026). A group
leader's planned session is one TOML file. Each briefing issued for it is kept as a fixed copy, apart
from the live pages, which go on updating: the data the pages were given, the PDFs, the pages as drawn,
the page code, what was missing, and the issue id. So the briefing a decision rested on can be found
again, and shown as it was.

    uv run python scripts/briefing.py issue   SESSION.toml
    uv run python scripts/briefing.py changes SESSION.toml
    uv run python scripts/briefing.py decide  SESSION.toml --decision go --by "Name" --note "Why"
    uv run python scripts/briefing.py find    --org "Name" [--date YYYY-MM-DD] [--issue ID] [--csv]

No accounts, no server: Ethan sends what `issue` and `changes` print, by his own email. Session files
hold the recipients, who are personal data, so they and the archive live outside this public
repository, under ~/Documents/GitHub/swimsignal-private/briefings/ unless SWIMSIGNAL_BRIEFINGS or
--root says otherwise. The script refuses to write inside this repository.

`issue` reads the live data once (spots.json, spots-lite.json, verification.json and alerts.json, all
from one build), keeps only the session's spots, and has headless Chrome draw the live decision record
(record.html) for each spot and the sites view (sites.html) for both, with the page's data requests
answered from the kept files. So the PDFs show exactly the archived data, and the live build can
move on meanwhile without changing them. The level words come from alerts.json, which the build writes
with the page's own rules (scripts/alerts.js), so the email never disagrees with the record.

Standard library only (Python 3.12+), plus Chrome, and pdftotext where it is installed (Homebrew
poppler) to check the PDFs' text.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
SITE = os.environ.get("SWIMSIGNAL_SITE", "https://swimsignal.co.uk/")
DEFAULT_ROOT = Path.home() / "Documents" / "GitHub" / "swimsignal-private" / "briefings"
CHROME = os.environ.get("SWIMSIGNAL_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
UK = ZoneInfo("Europe/London")
# What the pages read (record.js: spots.json and verification.json; sites.js: spots-lite.json) and the
# build's levels for each day in the page's words (alerts.json, scripts/alerts.js). All four come from
# one build, except verification.json, which the build writes from its own scoring run.
DATA_FILES = ("spots.json", "spots-lite.json", "verification.json", "alerts.json")
SAME_BUILD = ("spots.json", "spots-lite.json", "alerts.json")
STALE_MIN = 8 * 60      # the pages' "Stale" notice (organisers.js, STALE_MIN)
AHEAD = 4               # the forecast's five days: the day it is issued for and the four after it (organisers.js)
ORDER = {"low": 0, "moderate": 1, "high": 2, "very high": 3}   # levels.js, ORDER
DECISIONS = ("go", "change", "cancel")
# A page has drawn once record.js or sites.js has filled its container, from the data or with its error.
READY = "document.querySelector('#record, #sites') && document.querySelector('#record, #sites').children.length > 0"
# Recipient addresses that may appear in this repository: the reserved example domains (RFC 2606 and
# RFC 6761). Anything else is a real person's address and stays in the private folder.
RESERVED = re.compile(r"@(example\.(org|com|net)|[^@\s]+\.(example|invalid|test))$", re.IGNORECASE)

# The words a briefing opens with: what the forecast is and is not, then who decides. Close to the decision
# record's own opening (record.js, OP4 in docs/ORGANISER-PIVOT-2026-10.md, PR #275), so the email and the
# PDF say the same. For Ethan's approval, then a solicitor's, before any paid use. Watson v BBBC is why
# the customer is named as the decision maker in every briefing (the plan's section 8).
LIMITS = ("This is SwimSignal's pollution risk forecast for your planned session. It is one input to your own "
          "risk assessment. It is a forecast, not a water test: nothing was sampled at the water for it. It never "
          "says the water is safe or clean, and no level means that. It counts sewage from the monitored storm "
          "overflows upstream and the rain that makes them spill. It does not cover algae, leptospirosis (Weil's "
          "disease), runoff from farms and roads, outfalls no one monitors, or physical dangers. Missing data "
          "never means low risk: treat it as unknown.")
DECIDES = ("{org} makes the decision about this session, beside its own checks at the water, lab tests, the "
           "Environment Agency's advice and the water companies' own spill alerts. SwimSignal does not make it.")
# levels.js's words for a spot with no daily level (FOUND_NONE, OTHER_RISKS): never a risk level, so the
# briefing says so. tests/test_briefing.py checks they are still levels.js's.
FOUND_NONE = "No monitored overflow found upstream"
OTHER_RISKS = "Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water."
PLAIN = ("no overflows", "no river connection")   # levels.js, NO_OVERFLOWS and NO_RIVER


class BriefingError(Exception):
    """A problem Ethan has to fix before anything is sent: said in one plain message."""


# ------------------------------------------------------------------ the session file
@dataclass
class Session:
    path: Path
    organisation: str
    day: date
    time: str                 # "HH:MM", UK time
    main: str
    backup: str | None
    decision_maker: str
    recipients: list[dict]
    notes: str = ""
    raw: bytes = b""

    @property
    def spots(self) -> list[tuple[str, str]]:
        return [("main", self.main)] + ([("backup", self.backup)] if self.backup else [])

    @property
    def key(self) -> str:     # the session's folder: its date and start time
        return f"{self.day.isoformat()}T{self.time.replace(':', '')}"

    @property
    def org_slug(self) -> str:
        return slug(self.organisation)


FIELDS = {"organisation", "date", "time", "main", "backup", "decision_maker", "recipients", "notes"}


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "unnamed"


def load_session(path: Path) -> Session:
    """One planned session from its TOML file, every problem listed at once."""
    raw = Path(path).read_bytes()
    try:
        d = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise BriefingError(f"{path}: not valid TOML: {e}") from e
    bad = []
    for k in sorted(set(d) - FIELDS):
        bad.append(f"unknown field {k!r} (the fields are {', '.join(sorted(FIELDS))})")
    for k in ("organisation", "main", "decision_maker"):
        if not isinstance(d.get(k), str) or not d.get(k, "").strip():
            bad.append(f"{k} is missing")
    if not isinstance(d.get("date"), date) or isinstance(d.get("date"), datetime):
        bad.append("date must be a TOML date, like date = 2026-10-24 (no quotes)")
    if not isinstance(d.get("time"), str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", d.get("time", "")):
        bad.append('time must be the start time in UK time, like time = "09:30"')
    backup = d.get("backup") or None
    if backup is not None and not isinstance(backup, str):
        bad.append("backup must be a spot id")
    if backup and backup == d.get("main"):
        bad.append("backup is the same spot as main")
    rec = d.get("recipients")
    if not isinstance(rec, list) or not rec:
        bad.append("recipients is missing: add at least one [[recipients]] with a name and an email")
        rec = []
    for i, r in enumerate(rec, 1):
        if not isinstance(r, dict) or not str(r.get("name", "")).strip():
            bad.append(f"recipient {i} has no name")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(r.get("email", ""))):
            bad.append(f"recipient {i} ({r.get('name')}) has no valid email")
    if bad:
        raise BriefingError(f"{path}:\n  - " + "\n  - ".join(bad))
    return Session(path=Path(path), organisation=d["organisation"].strip(), day=d["date"], time=d["time"],
                   main=d["main"].strip(), backup=backup.strip() if backup else None,
                   decision_maker=d["decision_maker"].strip(), recipients=rec, notes=str(d.get("notes", "")).strip(), raw=raw)


# ------------------------------------------------------------------ where the private files go
def inside(p: Path, parent: Path) -> bool:
    try:
        p.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def public_repo(p: Path) -> Path | None:
    """The public SwimSignal checkout that p is inside, if any: this one, or another clone of it (the
    main checkout holds the worktrees). swimsignal-private is a different repository and is allowed."""
    if inside(p, REPO):
        return REPO
    q = p
    while not q.exists():
        q = q.parent
    try:
        top = subprocess.run(["git", "-C", str(q), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10, check=False).stdout.strip()
        url = subprocess.run(["git", "-C", top, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=10, check=False).stdout.strip() if top else ""
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(top) if re.search(r"[/:]ethanbuckley/(swimsignal|dipcast)(\.git)?/?$", url) else None


def guard(root: Path) -> Path:
    """The archive folder, refused where it is inside the public repository."""
    repo = public_repo(root)
    if repo:
        raise BriefingError(f"{root} is inside the public repository {repo}. Briefings hold recipients' names and "
                            f"addresses: keep them in swimsignal-private (the default, {DEFAULT_ROOT}).")
    return root


def archive_root(arg: str | None) -> Path:
    return guard(Path(arg or os.environ.get("SWIMSIGNAL_BRIEFINGS") or DEFAULT_ROOT).expanduser())


def session_dir(root: Path, s: Session) -> Path:
    return root / "issued" / s.org_slug / s.key


# ------------------------------------------------------------------ the live data
def issue_id(doc: dict) -> str:
    """The build's commit and the forecast's issue time in UTC, to the minute: 3ed1b5a-20261020T1216Z, as
    the record and the sites view print it (PR #275, printed.js, issueId). The commit is spots.json's
    `commit`, else the code part of a spot's model version ("code=0.1.0+3ed1b5a"), from files written
    before `commit` was, else "nogit"."""
    return f"{commit_of(doc)[0]}" + (f"-{t:%Y%m%dT%H%MZ}" if (t := parse_time(doc.get("generated_at"))) else "")


def commit_of(doc: dict) -> tuple[str, str]:
    if doc.get("commit"):
        return str(doc["commit"]), "spots.json commit"
    for s in doc.get("spots") or []:
        m = re.search(r"code=[^;+]*\+([^;]+)", str(((s or {}).get("assumptions") or {}).get("version") or ""))
        if m:
            return m.group(1), "model version"
    return "nogit", "none"


def parse_time(t) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(t).replace(" ", "T"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)


def utc(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def uk(t: datetime | str | None, fmt: str = "%-d %b %Y, %H:%M") -> str:
    d = parse_time(t) if not isinstance(t, datetime) else t
    return d.astimezone(UK).strftime(fmt) if d else "unknown"


def long_day(iso: str | date) -> str:
    d = date.fromisoformat(iso) if isinstance(iso, str) else iso
    return f"{d:%A} {d.day} {d:%B} {d.year}"


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "swimsignal-briefing/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


@dataclass
class Live:
    raw: dict[str, bytes]
    docs: dict[str, dict]
    urls: dict[str, str]
    fetched_at: str


def fetch_live(site: str, get=None, names=DATA_FILES, tries: int = 3, wait: float = 20.0) -> Live:
    """The live files, read once each. They must all come from one build (generated_at): a deploy
    replaces them one by one, so a read during one can mix two builds. Then wait and read them all
    again; after `tries`, stop. The query string is new each time, so no cache answers with an older copy."""
    get = get or http_get
    for attempt in range(1, tries + 1):
        stamp = str(int(time.time()))
        urls = {n: f"{site}data/{n}?briefing={stamp}" for n in names}
        raw = {n: get(u) for n, u in urls.items()}
        try:
            docs = {n: json.loads(b) for n, b in raw.items()}
        except json.JSONDecodeError as e:
            raise BriefingError(f"A live data file is not JSON ({e}). Try again in a few minutes.") from e
        gens = {n: docs[n].get("generated_at") for n in names if n in SAME_BUILD}
        if len(set(gens.values())) == 1:
            return Live(raw, docs, urls, utc(datetime.now(UTC)))
        if attempt < tries:
            print(f"The live files are from different builds ({gens}): a deploy is under way. Reading again in {wait:.0f} s.", file=sys.stderr)
            time.sleep(wait)
    raise BriefingError(f"The live build changed while its files were read, {tries} times running: {gens}. Nothing was issued. Try again in a few minutes.")


def slim(live: Live, ids: list[str]) -> dict[str, bytes]:
    """The files the pages are given and the archive keeps: each build file with only the session's
    spots, and verification.json whole (the record's accuracy figures)."""
    out = {}
    for n in DATA_FILES:
        doc = live.docs[n]
        if n == "alerts.json":
            doc = {**doc, "spots": {i: doc["spots"][i] for i in ids if i in doc.get("spots", {})}}
        elif n != "verification.json":
            by = {s.get("id"): s for s in doc.get("spots") or []}
            doc = {**doc, "spots": [by[i] for i in ids if i in by]}
        out[n] = live.raw[n] if n == "verification.json" else json.dumps(doc, ensure_ascii=False).encode()
    return out


# ------------------------------------------------------------------ a spot on the session's day
@dataclass
class Snapshot:
    """One build's data for some spots: spots.json's records and alerts.json's levels."""
    spots_doc: dict
    alerts_doc: dict

    @property
    def generated_at(self) -> str:
        return str(self.spots_doc.get("generated_at"))

    @property
    def issue_id(self) -> str:
        return issue_id(self.spots_doc)

    def spot(self, sid: str) -> dict | None:
        return next((s for s in self.spots_doc.get("spots") or [] if s.get("id") == sid), None)

    @classmethod
    def load(cls, path: Path) -> Snapshot:
        """From an archive folder (its data/), or one JSON file keyed by file name (the test fixtures)."""
        path = Path(path)
        if path.is_dir():
            return cls(json.loads((path / "data" / "spots.json").read_bytes()), json.loads((path / "data" / "alerts.json").read_bytes()))
        d = json.loads(path.read_bytes())
        return cls(d["spots.json"], d["alerts.json"])


def build_day(snap: Snapshot) -> str:
    return snap.generated_at[:10]   # the forecast's own day, as the pages take it (levels.js, setToday)


def when(snap: Snapshot, iso: str) -> str:
    """'in', 'past' or 'later', as the decision record judges a day (organisers.js, when)."""
    t = date.fromisoformat(build_day(snap))
    d = date.fromisoformat(iso)
    return "past" if d < t else "later" if d > t + timedelta(days=AHEAD) else "in"


def day_words(snap: Snapshot, sid: str, iso: str) -> tuple[str | None, str]:
    """The level and headline for one spot and day, as the page gives them (alerts.json: levels.js's
    dayLevel and dayHeadline). A spot with no daily forecast has its own level on every day."""
    a = (snap.alerts_doc.get("spots") or {}).get(sid)
    if a is None:
        return None, "Not in this forecast"
    if "days" not in a:
        return a.get("level"), a.get("headline") or ""
    dates = snap.alerts_doc.get("dates") or []
    if iso not in dates:
        return None, "Not in this forecast's five days"
    x = a["days"][dates.index(iso)]
    if not x:
        return None, "No forecast for this day"
    return x[0], snap.alerts_doc["words"][x[1]]


def rank(level: str | None) -> int:
    return ORDER.get(level or "", -1)


def daily(s: dict) -> bool:
    """A forecast that changes from day to day (levels.js, daily)."""
    return not s.get("error") and ((s.get("upstream_summary") or {}).get("overflows") or 0) > 0


def missing(s: dict, iso: str | None = None) -> list[dict]:
    """What a spot's forecast could not see when it was made, each as {key, say}: the overflows with no
    live feed, offline, on a feed that was down or not updating, the days with no forecast, rain missing on
    the session day, overflows in Wales, flood alerts not checked, the EA's short-notice advice against
    bathing (never readable: levels.js, eaUnchecked) and a stale river level. Counted as evidence.js counts them
    (evidenceOverflows). The key stays the same from build to build, so `changes` can compare."""
    out = []
    def add(key, say):
        out.append({"key": key, "say": say})
    us, n = s.get("upstream_summary") or {}, s.get("now") or {}
    total = us.get("overflows") or 0
    if str(s.get("error") or "").startswith("forecast failed"):
        add("forecast_failed", "No forecast for this spot in this update: it failed.")
    if total and daily(s):
        nf = n.get("no_feed_upstream") if isinstance(n.get("no_feed_upstream"), int) else us.get("without_live_feed")
        mon = min(total, n.get("monitored_upstream", total))
        st, fd = n.get("stale_upstream") or 0, n.get("feed_down_upstream") or 0
        offline = max(0, total - mon - st - fd - (nf or 0))
        if nf:
            add("no_feed", f"{nf} of the {total} overflows upstream {'has' if nf == 1 else 'have'} no live feed SwimSignal reads, "
                "so whether they are spilling now is not known; their chance of a spill comes from the rain alone.")
        if offline:
            add("offline", f"{offline} of the {total} overflows upstream {'was' if offline == 1 else 'were'} offline: not reporting on a working feed.")
        for f in n.get("feed_down") or []:
            add(f"feed_down:{f.get('company')}", f"{f.get('company')}'s live feed was down: {f.get('overflows')} overflows upstream not reporting.")
        for f in n.get("feed_stale") or []:
            since = f" since {uk(f['since'])}" if f.get("since") else ""
            add(f"feed_stale:{f.get('company')}", f"{f.get('overflows')} overflows upstream on {f.get('company')}'s feed had not updated{since or ' (no update time given)'}.")
        for x in (s.get("days") or [])[:AHEAD + 1]:
            if x.get("risk") is None:
                add(f"day:{x['date']}", f"No forecast for {long_day(x['date'])}: the rain forecast for it had not arrived.")
            elif x["date"] == iso and (x.get("rain_missing_share") or 0) > 0:
                add(f"rain:{x['date']}", f"Part of the rain forecast upstream was missing for {long_day(x['date'])} "
                    f"({round(100 * x['rain_missing_share'])}% of it).")
    w = us.get("wales_share") or 0
    if w > 0:
        add("wales", f"Overflows in Wales are not counted: about {max(1, round(100 * min(1, w)))}% of the river within "
            f"{(s.get('assumptions') or {}).get('max_upstream_km', 60):g} km above this spot is in Wales.")
    if "flood_alerts" in s and s["flood_alerts"] is None:
        add("flood_unchecked", "Flood alerts were not checked: the Environment Agency did not answer.")
    cl = s.get("classification")
    if s.get("source") == "designated" and cl:
        add("ea_advice", "The Environment Agency's short-notice advice against bathing, given after pollution or algae, cannot be read by SwimSignal"
            + (f": see {cl['url']}" if str(cl.get("url", "")).startswith("https://") else "") + ".")
    rs = s.get("river_state") or {}
    if rs.get("stale"):
        add("river_level", f"The river level at {rs.get('station')} was {rs.get('age_hours')} h old (not part of the pollution level).")
    return out


def build_missing(doc: dict) -> list[str]:
    """What the whole build could not read: live feeds that were down, and its own warnings."""
    out = []
    feeds = (doc.get("build") or {}).get("live_feeds") or {}
    for c in feeds.get("down") or []:
        out.append(f"{c}'s live feed was down for the whole forecast.")
    for w in (doc.get("build") or {}).get("warnings") or []:
        out.append(str(w))
    return out


# ------------------------------------------------------------------ what changed between two builds
@dataclass
class Change:
    role: str
    spot: str
    kind: str     # up, down, reason, gone, discharging, missing_new, missing_gone, missing_changed, ea_sample, ea_algae, ea_rating, flood
    say: str


def compare(old: Snapshot, new: Snapshot, s: Session) -> list[Change]:
    """What changed for the session's day between the briefing (old) and a later build (new), spot by
    spot: the level and its reason, overflows discharging upstream, missing data, the EA's samples, algae
    checks and rating, and flood alerts. Nothing when the build is the same."""
    iso = s.day.isoformat()
    if old.generated_at == new.generated_at:
        return []
    out = []
    for role, sid in s.spots:
        o, n = old.spot(sid), new.spot(sid)
        def ch(kind, say, role=role, sid=sid):
            out.append(Change(role, sid, kind, say))
        if n is None:
            ch("gone", "No longer in the forecast: the spot may have been renamed or removed.")
            continue
        if o is None:
            o = {}
        (ol, oh), (nl, nh) = day_words(old, sid, iso), day_words(new, sid, iso)
        if (ol, oh) != (nl, nh):
            # Higher or lower only between two risk levels: "No monitored overflow found upstream" is not one.
            both = ol in ORDER and nl in ORDER
            kind = "up" if both and rank(nl) > rank(ol) else "down" if both and rank(nl) < rank(ol) else "reason"
            word = {"up": "Higher", "down": "Lower", "reason": "Changed"}[kind]
            ch(kind, f"{word}: {nh} (was: {oh}).")
        od, nd = (o.get("now") or {}).get("discharging_upstream"), (n.get("now") or {}).get("discharging_upstream")
        if od != nd and nd is not None:
            was = {c.get("site_id") for c in o.get("contributors") or [] if c.get("status") == 1}
            started = [c for c in n.get("contributors") or [] if c.get("status") == 1 and c.get("site_id") not in was]
            far = lambda km: "under 0.1 km upstream" if (km or 0) < 0.1 else f"{km:g} km upstream"   # noqa: E731
            names = "; ".join(f"{c.get('site_name')} ({c.get('company')}), {far(c.get('distance_km'))}" for c in started[:3])
            ch("discharging", f"Overflows discharging upstream when the forecast was made: {nd} (was {od if od is not None else 'not known'})."
               + (f" Started since the briefing: {names}." if names else ""))
        om = {m["key"]: m["say"] for m in missing(o, iso) if not m["key"].startswith("day:") or m["key"] == f"day:{iso}"}
        nm = {m["key"]: m["say"] for m in missing(n, iso) if not m["key"].startswith("day:") or m["key"] == f"day:{iso}"}
        for k in nm:
            if k not in om:
                ch("missing_new", f"Now missing: {nm[k]}")
            elif nm[k] != om[k]:
                ch("missing_changed", f"Now: {nm[k]} (was: {om[k]})")
        for k in om:
            if k not in nm:
                ch("missing_gone", f"No longer missing: {om[k]}")
        ols, nls = o.get("lab_sample") or {}, n.get("lab_sample") or {}
        if nls.get("taken_at") and nls.get("taken_at") != ols.get("taken_at"):
            ch("ea_sample", f"A new Environment Agency lab sample, taken {uk(nls['taken_at'], '%-d %B')}: "
               f"{nls.get('qualifier') or ''}{nls.get('ecoli')} E. coli per 100 ml.")
        oa, na = o.get("algae") or {}, n.get("algae") or {}
        if na.get("date") and na.get("date") != oa.get("date"):
            ch("ea_algae", f"A new Environment Agency algae check, on {long_day(na['date'])}: {na.get('phrase')}.")
        oc, nc = (o.get("classification") or {}), (n.get("classification") or {})
        if (oc.get("class"), oc.get("year")) != (nc.get("class"), nc.get("year")) and nc:
            ch("ea_rating", f"Environment Agency rating now {str(nc.get('class') or 'none').lower()} for {nc.get('year')} "
               f"(was {str(oc.get('class') or 'none').lower()} for {oc.get('year')}).")
        of = {(f.get("severity"), f.get("area")) for f in o.get("flood_alerts") or [] if f and f.get("severity")}
        nf = {(f.get("severity"), f.get("area")) for f in n.get("flood_alerts") or [] if f and f.get("severity")}
        for sev, area in sorted(nf - of):
            ch("flood", f"Now in force: {sev}, {area}. A separate hazard, not part of the pollution level.")
        for sev, area in sorted(of - nf):
            ch("flood", f"No longer in force: {sev}, {area}.")
    return out


# ------------------------------------------------------------------ the words Ethan sends
def spot_lines(snap: Snapshot, sid: str, iso: str, role: str) -> list[str]:
    s = snap.spot(sid) or {}
    lv, head = day_words(snap, sid, iso)
    out = [f"{role.capitalize()} spot: {s.get('name', sid)}", f"{long_day(iso)}: {head}."]
    if lv in PLAIN:   # "No monitored overflow found upstream": never a level (levels.js, plainLevel)
        out.append(f"This is not a risk level. {OTHER_RISKS}")
    elif lv not in ORDER:   # no forecast for the day, or the spot not covered
        out.append("There is no level for this day: treat it as unknown, never as low.")
    m = missing(s, iso)
    if m:
        out.append("Missing or unknown:")
        out += [f"- {x['say']}" for x in m]
    return out


def change_lines(changes: list[Change], snap: Snapshot, s: Session) -> list[str]:
    out = []
    for role, sid in s.spots:
        mine = [c for c in changes if c.spot == sid]
        name = (snap.spot(sid) or {}).get("name", sid)
        out.append(f"{role.capitalize()} spot, {name}: " + ("no change." if not mine else ""))
        out += [f"- {c.say}" for c in mine]
    return out


def record_url(site: str, sid: str, iso: str, org: str = "") -> str:
    # record.html#spot=<id>&day=YYYY-MM-DD, and &org=<name>, which PR #275 adds (main ignores it).
    q = {"spot": sid, "day": iso, **({"org": org} if org else {})}
    return f"{site}record.html#" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def sites_url(site: str, s: Session) -> str:
    # sites.html#spots=a,b&name=...&day=YYYY-MM-DD (lists.js, sitesHash; sites.js reads day=). The name is
    # cut at 40 characters, so the session's day and time come first. With day=, each row gives the level on
    # the session's day, by its date: without it the rows said "today" and "tomorrow", counted from the
    # issue, in a sheet read on the day itself (20 Oct 2026).
    name = f"{s.day:%a} {s.day.day} {s.day:%b} {s.time}, {s.organisation}"[:40].strip()
    ids = ",".join(urllib.parse.quote(i, safe="") for _, i in s.spots)
    return f"{site}sites.html#spots={ids}&name={urllib.parse.quote(name, safe='')}&day={s.day.isoformat()}"


def briefing_text(snap: Snapshot, s: Session, site: str, files: list[str], prev: dict | None, changes: list[Change]) -> str:
    iso = s.day.isoformat()
    lines = [f"Subject: SwimSignal briefing for {s.organisation}: {long_day(iso)}, {s.time}", "",
             LIMITS, "", DECIDES.format(org=s.organisation), "",
             f"Session: {long_day(iso)}, {s.time} (UK time).", f"Decision by: {s.decision_maker}."]
    if s.notes:
        lines.append(f"Notes: {s.notes}")
    for role, sid in s.spots:
        lines += [""] + spot_lines(snap, sid, iso, role)
    if build_missing(snap.spots_doc):
        lines += ["", "Missing for every spot:"] + [f"- {m}" for m in build_missing(snap.spots_doc)]
    if prev:
        lines += ["", f"Changes since the briefing of {uk(prev['issued_at'], '%A %-d %B, %H:%M')} (issue id {prev['issue_id']}):"]
        lines += change_lines(changes, snap, s) if changes else ["- None for this day."]
    lines += ["", (f"The forecast was issued {uk(snap.generated_at)} (UK time). Its issue id is {snap.issue_id}. "
                   "Quote it to have this briefing found again, as it was sent."),
              "This briefing is a fixed copy: it does not change. The live pages keep updating, several times a day:"]
    lines += [f"  {record_url(site, sid, iso, s.organisation)}" for _, sid in s.spots]
    lines += ["", ("Attached: " + ", ".join(files) + ". Each decision record lists what the forecast rests on, how old each "
                   "part was and where it came from, its accuracy so far, and lines for your decision."),
              "", "If you tell us what you decided, we will keep it with this briefing, so the two can be found together later.",
              "", "SwimSignal"]
    return "\n".join(lines) + "\n"


def changes_text(old_manifest: dict, new: Snapshot, s: Session, changes: list[Change], site: str) -> str:
    iso = s.day.isoformat()
    if not changes:
        return (f"No change for {s.organisation}'s session on {long_day(iso)}, {s.time}, since the briefing issued "
                f"{uk(old_manifest['issued_at'])} (issue id {old_manifest['issue_id']}).\n")
    lines = [f"Subject: SwimSignal: changes for {s.organisation}, {long_day(iso)}, {s.time}", "",
             LIMITS, "", DECIDES.format(org=s.organisation), "",
             (f"The forecast was updated {uk(new.generated_at)} (UK time, issue id {new.issue_id}). For {long_day(iso)}, "
              f"compared with the briefing of {uk(old_manifest['issued_at'], '%A %-d %B, %H:%M')} (issue id {old_manifest['issue_id']}):"), ""]
    lines += change_lines(changes, new, s)
    lines += ["", "No new fixed copy goes with this note. The live pages:"]
    lines += [f"  {record_url(site, sid, iso, s.organisation)}" for _, sid in s.spots]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ headless Chrome, over its DevTools protocol
class CDP:
    """A minimal client for Chrome's DevTools protocol on one page: a websocket (RFC 6455) in the
    standard library, JSON commands, and events handed to `on` handlers while a command waits."""

    def __init__(self, ws_url: str, timeout: float = 60):
        u = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.buf = bytearray()
        while b"\r\n\r\n" not in self.buf:
            self.buf += self._recv()
        head, _, rest = bytes(self.buf).partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n")[0] + b" ":
            raise BriefingError(f"Chrome refused the DevTools connection: {head[:200]!r}")
        self.buf = bytearray(rest)
        self.next_id, self.handlers, self.errors = 0, {}, []

    def _recv(self) -> bytes:
        b = self.sock.recv(1 << 20)
        if not b:
            raise ConnectionError("Chrome closed the DevTools connection")
        return b

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            self.buf += self._recv()
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def _frame(self, op: int, data: bytes) -> None:
        n, head = len(data), bytearray([0x80 | op])
        head += bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        masked = (int.from_bytes(data, "big") ^ int.from_bytes((mask * (n // 4 + 1))[:n], "big")).to_bytes(n, "big") if n else b""
        self.sock.sendall(bytes(head) + mask + masked)

    def _message(self) -> dict:
        parts = []
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            n = struct.unpack(">H", self._read(2))[0] if n == 126 else struct.unpack(">Q", self._read(8))[0] if n == 127 else n
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
            if op == 0x8:
                raise ConnectionError("Chrome closed the DevTools connection")
            if op == 0x9:
                self._frame(0xA, data)
                continue
            if op in (0x0, 0x1, 0x2):
                parts.append(data)
                if b1 & 0x80:
                    return json.loads(b"".join(parts))

    def send(self, method: str, params: dict | None = None) -> int:
        self.next_id += 1
        self._frame(0x1, json.dumps({"id": self.next_id, "method": method, "params": params or {}}).encode())
        return self.next_id

    def call(self, method: str, params: dict | None = None) -> dict:
        mid = self.send(method, params)
        while True:
            m = self._message()
            if m.get("id") == mid:
                if "error" in m:
                    raise BriefingError(f"Chrome: {method} failed: {m['error']}")
                return m.get("result") or {}
            if "method" in m and m["method"] in self.handlers:
                self.handlers[m["method"]](m.get("params") or {})
            elif "error" in m:   # a command sent from a handler, not waited for
                self.errors.append(m["error"])

    def evaluate(self, expr: str, await_promise: bool = False):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        if "exceptionDetails" in r:
            raise BriefingError(f"Chrome: the page script failed: {r['exceptionDetails'].get('text')}")
        return (r.get("result") or {}).get("value")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@dataclass
class Rendered:
    url: str
    dom: str
    text: str
    pdf: bytes
    served: dict[str, int] = field(default_factory=dict)     # data file -> times the page was given it
    blocked: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)      # data requests the archive could not answer
    page_files: dict[str, tuple[str, bytes]] = field(default_factory=dict)   # path -> (url, body)
    exceptions: list[str] = field(default_factory=list)
    level: str = ""          # the record's level line, .r-level
    expect: dict = field(default_factory=dict)   # the issue times as the browser formats them
    rows: dict = field(default_factory=dict)     # the sites view's rows drawn for a day: spot id -> (day, level)


class Chrome:
    """Headless Chrome with its own profile, for one `issue`; `render` draws one page from the archived data."""

    def __init__(self, binary: str = CHROME, port: int = 0):
        self.binary, self.port = binary, port

    def __enter__(self) -> Chrome:
        if not Path(self.binary).exists() and not shutil.which(self.binary):
            raise BriefingError(f"Chrome not found at {self.binary}. Set SWIMSIGNAL_CHROME to its path.")
        self.profile = tempfile.mkdtemp(prefix="swimsignal-briefing-")
        self.proc = subprocess.Popen([self.binary, "--headless=new", f"--remote-debugging-port={self.port}",
                                      f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
                                      "--hide-scrollbars", "--disable-extensions", "--disable-background-networking",
                                      "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Port 0: Chrome picks a free port and writes it in the profile (DevToolsActivePort). A port given
        # is not written there, so ask it.
        f, port, targets = Path(self.profile) / "DevToolsActivePort", self.port, None
        for _ in range(150):
            try:
                if not port and f.exists() and len(f.read_text().splitlines()) >= 2:
                    port = int(f.read_text().splitlines()[0])
                if port:
                    targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5).read())
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        if not targets:
            self.__exit__()
            raise BriefingError("Chrome did not start its DevTools server within 15 s.")
        page = next(t for t in targets if t.get("type") == "page")
        self.cdp = CDP(page["webSocketDebuggerUrl"])
        return self

    def __exit__(self, *exc) -> None:
        if getattr(self, "cdp", None):
            self.cdp.close()
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def render(self, url: str, data: dict[str, bytes], generated_at: str, ready: str, timeout: float = 45) -> Rendered:
        c = self.cdp
        out = Rendered(url=url, dom="", text="", pdf=b"")
        responses: dict[str, tuple[str, str]] = {}
        site = url.split("#")[0].rsplit("/", 1)[0] + "/"

        def paused(p):
            u = p["request"]["url"]
            path = urllib.parse.urlparse(u).path
            name = path.rsplit("/", 1)[-1]
            if "cloudflareinsights.com" in u:   # the page-view counter: a briefing is not a visit
                out.blocked.append(u)
                c.send("Fetch.failRequest", {"requestId": p["requestId"], "errorReason": "BlockedByClient"})
            elif "/data/" in path and name in data:
                out.served[name] = out.served.get(name, 0) + 1
                c.send("Fetch.fulfillRequest", {"requestId": p["requestId"], "responseCode": 200, "body": base64.b64encode(data[name]).decode(),
                                                "responseHeaders": [{"name": "Content-Type", "value": "application/json; charset=utf-8"},
                                                                    {"name": "Cache-Control", "value": "no-store"}]})
            else:   # data the archive does not keep: never let the live copy into a fixed briefing
                out.unexpected.append(u)
                c.send("Fetch.failRequest", {"requestId": p["requestId"], "errorReason": "BlockedByClient"})

        def response(p):
            r = p.get("response") or {}
            if p.get("type") in ("Document", "Script", "Stylesheet") and r.get("url", "").startswith(site) and "/data/" not in r.get("url", ""):
                responses[p["requestId"]] = (r["url"], p["type"])

        c.handlers = {"Fetch.requestPaused": paused, "Network.responseReceived": response,
                      "Runtime.exceptionThrown": lambda p: out.exceptions.append(str((p.get("exceptionDetails") or {}).get("text")))}
        c.call("Page.navigate", {"url": "about:blank"})
        for m, prm in (("Page.enable", {}), ("Runtime.enable", {}), ("Network.enable", {}),
                       ("Network.setCacheDisabled", {"cacheDisabled": True}),
                       ("Emulation.setTimezoneOverride", {"timezoneId": "Europe/London"}),
                       ("Fetch.enable", {"patterns": [{"urlPattern": "*/data/*"}, {"urlPattern": "*cloudflareinsights.com*"}]})):
            c.call(m, prm)
        c.call("Page.navigate", {"url": url})
        end = time.monotonic() + timeout
        while True:
            try:   # the page may be between documents, with no context to evaluate in yet
                if c.evaluate(f"(() => {{ try {{ return !!({ready}); }} catch (e) {{ return false; }} }})()"):
                    break
            except BriefingError:
                pass
            if time.monotonic() > end:
                raise BriefingError(f"{url} did not finish drawing within {timeout:.0f} s.")
            time.sleep(0.25)
        c.evaluate("document.fonts.ready.then(() => true)", await_promise=True)
        g = json.dumps(generated_at)
        # The issue time as each page writes it: record.js's `at` and sites.js's `issue`. Formatted by this
        # browser, so Chrome's own wording of a month ("Sept") cannot fail the check.
        out.expect = c.evaluate(f"({{ record: new Date({g}).toLocaleString('en-GB', {{ day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' }}),"
                                f" sites: new Date({g}).toLocaleString('en-GB', {{ weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' }}) }})")
        out.dom = "<!doctype html>\n" + c.evaluate("document.documentElement.outerHTML")
        out.text = c.evaluate("document.body.innerText")
        out.level = c.evaluate("(document.querySelector('#record .r-level') || {}).textContent || ''")
        out.rows = c.evaluate("Object.fromEntries([...document.querySelectorAll('#sites li.site[data-day]')]"
                              ".map(li => [li.dataset.spot, [li.dataset.day, li.dataset.level]]))") or {}
        pdf = c.call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True, "paperWidth": 8.27, "paperHeight": 11.69})
        out.pdf = base64.b64decode(pdf["data"])
        for rid, (u, _) in responses.items():
            try:
                b = c.call("Network.getResponseBody", {"requestId": rid})
            except BriefingError:
                continue
            body = base64.b64decode(b["body"]) if b.get("base64Encoded") else b["body"].encode()
            out.page_files[urllib.parse.urlparse(u).path.rsplit("/", 1)[-1] or "index.html"] = (u, body)
        c.call("Fetch.disable")
        c.handlers = {}
        return out


def pdf_text(pdf: Path) -> str | None:
    """The PDF's text with pdftotext (poppler), whitespace run together; None where it is not installed."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    t = subprocess.run([exe, "-enc", "UTF-8", str(pdf), "-"], capture_output=True, text=True, timeout=60, check=False).stdout
    return re.sub(r"-\s+", "-", re.sub(r"\s+", " ", t))


def check_page(r: Rendered, kind: str, iid: str, want_level: str | None, pdf: Path,
               day: str | None = None, want_rows: dict | None = None) -> dict:
    """That the page drew the archived build and nothing else, and the PDF says so: the issue time (and
    the issue id, where the page prints one, PR #275) in the page and in the PDF's text, every data
    request answered from the archive, and the record's level the same as alerts.json's. The sites view,
    given the session's day, must draw every spot on that day (want_rows: spot id -> alerts.json's level)
    at alerts.json's level."""
    fail = []
    need = "spots.json" if kind == "record" else "spots-lite.json"
    if not r.served.get(need):
        fail.append(f"the page never asked for {need}, so it cannot have drawn the archived data")
    if r.unexpected:
        fail.append(f"the page asked for data the archive does not keep: {', '.join(r.unexpected)}")
    t = r.expect.get(kind, "")
    text = re.sub(r"\s+", " ", r.text)
    if not t or t not in text:
        fail.append(f"the page does not show the forecast's issue time {t!r}")
    shows_id = "Issue id" in text or "issue id" in text
    if shows_id and iid not in re.sub(r"-\s+", "-", text):
        fail.append(f"the page shows an issue id, but not {iid}")
    if kind == "record" and want_level in ORDER and not r.level.lower().startswith(f"{want_level} risk"):
        fail.append(f"the record says {r.level!r}, alerts.json {want_level!r} risk: the two disagree")
    if kind == "sites" and day:
        for sid, want in (want_rows or {}).items():
            got_day, got = (r.rows.get(sid) or [None, None])[:2]
            if got_day != day:
                fail.append(f"the sites view does not give {sid}'s level on {day}, so its rows would say "
                            "'today' and 'tomorrow' (is sites.js with day= live yet?)")
            elif want in ORDER and got != want:
                fail.append(f"the sites view says {got!r} for {sid} on {day}, alerts.json {want!r}: the two disagree")
    pt = pdf_text(pdf)
    if pt is not None:
        if t not in pt:
            fail.append(f"the PDF's text does not show the issue time {t!r}")
        if shows_id and iid not in pt:
            fail.append(f"the PDF's text does not show the issue id {iid}")
    if fail:
        raise BriefingError(f"{r.url}: " + "; ".join(fail) + ". Nothing was issued.")
    return {"issue_time_shown": t, "issue_id_shown": shows_id, **({"day_shown": day} if kind == "sites" and day else {}),
            "pdf_text": "checked" if pt is not None else "not checked: pdftotext not found",
            "data_served": r.served, "blocked": len(r.blocked), "page_exceptions": r.exceptions}


# ------------------------------------------------------------------ the archive
def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def manifests(root: Path) -> list[tuple[Path, dict]]:
    out = []
    for m in sorted((root / "issued").glob("*/*/*/manifest.json")):
        try:
            out.append((m.parent, json.loads(m.read_text())))
        except (OSError, json.JSONDecodeError):
            out.append((m.parent, {"broken": True}))
    return out


def latest_issue(root: Path, s: Session) -> tuple[Path, dict] | None:
    d = session_dir(root, s)
    found = [(m.parent, json.loads(m.read_text())) for m in d.glob("*/manifest.json")]
    return max(found, key=lambda x: x[1]["issued_at"]) if found else None


def check_files(folder: Path, man: dict) -> list[str]:
    """The files that differ from the manifest: a fixed copy should never change."""
    bad = []
    for f in man.get("files") or []:
        p = folder / f["path"]
        if not p.exists():
            bad.append(f"{f['path']} is missing")
        elif sha256(p.read_bytes()) != f["sha256"]:
            bad.append(f"{f['path']} has changed")
    return bad


def issue(session_path: Path, root: Path, site: str = SITE, get=None, render=None, now: datetime | None = None,
          stale_ok: bool = False, port: int = 0) -> tuple[Path, str]:
    """Issue one briefing: read the live build once, keep the session's spots, draw the PDFs from the
    kept data, check them, and write the archive folder. Returns the folder and the email text."""
    guard(root)
    s = load_session(session_path)
    if public_repo(s.path) and any(not RESERVED.search(str(r.get("email", ""))) for r in s.recipients):
        raise BriefingError(f"{s.path} is inside the public repository and names real recipients. Move it to {DEFAULT_ROOT.parent}.")
    now = now or datetime.now(UTC)
    live = fetch_live(site, get)
    spots = live.docs["spots.json"]
    have = {x.get("id") for x in spots.get("spots") or []}
    gone = [sid for _, sid in s.spots if sid not in have]
    if gone:
        raise BriefingError(f"Not in the live forecast: {', '.join(gone)}. Check the spot ids in {s.path}.")
    data = slim(live, [sid for _, sid in s.spots])
    snap = Snapshot(json.loads(data["spots.json"]), json.loads(data["alerts.json"]))
    iso, iid = s.day.isoformat(), snap.issue_id
    w = when(snap, iso)
    if w == "past":
        raise BriefingError(f"{long_day(iso)} has passed: the live forecast starts on {long_day(build_day(snap))}.")
    if w == "later":
        first = date.fromisoformat(iso) - timedelta(days=AHEAD)
        raise BriefingError(f"The forecast for {long_day(iso)} first appears on {long_day(first)}. Issue the briefing then.")
    age = (now - parse_time(snap.generated_at)).total_seconds() / 60
    if age > STALE_MIN and not stale_ok:
        raise BriefingError(f"The live forecast is {age / 60:.1f} h old: the automatic update has not run. Its pages say "
                            "\"Stale\". Find out why first; --stale-ok issues it anyway, and the email must say it is stale.")
    sdir = session_dir(root, s)
    folder = sdir / iid
    if folder.exists():
        raise BriefingError(f"This session already has a briefing from this build ({iid}): {folder}. The forecast has not "
                            "been rebuilt since, so there is nothing new to issue. `changes` says when there is.")
    prev = latest_issue(root, s)
    changes = compare(Snapshot.load(prev[0]), snap, s) if prev else []

    work = sdir / f".{iid}.partial"
    shutil.rmtree(work, ignore_errors=True)
    (work / "data").mkdir(parents=True)
    (work / "page").mkdir()
    for n, b in data.items():
        (work / "data" / n).write_bytes(b)
    (work / "session.toml").write_bytes(s.raw)
    # Each page's PDF, and its DOM as drawn (page/ holds the files as served).
    pages = [("record", role, sid, record_url(site, sid, iso, s.organisation), f"swimsignal-record-{role}-{iid}.pdf", f"record-{role}.drawn.html")
             for role, sid in s.spots]
    pages.append(("sites", "both", None, sites_url(site, s), f"swimsignal-sites-{iid}.pdf", "sites.drawn.html"))
    checks, page_files = [], {}
    try:
        with contextlib.ExitStack() as stack:
            if render is None:
                chrome = stack.enter_context(Chrome(port=port))
                def render(url, d, g, kind, chrome=chrome):
                    return chrome.render(url, d, g, READY)
            for kind, role, sid, url, pdf_name, dom_name in pages:
                r = render(url, data, snap.generated_at, kind)
                (work / pdf_name).write_bytes(r.pdf)
                (work / dom_name).write_text(r.dom)
                want = day_words(snap, sid, iso)[0] if sid else None
                rows = {i: day_words(snap, i, iso)[0] for _, i in s.spots} if kind == "sites" else None
                checks.append({"kind": kind, "role": role, "spot": sid, "url": url, "pdf": pdf_name, "dom": dom_name,
                               **check_page(r, kind, iid, want, work / pdf_name, iso if kind == "sites" else None, rows)})
                page_files.update(r.page_files)
        for name, (url, body) in sorted(page_files.items()):
            (work / "page" / name).write_bytes(body)
        pdfs = [p[4] for p in pages]
        text = briefing_text(snap, s, site, pdfs, prev[1] if prev else None, changes)
        (work / "briefing.txt").write_text(text)
        man = {
            "format": 1, "issue_id": iid, "issued_at": utc(now),
            "forecast": {"generated_at": snap.generated_at, "version": spots.get("version"), "commit": spots.get("commit"),
                         "commit_from": commit_of(spots)[1], "age_min": round(age),
                         "model_versions": {sid: ((snap.spot(sid) or {}).get("assumptions") or {}).get("version") for _, sid in s.spots},
                         "verification_generated_at": (live.docs["verification.json"].get("live") or {}).get("generated_at")},
            "session": {"organisation": s.organisation, "org_slug": s.org_slug, "date": iso, "time": s.time, "main": s.main,
                        "backup": s.backup, "decision_maker": s.decision_maker, "file": "session.toml", "from": str(s.path)},
            "sources": [{"url": live.urls[n], "file": f"data/{n}", "fetched_at": live.fetched_at, "bytes": len(live.raw[n]),
                         "sha256": sha256(live.raw[n]), "generated_at": live.docs[n].get("generated_at") or (live.docs[n].get("live") or {}).get("generated_at"),
                         "kept": "whole" if n == "verification.json" else "the session's spots only"} for n in DATA_FILES],
            "spots": [{"role": role, "id": sid, "name": (snap.spot(sid) or {}).get("name"),
                       "day": dict(zip(("level", "headline"), day_words(snap, sid, iso)), date=iso),
                       "missing": missing(snap.spot(sid) or {}, iso)} for role, sid in s.spots],
            "build_missing": build_missing(spots),
            "pages": checks,
            "previous": {"issue_id": prev[1]["issue_id"], "issued_at": prev[1]["issued_at"]} if prev else None,
            "changes_since_previous": [c.__dict__ for c in changes] if prev else None,
        }
        files = sorted(p for p in work.rglob("*") if p.is_file())
        man["files"] = [{"path": str(p.relative_to(work)), "sha256": sha256(p.read_bytes()), "bytes": p.stat().st_size} for p in files]
        (work / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n")
        work.rename(folder)   # whole or not at all: a half-written briefing never sits beside the real ones
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return folder, text


def check_changes(session_path: Path, root: Path, site: str = SITE, get=None, now: datetime | None = None) -> tuple[list[Change], str]:
    """The live build against the session's latest briefing, for the session's day. Logged in checks.jsonl."""
    guard(root)
    s = load_session(session_path)
    prev = latest_issue(root, s)
    if not prev:
        raise BriefingError(f"No briefing has been issued for this session yet ({session_dir(root, s)}). Run `issue` first.")
    live = fetch_live(site, get, names=("spots.json", "alerts.json"))
    sp, al = live.docs["spots.json"], live.docs["alerts.json"]
    ids = [sid for _, sid in s.spots]
    new = Snapshot({**sp, "spots": [x for x in sp.get("spots") or [] if x.get("id") in ids]},
                   {**al, "spots": {i: al["spots"][i] for i in ids if i in al.get("spots", {})}})
    if when(new, s.day.isoformat()) == "past":
        raise BriefingError(f"{long_day(s.day)} has passed: the live forecast no longer covers it.")
    changes = compare(Snapshot.load(prev[0]), new, s)
    text = changes_text(prev[1], new, s, changes, site)
    log = session_dir(root, s) / "checks.jsonl"
    with log.open("a") as f:
        f.write(json.dumps({"checked_at": utc(now or datetime.now(UTC)),
                            "against": prev[1]["issue_id"], "live": new.issue_id, "changes": len(changes),
                            "kinds": sorted({c.kind for c in changes})}) + "\n")
    return changes, text


def decide(session_path: Path, root: Path, decision: str, by: str, note: str, iid: str | None = None, at: str | None = None,
           now: datetime | None = None) -> dict:
    """Record the customer's decision against the briefing it was made on (the latest, unless --issue says
    which). Appended to the session's decisions.jsonl; the briefing's own folder is never changed."""
    s = load_session(session_path)
    if decision not in DECISIONS:
        raise BriefingError(f"--decision must be one of {', '.join(DECISIONS)}")
    issued = sorted((json.loads(m.read_text()) for m in session_dir(root, s).glob("*/manifest.json")), key=lambda m: m["issued_at"])
    if not issued:
        raise BriefingError("No briefing has been issued for this session, so the decision cannot be tied to one. Run `issue` first.")
    pick = next((m for m in issued if m["issue_id"] == iid), None) if iid else issued[-1]
    if pick is None:
        raise BriefingError(f"No briefing {iid} for this session. Issued: {', '.join(m['issue_id'] for m in issued)}.")
    now = now or datetime.now(UTC)
    row = {"recorded_at": utc(now), "decided_at": at or None,
           "issue_id": pick["issue_id"], "issued_at": pick["issued_at"], "latest_issued": pick is issued[-1],
           "decision": decision, "by": by, "note": note}
    with (session_dir(root, s) / "decisions.jsonl").open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def find(root: Path, org: str | None = None, day: str | None = None, iid: str | None = None) -> list[dict]:
    """Every issued briefing that matches, oldest first, with the decisions made on it and whether its files
    are as issued."""
    out = []
    for folder, m in manifests(root):
        if m.get("broken"):
            out.append({"folder": str(folder), "broken": True})
            continue
        ss = m["session"]
        if org and org.lower() not in ss["organisation"].lower() and slug(org) != ss["org_slug"]:
            continue
        if day and ss["date"] != day:
            continue
        if iid and m["issue_id"] != iid:
            continue
        decisions = [d for d in jsonl(folder.parent / "decisions.jsonl") if d["issue_id"] == m["issue_id"]]
        out.append({"folder": str(folder), "manifest": m, "decisions": decisions, "altered": check_files(folder, m)})
    return sorted(out, key=lambda x: (x.get("manifest") or {}).get("issued_at", ""))


# ------------------------------------------------------------------ the command line
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help=f"the private folder for briefings (default: $SWIMSIGNAL_BRIEFINGS or {DEFAULT_ROOT})")
    ap.add_argument("--site", default=SITE, help="the live site (default: %(default)s)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("issue", help="issue a briefing for a session")
    p.add_argument("session", type=Path)
    p.add_argument("--stale-ok", action="store_true", help="issue from a forecast over 8 h old")
    p.add_argument("--cdp-port", type=int, default=0, help="Chrome's DevTools port (default: any free one)")
    p = sub.add_parser("changes", help="what changed since the session's latest briefing; exit 1 if anything did")
    p.add_argument("session", type=Path)
    p = sub.add_parser("decide", help="record the customer's decision against a briefing")
    p.add_argument("session", type=Path)
    p.add_argument("--decision", required=True, choices=DECISIONS)
    p.add_argument("--by", required=True, help="who decided, as the customer said")
    p.add_argument("--note", default="", help="the reasons, as the customer gave them")
    p.add_argument("--issue", help="the issue id it was made on (default: the latest issued)")
    p.add_argument("--at", help="when they decided, if not now (e.g. 2026-10-24T08:15)")
    p = sub.add_parser("find", help="list issued briefings")
    p.add_argument("--org")
    p.add_argument("--date", help="the session's date, YYYY-MM-DD")
    p.add_argument("--issue", help="an issue id")
    p.add_argument("--csv", action="store_true", help="one row per briefing, for the pilot log")
    a = ap.parse_args(argv)
    try:
        root = archive_root(a.root)
        if a.cmd == "issue":
            folder, text = issue(a.session, root, a.site, stale_ok=a.stale_ok, port=a.cdp_port)
            s = load_session(a.session)
            print(text)
            print(f"Kept in {folder}")
            print("Send to: " + "; ".join(f"{r['name']} <{r['email']}>" for r in s.recipients))
            print("Attach: " + ", ".join(p["pdf"] for p in json.loads((folder / "manifest.json").read_text())["pages"]))
            return 0
        if a.cmd == "changes":
            changes, text = check_changes(a.session, root, a.site)
            print(text, end="")
            if changes:
                print("\nSend to: " + "; ".join(f"{r['name']} <{r['email']}>" for r in load_session(a.session).recipients))
            return 1 if changes else 0
        if a.cmd == "decide":
            row = decide(a.session, root, a.decision, a.by, a.note, a.issue, a.at)
            print(f"Recorded: {row['decision']} by {row['by']}, on briefing {row['issue_id']} (issued {uk(row['issued_at'])}).")
            if not row["latest_issued"]:
                print("Note: a later briefing was issued for this session after that one.")
            return 0
        rows = find(root, a.org, a.date, a.issue)
        if a.csv:
            w = csv.writer(sys.stdout)
            w.writerow(["organisation", "session_date", "session_time", "issue_id", "issued_at", "main", "main_level", "backup",
                        "backup_level", "decision", "decided_by", "files_as_issued", "folder"])
            for r in rows:
                if r.get("broken"):
                    continue
                m, sp = r["manifest"], {x["role"]: x for x in r["manifest"]["spots"]}
                d = r["decisions"][-1] if r["decisions"] else {}
                w.writerow([m["session"]["organisation"], m["session"]["date"], m["session"]["time"], m["issue_id"], m["issued_at"],
                            m["session"]["main"], sp["main"]["day"]["headline"], m["session"]["backup"] or "",
                            (sp.get("backup") or {}).get("day", {}).get("headline", ""), d.get("decision", ""), d.get("by", ""),
                            "yes" if not r["altered"] else "no", r["folder"]])
            return 0
        if not rows:
            print("No issued briefing matches.")
            return 0
        for r in rows:
            if r.get("broken"):
                print(f"{r['folder']}: manifest unreadable")
                continue
            m, ss = r["manifest"], r["manifest"]["session"]
            print(f"{ss['organisation']}, {long_day(ss['date'])}, {ss['time']}: issue {m['issue_id']}, issued {uk(m['issued_at'])}")
            for x in m["spots"]:
                print(f"  {x['role']}: {x['name']}: {x['day']['headline']}")
            for d in r["decisions"]:
                print(f"  decision: {d['decision']} by {d['by']}, recorded {uk(d['recorded_at'])}" + (f": {d['note']}" if d["note"] else ""))
            print(f"  files: {'as issued' if not r['altered'] else 'ALTERED: ' + '; '.join(r['altered'])}")
            print(f"  {r['folder']}")
        return 0
    except BriefingError as e:
        print(f"briefing: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
