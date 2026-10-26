"""Advisory finder, a prototype: drafts of official advice against swimming at a spot, for a person
to read and approve. Nothing here is published, sent or wired into the site build, and nothing here
changes a forecast level. docs/ADVISORY-FINDER-2026-10.md has the reasons and the open decisions.

It reads two kinds of source, both fixed in this module (SOURCES), and refuses any other address:

- Structured official feeds. The Environment Agency's open pollution incidents at bathing waters
  (bathing-water linked-data API, Open Government Licence v3.0) and the Irish EPA's bathing
  restrictions (Bathing Water Open Data API, CC BY 4.0). Each record becomes one draft per water.
- A short list of public notice pages: the EA's own panel for one water, an EA press release on
  GOV.UK, a council news item and a council's swimming status page. Their text is read
  deterministically: HTML to plain text, fixed phrases, labelled dates and a gazetteer of the spots'
  names. No language model, no paid service, no account.

Every draft keeps the source's own words (the evidence, capped in length), the address, the notice
date, the stated expiry, the fetch time and a reason. The defaults are conservative: an expiry
nobody stated stays null; a place name that fits no spot, several spots, or is only a generic word
("the lake") leaves the draft unmatched; a notice without a date is held; a newer lifting or
withdrawal supersedes an older notice in the same thread; notices for one spot that disagree are
all kept and flagged; duplicates collapse; a notice older than STALE_DAYS with no expiry is flagged
stale, never dropped.

Source text is hostile data. Scripts, styles, comments and hidden elements are dropped; control and
invisible characters are removed; evidence is plain text. No link found on a page is ever followed.
Words on a page such as "ignore previous instructions" are text like any other: the only things a
page can change are the fields of its own drafts.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from dipcast import config

TZ = ZoneInfo("Europe/London")
STALE_DAYS = 28            # a notice older than this with no stated expiry is flagged stale
MAX_EVIDENCE = 600         # characters of evidence kept per draft
SHORT = 80                 # a passage shorter than this is read with the block after it
MAX_BYTES = 4_000_000      # a page larger than this is refused (the City of London page is 2.3 MB)
TIMEOUT_S = 20
PAUSE_S = 1.0              # between live requests, one at a time
STATUSES = ("new", "update", "withdrawn", "lifted")
ENDED = {"withdrawn", "lifted"}
# Flags that stop a draft being approved as it stands: a reviewer has to settle them first.
HOLDING = {"unmatched", "ambiguous", "no_date", "conflict", "superseded"}

EA_ID = re.compile(r"uk[a-z0-9]+-\d{5}\Z")                 # "ukj2310-11945"
EA_INCIDENT = re.compile(r"\d{5}-\d{8}-\d{6}\Z")            # "11945-20260619-142800"
EPA_ID = re.compile(r"[A-Za-z0-9_]{10,30}\Z")              # as ireland.ID
EPA_HOME = "https://www.beaches.ie/"

EA_OPEN = "https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident/open.json?_pageSize=100"
EA_HISTORY = "https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident.json?bathingWater.eubwidNotation={}&_pageSize=50"
EPA_ALERTS = "https://data.epa.ie/bw/api/v1/alerts?page=1&per_page=100"

EA_LICENCE = ("Open Government Licence v3.0. environment.data.gov.uk/bwq: \"This dataset is published under "
              "the terms of the Open Government Licence\" (read 26 Oct 2026).")
EPA_LICENCE = ("CC BY 4.0. data.epa.ie/api-list/bathing-water-open-data: \"The data provided in the API is "
               "licensed under a Creative Commons Attribution 4.0 International License\" (read 26 Oct 2026).")
GOVUK_LICENCE = ("Open Government Licence v3.0. GOV.UK footer: \"All content is available under the Open "
                 "Government Licence v3.0, except where otherwise stated\" (read 26 Oct 2026).")


@dataclass(frozen=True)
class Source:
    """One whitelisted source. `kind` is "ea-feed", "epa-feed" or "page"; `scope` lists the spot ids
    a page may speak for (None: any spot)."""
    key: str
    url: str
    publisher: str
    short: str
    kind: str
    licence: str
    scope: tuple[str, ...] | None = None


SOURCES: tuple[Source, ...] = (
    Source("ea-open", EA_OPEN, "Environment Agency", "EA", "ea-feed", EA_LICENCE),
    Source("epa-alerts", EPA_ALERTS, "Environmental Protection Agency (Ireland)", "EPA", "epa-feed", EPA_LICENCE),
    Source("ea-widget-frensham",
           "https://environment.data.gov.uk/bwq/widget/widget/widget1?eu=ukj2310-11945&history=false&m=false&p=false",
           "Environment Agency", "EA", "page", EA_LICENCE + " The panel itself ends \"Linked-data from the "
           "Environment Agency · OGL\".", ("bw-ukj2310-11945",)),
    Source("govuk-lake-district-algae-2018",
           "https://www.gov.uk/government/news/blue-green-algae-remains-present-in-four-lake-district-locations",
           "Environment Agency (GOV.UK)", "EA", "page", GOVUK_LICENCE),
    Source("waverley-frensham",
           "https://www.waverley.gov.uk/council-updates/read-our-latest-news/visitors-to-frensham-reminded-do-not-enter-water",
           "Waverley Borough Council", "Waverley BC", "page",
           "Not open-licensed: the footer reads \"© Copyright 2026 by Waverley Borough Council\" (read 26 Oct "
           "2026). Evidence may be kept for review; it may not be republished without permission."),
    Source("col-hampstead-swimming",
           "https://www.cityoflondon.gov.uk/things-to-do/green-spaces/hampstead-heath/activities-at-hampstead-heath/swimming-at-hampstead-heath",
           "City of London Corporation", "City of London", "page",
           "Not open-licensed: the footer reads \"© City of London Corporation 2026\" (read 26 Oct 2026). "
           "Evidence may be kept for review; it may not be republished without permission.",
           ("bw-uki1101-11910", "bw-uki1101-11920", "bw-uki1101-11930")),
)
BY_KEY = {s.key: s for s in SOURCES}


class Refused(ValueError):
    """An address or source that is not on the whitelist."""


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{(parts.hostname or '').lower()}{parts.path}?{parts.query}"


def ea_history_url(eubwid: str) -> str | None:
    """One water's incident history at the EA, open and closed: built here for an id that is strictly
    an EA bathing-water id, never taken from a response."""
    return EA_HISTORY.format(eubwid) if isinstance(eubwid, str) and EA_ID.fullmatch(eubwid) else None


def source_for(url: str, key: str | None = None) -> Source:
    """The whitelisted source for an address, or Refused. An address must equal a listed one exactly
    (https, host, path and query); the one pattern is an EA history for a valid bathing-water id."""
    if not isinstance(url, str) or not url.startswith("https://"):
        raise Refused(f"not an https address on the whitelist: {url!r}")
    want = _canonical(url)
    for s in SOURCES:
        if _canonical(s.url) == want and (key is None or key == s.key):
            return s
    m = re.fullmatch(r"https://environment\.data\.gov\.uk/doc/bathing-water-quality/pollution-incident\.json"
                     r"\?bathingWater\.eubwidNotation=([a-z0-9-]+)&_pageSize=50", url)
    if m and ea_history_url(m[1]) == url and key in (None, "ea-history"):
        return Source("ea-history", url, "Environment Agency", "EA", "ea-feed", EA_LICENCE)
    raise Refused(f"not on the whitelist: {url!r}")


# ---- text --------------------------------------------------------------------------------------

_SKIP = {"script", "style", "noscript", "template", "iframe", "svg", "math", "object", "embed"}
_BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "tr", "dt", "dd",
          "br", "section", "article", "header", "footer", "main", "blockquote", "figcaption", "title",
          "table", "dl", "nav", "aside", "form", "time", "hr"}
_VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}


def clean(text) -> str:
    """Plain text: Unicode NFKC, control and invisible format characters removed (zero-width
    spaces, bidi overrides, terminal escapes), runs of white space made one space."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = "".join(" " if c in "\t\n\r\f\v" else c for c in t
                if unicodedata.category(c) not in ("Cc", "Cf") or c in "\t\n\r\f\v")
    return re.sub(r"\s+", " ", t).strip()


def _hidden(attrs) -> bool:
    a = {k.lower(): (v or "") for k, v in attrs}
    style = re.sub(r"\s+", "", a.get("style", "").lower())
    return ("hidden" in a or a.get("aria-hidden", "").lower() == "true"
            or "display:none" in style or "visibility:hidden" in style)


class _Blocks(HTMLParser):
    """HTML to a list of plain-text blocks, one per paragraph, heading, list item or cell. Content of
    scripts, styles, frames and hidden elements is dropped; comments and processing instructions are
    ignored; links are never collected."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._buf: list[str] = []
        self._skip: str | None = None
        self._depth = 0

    def _flush(self):
        t = clean("".join(self._buf))
        if t:
            self.blocks.append(t)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if self._skip:
            if tag == self._skip and tag not in _VOID:
                self._depth += 1
            return
        if tag in _SKIP or (tag not in _VOID and _hidden(attrs)):
            self._skip, self._depth = tag, 1
            return
        if tag in _BLOCK:
            self._flush()

    def handle_startendtag(self, tag, attrs):
        if not self._skip and tag in _BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if self._skip:
            if tag == self._skip:
                self._depth -= 1
                if self._depth <= 0:
                    self._skip, self._depth = None, 0
            return
        if tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def html_blocks(markup: str) -> list[str]:
    p = _Blocks()
    try:
        p.feed(markup if isinstance(markup, str) else "")
        p.close()
    except Exception:  # noqa: BLE001 - html.parser rarely raises; a page it cannot read gives no blocks
        return []
    return p.blocks


def cap(text: str) -> tuple[str, bool]:
    """Evidence at most MAX_EVIDENCE characters, cut at a word. (text, whether it was cut)."""
    t = clean(text)
    if len(t) <= MAX_EVIDENCE:
        return t, False
    cut = t[:MAX_EVIDENCE].rsplit(" ", 1)[0]
    return cut, True


# ---- phrases and dates -------------------------------------------------------------------------

ADVICE = re.compile(
    r"\b(advi[cs]e[sd]? against (?:bathing|swimming)|(?:bathing|swimming) is not advised|not advised"
    r"|advice not to swim|do not swim|don'?t swim|not to (?:swim|enter the water)"
    r"|(?:bathing|swimming) (?:is )?(?:temporarily )?prohibited|blue[- ]green alga(?:e|l)|harmful alga(?:e|l)"
    r"|algal bloom|cyanobacteria|sewage|pollution incident"
    r"|closed (?:due to|because of) (?:pollution|algae|sewage|(?:poor )?water quality))", re.I)
# A lifting or withdrawal counts only when the page says what was lifted ("the warning has been
# lifted"): a bare "lifted" or "status=lifted" in a passage changes nothing.
_WHAT = r"\b(?:advice|advisory|warning|notice|restriction|prohibition|closure|ban)s?\b[^.;]{0,80}?\b(?:has|have|was|were|is|are)\s+(?:now\s+)?(?:been\s+)?"
LIFTED = re.compile(_WHAT + r"lifted\b|\b(?:no longer (?:in place|in force|applies)|(?:has|have) (?:now )?re-?opened"
                    r"|safe to swim again)\b", re.I)
WITHDRAWN = re.compile(_WHAT + r"(?:withdrawn|cancell?ed|rescinded)\b|\bissued in error\b", re.I)
CAUSES = (("algae", re.compile(r"\b(harmful alga(?:e|l bloom)|blue[- ]green alga(?:e|l bloom)|algal bloom|cyanobacteria)\b", re.I)),
          ("sewage", re.compile(r"\bsewage\b", re.I)),
          ("oil or fuel", re.compile(r"\b(oil|fuel) (?:spill|pollution|sheen)\b", re.I)))
_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december"]
MONTHS = {**{m: i for i, m in enumerate(_MONTH_NAMES, 1)}, **{m[:3]: i for i, m in enumerate(_MONTH_NAMES, 1)}, "sept": 9}
_DATE = r"(\d{1,2}(?:st|nd|rd|th)? [A-Za-z]{3,9},? \d{4}|\d{4}-\d{2}-\d{2})"
LABELLED = re.compile(r"\b(first published|published|date posted|posted|last updated|updated|issued)\s*:?\s*" + _DATE, re.I)
UNTIL = re.compile(r"\buntil (?:at least )?" + _DATE, re.I)
FURTHER_NOTICE = re.compile(r"\buntil further notice\b", re.I)


def parse_day(text) -> date | None:
    """"22 August 2025", "19 Jul 2018", "1st June 2026" or "2026-06-19" as a date; None otherwise."""
    if not isinstance(text, str):
        return None
    t = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t[:10]):
        try:
            return date.fromisoformat(t[:10])
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]{3,9}),? (\d{4})", t)
    if not m or m[2].lower() not in MONTHS:
        return None
    try:
        return date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
    except ValueError:
        return None


def _local_day(stamp) -> date | None:
    """An EA or EPA time ("2026-06-19T14:28:00", local) as its date."""
    return parse_day(stamp[:10]) if isinstance(stamp, str) and len(stamp) >= 10 else None


def show_day(d: date | None) -> str:
    return f"{d.day} {d:%b %Y}" if d else "no date"


# ---- spots -------------------------------------------------------------------------------------

SPOT_FILES = ("spots.csv", "spots-osm.csv")
# Words that never name a spot on their own.
GENERIC = {"the", "lake", "lakes", "pond", "ponds", "river", "water", "waters", "lido", "beach", "mere", "tarn",
           "reservoir", "bathing", "swimming", "the lake", "the pond", "the river", "the water", "the lido",
           "the beach", "the ponds", "the mere", "the tarn", "the reservoir", "bathing water", "bathing pond",
           "bathing ponds"}
# Names a source may use for one spot that its own name does not contain (the City of London's
# names for the three Hampstead Heath ponds). Each must name exactly one spot.
ALIASES = {
    "bw-uki1101-11910": ("kenwood ladies pond", "kenwood ladies bathing pond"),
    "bw-uki1101-11920": ("highgate mens pond", "highgate mens bathing pond"),
    "bw-uki1101-11930": ("hampstead mixed pond", "hampstead mixed bathing pond"),
}
_SEPARATORS = re.compile(r",|\(| - | at | in | above | below | near ")


def norm(text: str) -> str:
    """A name or passage for matching: lower case, accents and apostrophes dropped, letters and digits."""
    t = unicodedata.normalize("NFKD", clean(text))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"['’‘`]", "", t)
    return " ".join(re.findall(r"[a-z0-9]+", t))


@dataclass(frozen=True)
class Spot:
    id: str
    name: str
    kind: str


class Gazetteer:
    """The spots' names. `specific` keys name one spot (its whole name, or an alias); `waters` keys are
    the water a name begins with ("windermere", "hampstead heath", "river lune"), which may be shared."""

    def __init__(self, spots: list[Spot]):
        self.spots = {s.id: s for s in spots}
        self.specific: dict[str, set[str]] = {}
        self.waters: dict[str, set[str]] = {}
        for s in spots:
            full = norm(s.name)
            if full and full not in GENERIC:
                self.specific.setdefault(full, set()).add(s.id)
            for alias in ALIASES.get(s.id, ()):
                self.specific.setdefault(norm(alias), set()).add(s.id)
            water = norm(_SEPARATORS.split(s.name.lower(), maxsplit=1)[0])
            if water and water not in GENERIC and not set(water.split()) <= GENERIC:
                self.waters.setdefault(water, set()).add(s.id)

    @classmethod
    def load(cls, root: Path | None = None) -> Gazetteer:
        root = Path(root or config.ROOT)
        spots, seen = [], set()
        for f in SPOT_FILES:
            path = root / f
            if not path.exists():
                continue
            with path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    sid = (row.get("id") or "").strip()
                    if sid and sid not in seen:
                        seen.add(sid)
                        spots.append(Spot(sid, (row.get("name") or "").strip(), (row.get("kind") or "").strip()))
        return cls(spots)

    def match(self, passage: str, scope: tuple[str, ...] | None = None) -> tuple[str | None, list[str], str]:
        """(spot id or None, candidate ids, reason). One spot only when the passage names exactly one:
        by a specific name, or else by a water name only that spot has. A water several spots share,
        names of several spots, or only generic words leave it unmatched, with the candidates."""
        text = f" {norm(passage)} "
        allowed = set(scope) if scope else None
        keep = lambda ids: {i for i in ids if allowed is None or i in allowed}  # noqa: E731
        found = set()
        for key, ids in self.specific.items():
            if f" {key} " in text:
                found |= keep(ids)
        if len(found) == 1:
            sid = next(iter(found))
            return sid, [], f"names {self.spots[sid].name!r}"
        if len(found) > 1:
            return None, sorted(found), "names more than one spot"
        shared, words = set(), []
        for key, ids in self.waters.items():
            if f" {key} " in text:
                shared |= keep(ids)
                words.append(key)
        if len(shared) == 1:
            sid = next(iter(shared))
            return sid, [], f"names {self.spots[sid].name!r} (the only spot on {words[0]!r})"
        if len(shared) > 1:
            return None, sorted(shared), f"names {', '.join(sorted(words))}: shared by {len(shared)} spots"
        if any(f" {g} " in text for g in GENERIC):
            return None, [], "only a generic word for a water"
        return None, [], "names no spot"


# ---- drafts ------------------------------------------------------------------------------------

def _draft(source: Source, *, spot_id, spot_name, candidates, water_id, water_name, feed_id, record_url,
           record_time, evidence, evidence_kind, notice_date, status, advice, cause, expiry, expiry_basis,
           ended, fetched_at, reason, flags=()) -> dict:
    text, cut = cap(evidence)
    d = {
        "draft_id": None, "approved": False, "held": False,
        "spot_id": spot_id, "spot_name": spot_name, "candidates": list(candidates),
        "water_id": water_id, "water_name": water_name,
        "source": {"key": source.key, "publisher": source.publisher, "short": source.short, "url": source.url,
                   "licence": source.licence},
        "feed_id": feed_id, "record_url": record_url, "record_time": record_time,
        "evidence": text, "evidence_kind": evidence_kind, "evidence_truncated": cut,
        "notice_date": notice_date.isoformat() if notice_date else None,
        "status": status, "advice": advice, "cause": cause,
        "expiry": expiry.isoformat() if expiry else None, "expiry_basis": expiry_basis,
        "ended": ended.isoformat() if ended else None,
        "fetched_at": fetched_at, "flags": sorted(set(flags)), "reason": reason,
        "duplicates": 0, "superseded_by": None, "draft_line": None,
    }
    if spot_id is None:
        d["flags"] = sorted(set(d["flags"]) | {"unmatched"} | ({"ambiguous"} if candidates else set()))
    if notice_date is None:
        d["flags"] = sorted(set(d["flags"]) | {"no_date"})
    key = feed_id or f"{source.url}|{spot_id}|{text}"
    d["draft_id"] = hashlib.sha1(f"{source.key}|{key}|{spot_id}|{water_id}".encode()).hexdigest()[:12]
    return d


def _v(x):
    """A linked-data value: {"_value": ...} or a plain value; the first of a list."""
    if isinstance(x, list):
        x = x[0] if x else None
    return x.get("_value") if isinstance(x, dict) else x


def _label(x) -> str | None:
    if isinstance(x, dict):
        v = _v(x.get("name")) or _v(x.get("label"))
        return clean(v) or None if isinstance(v, str) else None
    return None


def parse_ea(body, source: Source, gazetteer: Gazetteer, fetched_at: str, errors: list) -> list[dict]:
    """The EA's pollution-incident list (open, or one water's history) as drafts, one per incident and
    water. An incident with an end is "lifted"; one without is open ("new"). A row without a valid
    incident id, water id or start is left out and named in `errors`."""
    items = ((body or {}).get("result") or {}).get("items") if isinstance(body, dict) else None
    if not isinstance(items, list):
        errors.append({"source": source.key, "row": None, "problem": "no items list"})
        return []
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errors.append({"source": source.key, "row": i, "problem": "row is not an object"})
            continue
        inc = it.get("incidentNotation")
        start_raw = _v(it.get("startOfIncident"))
        start = _local_day(start_raw)
        waters = it.get("bathingWater")
        waters = waters if isinstance(waters, list) else [waters]
        if not isinstance(inc, str) or not EA_INCIDENT.fullmatch(inc):
            errors.append({"source": source.key, "row": i, "problem": "no valid incidentNotation"})
            continue
        if start is None:
            errors.append({"source": source.key, "row": i, "problem": f"{inc}: no readable startOfIncident"})
            continue
        kind = _label(it.get("incidentType"))
        expected_raw, end_raw = _v(it.get("expectedEndOfIncident")), _v(it.get("endOfIncident"))
        expected, ended = _local_day(expected_raw), _local_day(end_raw)
        rec = _v(it.get("som_recordDateTime")) or _v(it.get("recordDateTime"))
        about = it.get("_about") if isinstance(it.get("_about"), str) else None
        good = 0
        for w in waters:
            wid = w.get("eubwidNotation") if isinstance(w, dict) else None
            if not isinstance(wid, str) or not EA_ID.fullmatch(wid):
                continue
            good += 1
            wname = _label(w) if isinstance(w, dict) else None
            sid = f"bw-{wid}"
            spot = gazetteer.spots.get(sid)
            fields = [("label", _v(it.get("label"))), ("bathingWater", f"{wname} ({wid})"),
                      ("incidentType", kind), ("startOfIncident", start_raw),
                      ("expectedEndOfIncident", expected_raw), ("endOfIncident", end_raw),
                      ("recordDateTime", rec)]
            evidence = "; ".join(f"{k}: {clean(str(v))}" for k, v in fields if v)
            status = "lifted" if ended else "new"
            if spot:
                reason = f"EA incident {inc} at {wname} ({wid}), which is spot {sid}"
            else:
                reason = f"EA incident {inc} at {wname} ({wid}): not a SwimSignal spot (coast or estuary, or not listed)"
            reason += f"; {'ended ' + end_raw if ended else 'open in the EA list'} as read {fetched_at}"
            if expected_raw and not ended:
                basis = "EA expectedEndOfIncident"
            elif ended:
                basis = None
            else:
                basis = "the EA gives no expected end"
            out.append(_draft(source, spot_id=sid if spot else None, spot_name=spot.name if spot else None,
                              candidates=[], water_id=wid, water_name=wname, feed_id=f"ea:{inc}",
                              record_url=about, record_time=rec, evidence=evidence, evidence_kind="feed fields",
                              notice_date=start, status=status, advice="open pollution incident" if not ended
                              else "pollution incident ended", cause=kind, expiry=expected if not ended else None,
                              expiry_basis=basis, ended=ended, fetched_at=fetched_at, reason=reason))
        if not good:
            errors.append({"source": source.key, "row": i, "problem": f"{inc}: no valid bathing-water id"})
    return out


def parse_epa(body, source: Source, gazetteer: Gazetteer, fetched_at: str, now: datetime, errors: list) -> list[dict]:
    """The Irish EPA's restrictions as drafts. The Republic's waters are on the coverage page, not
    SwimSignal spots, so every draft is unmatched and keeps the EPA's water id. The expiry is the
    start plus the EPA's expected duration in days, marked as such; an end date already past makes
    the draft "lifted"."""
    items = body.get("list") if isinstance(body, dict) else None
    if not isinstance(items, list):
        errors.append({"source": source.key, "row": None, "problem": "no list"})
        return []
    today = now.astimezone(TZ).date()
    out = []
    for i, a in enumerate(items):
        if not isinstance(a, dict):
            errors.append({"source": source.key, "row": i, "problem": "row is not an object"})
            continue
        wid, kind = a.get("beach_id"), clean(a.get("bathing_restriction_type"))
        start, end = _local_day(a.get("incident_start_date")), _local_day(a.get("incident_end_date"))
        inc = a.get("incident_id")
        if not isinstance(wid, str) or not EPA_ID.fullmatch(wid) or not kind:
            errors.append({"source": source.key, "row": i, "problem": "no valid beach_id or restriction type"})
            continue
        if start is None:
            errors.append({"source": source.key, "row": i, "problem": f"{wid}: no readable incident_start_date"})
            continue
        if isinstance(inc, bool) or not isinstance(inc, int):
            errors.append({"source": source.key, "row": i, "problem": f"{wid}: no incident_id"})
            continue
        days = a.get("incident_expected_duration")
        expiry = basis = None
        if isinstance(days, int) and not isinstance(days, bool) and 0 < days <= 366:
            expiry = start + timedelta(days=days)
            basis = f"EPA expected duration {days} days, counted from the start date"
        else:
            basis = "the EPA gives no expected duration"
        ended = end if end and end <= today else None
        name = clean(a.get("beach_name")) or None
        fields = [("bathing_water_incident_id", a.get("bathing_water_incident_id")), ("beach_name", name),
                  ("bathing_restriction_type", kind), ("incident_start_date", a.get("incident_start_date")),
                  ("incident_expected_duration", days), ("incident_description", a.get("incident_description")),
                  ("incident_end_date", a.get("incident_end_date")), ("last_updated", a.get("last_updated"))]
        evidence = "; ".join(f"{k}: {clean(str(v))}" for k, v in fields if v not in (None, ""))
        out.append(_draft(source, spot_id=None, spot_name=None, candidates=[], water_id=wid, water_name=name,
                          feed_id=f"epa:{inc}", record_url=None, record_time=a.get("last_updated"),
                          evidence=evidence, evidence_kind="feed fields", notice_date=start,
                          status="lifted" if ended else "new", advice=kind,
                          cause=clean(a.get("incident_description")) or None,
                          expiry=None if ended else expiry, expiry_basis=None if ended else basis, ended=ended,
                          fetched_at=fetched_at,
                          reason=f"EPA restriction at {name} ({wid}): the Republic of Ireland's list on the "
                                 "coverage page, not a SwimSignal spot"))
    return out


def _cause(text: str) -> str | None:
    for _, rx in CAUSES:
        m = rx.search(text)
        if m:
            return clean(m.group(0)).lower()
    return None


def parse_page(markup: str, source: Source, gazetteer: Gazetteer, fetched_at: str) -> list[dict]:
    """A notice page as drafts: one per spot the page's advisory passages name, or one unmatched
    draft when they name none. The notice date is the latest labelled date on the page ("Published",
    "Date posted", "Updated"); an expiry only where the page states a date ("until 3 July 2026")."""
    blocks = html_blocks(markup)
    page = " ".join(blocks)
    dates = [parse_day(m[2]) for m in LABELLED.finditer(page)]
    dates = [d for d in dates if d]
    notice = max(dates) if dates else None
    until = {d for d in (parse_day(m[1]) for m in UNTIL.finditer(page)) if d}
    if len(until) == 1:
        expiry, basis = next(iter(until)), "the page gives an end date"
    elif len(until) > 1:
        expiry, basis = None, "the page gives more than one end date"
    elif FURTHER_NOTICE.search(page):
        expiry, basis = None, "the page says until further notice"
    else:
        expiry, basis = None, "the page gives no end"
    # A short passage runs on into the next block ("Bathing is not advised today" / "due to pollution
    # from harmful algae" in the EA's panel): the two together are the evidence.
    hits = [b if len(b) >= SHORT or i + 1 >= len(blocks) else f"{b} {blocks[i + 1]}"
            for i, b in enumerate(blocks) if ADVICE.search(b)]
    out, by_spot, unmatched = [], {}, []
    for b in hits:
        sid, cands, why = gazetteer.match(b, source.scope)
        if not sid and not cands and source.scope and len(source.scope) == 1 and source.scope[0] in gazetteer.spots:
            sid, why = source.scope[0], "names no spot, but the page is the spot's own panel (its address names the water)"
        if sid:
            by_spot.setdefault(sid, (b, why))
        elif cands:
            unmatched.append((b, cands, why))
    date_note = f"notice date {show_day(notice)} (latest labelled date on the page)" if notice else "no labelled date on the page"

    def make(b, sid, cands, reason):
        status = "withdrawn" if WITHDRAWN.search(b) else "lifted" if LIFTED.search(b) else "new"
        return _draft(source, spot_id=sid, spot_name=gazetteer.spots[sid].name if sid else None, candidates=cands,
                      water_id=None, water_name=None, feed_id=None, record_url=None, record_time=None, evidence=b,
                      evidence_kind="page passage", notice_date=notice, status=status,
                      advice=clean(ADVICE.search(b).group(0)), cause=_cause(b), expiry=expiry, expiry_basis=basis,
                      ended=None, fetched_at=fetched_at, reason=f"{reason}; {date_note}")

    for sid, (b, why) in by_spot.items():
        out.append(make(b, sid, [], f"passage {why}"))
    if not by_spot:
        # No passage names one spot: a draft for each set of candidates, or else one for the first
        # advisory passage, unmatched. Generic health advice on the same page adds nothing.
        seen = set()
        for b, cands, why in unmatched:
            if tuple(cands) not in seen:
                seen.add(tuple(cands))
                out.append(make(b, None, cands, f"passage {why}; left unmatched"))
        if not out and hits:
            out.append(make(hits[0], None, [], f"advisory passage {gazetteer.match(hits[0], source.scope)[2]}; left unmatched"))
    return out


# ---- resolving ---------------------------------------------------------------------------------

def _thread(d: dict) -> str:
    """Drafts in one thread speak about the same thing: one feed incident, or one publisher on one spot."""
    if d["feed_id"]:
        return f"{d['feed_id']}|{d['water_id']}"
    if not d["spot_id"]:
        return f"solo|{d['draft_id']}"
    return f"{d['source']['publisher']}|{d['spot_id']}"


def _flag(d: dict, *flags: str) -> None:
    d["flags"] = sorted(set(d["flags"]) | set(flags))


def resolve(drafts: list[dict], now: datetime, previous: list[dict] | None = None,
            complete_feeds: set[str] | None = None) -> list[dict]:
    """Collapse duplicates, mark updates against `previous`, supersede within a thread, flag conflicts
    and stale notices, and set `held`. Nothing is dropped except exact duplicates, which are counted
    on the draft kept. `complete_feeds` are feed sources read whole this run: a previous open draft
    from one of them that is no longer listed comes back as "withdrawn", for a person to check."""
    drafts = copy.deepcopy(drafts)
    kept: dict[str, dict] = {}
    for d in drafts:
        key = (f"feed|{d['feed_id']}|{d['water_id']}" if d["feed_id"]
               else f"page|{d['source']['url']}|{d['spot_id']}|{d['evidence']}")
        old = kept.get(key)
        if old is None:
            kept[key] = d
            continue
        newer = (d["record_time"] or "") > (old["record_time"] or "")
        winner = d if newer else old
        winner["duplicates"] = old["duplicates"] + d["duplicates"] + 1
        kept[key] = winner
    out = list(kept.values())

    prev = {p.get("draft_id"): p for p in (previous or []) if isinstance(p, dict)}
    prev_threads = {}
    for p in prev.values():
        try:
            prev_threads.setdefault(_thread(p), []).append(p)
        except (KeyError, TypeError):
            continue
    for d in out:
        if d["status"] in ENDED:
            continue
        for p in prev_threads.get(_thread(d), []):
            if p.get("status") not in ENDED and (p.get("evidence") != d["evidence"] or p.get("expiry") != d["expiry"]):
                d["status"] = "update"
                d["reason"] += "; changed since the previous run"
                break
    seen_feed = {d["feed_id"] for d in out if d["feed_id"]}
    for p in prev.values():
        src = (p.get("source") or {}).get("key")
        if (src in (complete_feeds or set()) and p.get("feed_id") and p.get("status") not in ENDED
                and p["feed_id"] not in seen_feed):
            gone = dict(p, status="withdrawn", flags=[f for f in p.get("flags", []) if f != "superseded"],
                        reason=f"{p.get('feed_id')} is no longer in the source's list and no end was read; "
                               "check the source before treating it as lifted",
                        superseded_by=None, duplicates=0, approved=False)
            out.append(gone)

    threads: dict[str, list[dict]] = {}
    for d in out:
        threads.setdefault(_thread(d), []).append(d)
    for items in threads.values():
        if len(items) < 2:
            continue
        dated = [d for d in items if d["notice_date"]]
        if len(dated) < len(items):
            for d in items:
                _flag(d, "conflict")
                d["reason"] += "; same thread as a notice it cannot be ordered against (no date)"
            continue
        latest = max(dated, key=lambda d: (d["notice_date"], d["status"] in ENDED))
        for d in items:
            if d is not latest and d["notice_date"] <= latest["notice_date"]:
                _flag(d, "superseded")
                d["superseded_by"] = latest["draft_id"]
                d["reason"] += f"; superseded by the newer {latest['status']} notice of {latest['notice_date']}"

    by_spot: dict[str, list[dict]] = {}
    for d in out:
        if d["spot_id"] and "superseded" not in d["flags"]:
            by_spot.setdefault(d["spot_id"], []).append(d)
    for items in by_spot.values():
        states = {d["status"] in ENDED for d in items}
        if len(states) > 1:
            for d in items:
                _flag(d, "conflict")
                d["reason"] += "; another current notice for this spot disagrees"

    today = now.astimezone(TZ).date()
    for d in out:
        nd = date.fromisoformat(d["notice_date"]) if d["notice_date"] else None
        if nd and d["status"] not in ENDED and not d["expiry"] and (today - nd).days > STALE_DAYS:
            _flag(d, "stale")
            d["reason"] += f"; older than {STALE_DAYS} days with no stated expiry"
        d["held"] = bool(HOLDING & set(d["flags"]))
        d["approved"] = False
        d["draft_line"] = draft_line(d)
    order = {"new": 0, "update": 1, "lifted": 2, "withdrawn": 3}
    return sorted(out, key=lambda d: (d["spot_id"] is None, d["spot_id"] or "", order.get(d["status"], 9),
                                      d["notice_date"] or "", d["draft_id"]))


def draft_line(d: dict) -> str | None:
    """A suggested line for a matched draft, from its fields only. The wording is not settled
    (docs/ADVISORY-FINDER-2026-10.md); a person writes or approves the line that is shown."""
    if not d.get("spot_id"):
        return None
    short = d["source"].get("short") or d["source"]["publisher"]
    nd = date.fromisoformat(d["notice_date"]) if d.get("notice_date") else None
    parts = [f"{short}: {d['advice']} at {d['spot_name']}"]
    if d.get("cause"):
        parts.append(d["cause"])
    if d["status"] in ENDED:
        parts.append(f"ended {show_day(date.fromisoformat(d['ended']))}" if d.get("ended") else d["status"])
    elif nd:
        parts.append(f"since {show_day(nd)}")
    return ", ".join(parts)


# ---- reading -----------------------------------------------------------------------------------

def _parse(source: Source, raw: str, gazetteer: Gazetteer, fetched_at: str, now: datetime, errors: list) -> list[dict]:
    if source.kind == "page":
        return parse_page(raw, source, gazetteer, fetched_at)
    try:
        body = json.loads(raw)
    except ValueError:
        errors.append({"source": source.key, "row": None, "problem": "not JSON"})
        return []
    if source.kind == "ea-feed":
        return parse_ea(body, source, gazetteer, fetched_at, errors)
    return parse_epa(body, source, gazetteer, fetched_at, now, errors)


def _complete(source: Source, raw: str) -> bool:
    """Whether a feed answer is the whole list: no next page (EA), or as many rows as its count (EPA)."""
    try:
        body = json.loads(raw)
    except ValueError:
        return False
    if source.kind == "ea-feed":
        res = body.get("result") if isinstance(body, dict) else None
        return isinstance(res, dict) and "next" not in res and isinstance(res.get("items"), list)
    if source.kind == "epa-feed":
        return isinstance(body, dict) and isinstance(body.get("list"), list) and body.get("count") == len(body["list"])
    return False


def fetch(url: str, client: httpx.Client, key: str | None = None) -> tuple[Source, str]:
    """One whitelisted address, without following redirects. Raises Refused for any other address."""
    source = source_for(url, key)
    with client.stream("GET", url, timeout=TIMEOUT_S) as r:
        if r.status_code != 200:
            raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
        chunks, size = [], 0
        for chunk in r.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise Refused(f"larger than {MAX_BYTES} bytes: {url}")
            chunks.append(chunk)
        return source, b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")


def run(*, fixtures: Path | None = None, now: datetime | None = None, previous: list[dict] | None = None,
        gazetteer: Gazetteer | None = None, client: httpx.Client | None = None,
        keys: tuple[str, ...] | None = None) -> dict:
    """A dry run: read every whitelisted source (from `fixtures`/manifest.json, or live, one request at
    a time), and return the drafts. Writes nothing and sends nothing."""
    now = now or datetime.now(TZ)
    gazetteer = gazetteer or Gazetteer.load()
    drafts, errors, report, complete = [], [], [], set()
    if fixtures is not None:
        manifest = json.loads((Path(fixtures) / "manifest.json").read_text(encoding="utf-8"))
        entries = manifest.get("sources", []) if isinstance(manifest, dict) else []
        for e in entries:
            key, url = e.get("key"), e.get("url")
            if keys and key not in keys:
                continue
            try:
                source = source_for(url, key)
                raw = (Path(fixtures) / Path(str(e.get("file"))).name).read_text(encoding="utf-8")
            except Refused as err:
                report.append({"key": key, "url": url, "state": "refused", "error": str(err)})
                continue
            except OSError as err:
                report.append({"key": key, "url": url, "state": "error", "error": type(err).__name__})
                continue
            fetched = str(e.get("fetched_at") or "")
            found = _parse(source, raw, gazetteer, fetched, now, errors)
            if source.kind != "page" and _complete(source, raw):
                complete.add(source.key)
            drafts += found
            report.append({"key": key, "url": url, "state": "ok", "fetched_at": fetched, "candidates": len(found),
                           "from": "fixture " + Path(str(e.get("file"))).name})
    else:
        own = client is None
        client = client or httpx.Client(headers={"User-Agent": config.USER_AGENT}, follow_redirects=False)
        try:
            for i, s in enumerate(x for x in SOURCES if not keys or x.key in keys):
                if i:
                    time.sleep(PAUSE_S)
                fetched = datetime.now(TZ).isoformat(timespec="seconds")
                try:
                    source, raw = fetch(s.url, client, s.key)
                except Refused as err:
                    report.append({"key": s.key, "url": s.url, "state": "refused", "error": str(err)})
                    continue
                except Exception as err:  # noqa: BLE001 - a source that fails gives no drafts, and says so
                    code = getattr(getattr(err, "response", None), "status_code", None)
                    report.append({"key": s.key, "url": s.url, "state": "error",
                                   "error": f"HTTP {code}" if code else type(err).__name__})
                    continue
                found = _parse(source, raw, gazetteer, fetched, now, errors)
                if source.kind != "page" and _complete(source, raw):
                    complete.add(source.key)
                drafts += found
                report.append({"key": s.key, "url": s.url, "state": "ok", "fetched_at": fetched, "candidates": len(found)})
        finally:
            if own:
                client.close()
    drafts = resolve(drafts, now, previous, complete)
    return {"generated_at": now.isoformat(timespec="seconds"), "dry_run": True, "published": False,
            "mode": "fixtures" if fixtures is not None else "live", "stale_days": STALE_DAYS,
            "sources": report, "errors": errors, "drafts": drafts}


def table(result: dict, width: int = 64) -> str:
    """A short plain-text review table. Every cell is cleaned again, so a page cannot write terminal
    escapes or new lines into it."""
    rows = [("status", "spot", "notice", "expiry", "source", "flags", "evidence")]
    for d in result["drafts"]:
        spot = d["spot_id"] or ("? " + ",".join(c.removeprefix("bw-") for c in d["candidates"][:3])
                                + ("…" if len(d["candidates"]) > 3 else "") if d["candidates"] else "-")
        ev = clean(d["evidence"])
        rows.append((d["status"], clean(spot)[:28], d["notice_date"] or "-", d["expiry"] or "-",
                     d["source"]["key"][:24], ",".join(d["flags"]) or "-",
                     ev[:width] + ("…" if len(ev) > width else "")))
    widths = [max(len(r[i]) for r in rows) for i in range(6)]
    lines = ["  ".join(r[i].ljust(widths[i]) for i in range(6)) + "  " + r[6] for r in rows]
    for s in result["sources"]:
        lines.append(f"source {clean(str(s['key']))}: {s['state']}"
                     + (f", {s.get('candidates', 0)} candidate(s)" if s["state"] == "ok" else f" ({clean(str(s.get('error')))})"))
    if result["errors"]:
        lines.append(f"{len(result['errors'])} feed row(s) left out: "
                     + "; ".join(clean(f"{e['source']} row {e['row']}: {e['problem']}") for e in result["errors"][:5]))
    held = sum(d["held"] for d in result["drafts"])
    lines.append(f"{len(result['drafts'])} draft(s), {held} held. Dry run: nothing approved, published or sent.")
    return "\n".join(lines)
