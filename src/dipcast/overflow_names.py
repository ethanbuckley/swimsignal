"""Storm overflow names in plain words: the Python copy of plainName and nameCase in
src/dipcast/site/levels.js, whose comment gives the rules and the evidence for them. Used where
Python writes a name a person reads (scripts/site_profile.py). tests/test_overflow_names.py checks
the two copies agree on every name in tests/fixtures/overflow_names.txt; change both together.

    "Addingham/NO 1 SPS/Preliminary Treatment-STW/6Xdwf Overflow" -> "Addingham sewage works overflow"
    "RIVADALE VIEW/CSO" -> "Rivadale View storm overflow"
"""
from __future__ import annotations

import math
import re

A = re.ASCII

# [words, codes as written, phrases in any case], best first.
KINDS = [
    ("sewage works overflow", r"STW|STWs|WwTW|WWTW|Wwtw|WTW|WRC|WRW",
     r"stw|(?:sewage |waste ?water |water )?treatment works|sewage (?:disposal )?works|water recycling centre"),
    ("pumping station overflow", r"SPS|SPST|TPS|IPS|SWPS|PS|SP|P\.STN|PSCSOEO|PSCSO|CEO",
     r"(?:sewage |terminal |storm water |surface water )?pumping station"),
    ("storm sewage overflow", r"SSO|SSTO", r"storm sew(?:age|er) overflow"),
    ("storm overflow", r"CSO|CSOs|CSOEO|SO|OV", r"combined sew(?:er|age) overflow|storm overflow"),
    ("emergency overflow", r"EO|FEEO", r"emergency overflow"),
    ("overflow", r"OVERFLOW", r"overflow"),
]
WORKS, PUMP, SSO, NONE = 0, 1, 2, len(KINDS)
NUM = r"(?:[Nn][Oo]\.? ?|#)?(\d+)"


def _coded(alts: str, flags: int) -> re.Pattern:
    return re.compile(rf"(?:(?<!\S){NUM} )?\b({alts})\b(?: ?(?:#|[Nn][Oo]\.? ?)?(\d+)\b)?", flags | A)


CODES = _coded("|".join(k[1] for k in KINDS), 0)
PHRASES = _coded("|".join(k[2] for k in KINDS), re.IGNORECASE)
_EXACT = [(re.compile(rf"(?:{k[1]})", A), re.compile(rf"(?:{k[2]})", re.IGNORECASE | A)) for k in KINDS]
TECH = re.compile(r"\b[4-9] ?x? ?dwf\b(?: overflow)?|\bpreliminary treatment\b|\bsettled storm\b|\bstorm treatment\b"
                  r"|\binlet(?: works)?\b|\bwaste ?water network\b|\bFFT\b", re.IGNORECASE | A)
TANK = re.compile(r"\bstorm tanks?\b|\b3 ?x? ?dwf\b(?: overflow)?", re.IGNORECASE | A)
IDS = re.compile(r"\s*\((?:site id[^)]*|[A-Z]{3} ?\d{2,4}|\d{3,}[A-Z0-9]*|OOS)\)|\s+[-–] \d{4,}$|\s+[-–] NWL name$"
                 r"|\b(?:DER|NTY|LAK) ?\d{2,4}\b", re.IGNORECASE | A)
SMALL = {"of", "the", "on", "in", "and", "at", "upon", "under", "by", "for", "le", "de", "to", "with", "next"}
EDGE = re.compile(r"^(?:(?:and|at|for|of|to)\b|[&,.)\-–])\s*|\s*(?:\b(?:and|at|for|of|to|sewage)|[&,(\-–])$", re.IGNORECASE | A)
SEP = re.compile(r"\s*[-–]\s+|\s+[-–]\s*|_|/", A)
HELD = "∕"   # a "/" that is not a separator ("O/S", "95/97"), until the end


def name_case(s) -> str:
    """Overflow names that arrive in capitals ("GRASSINGTON/STW") in normal case, as the site shows them."""
    return re.sub(r"[A-Za-z']+", lambda m: m[0][0] + m[0][1:].lower() if re.fullmatch(r"[A-Z']{4,}", m[0]) else m[0],
                  "" if s is None else str(s))


def _kind_of(code: str) -> int:
    return next(i for i, (c, p) in enumerate(_EXACT) if c.fullmatch(code) or p.fullmatch(code))


def _title_case(s: str) -> str:
    def word(i: int, w: str) -> str:
        if re.search(r"[0-9]", w):
            return w
        return "-".join(p if (i or j) and p in SMALL else re.sub(r"[a-z]", lambda c: c[0].upper(), p, count=1)
                        for j, p in enumerate(w.lower().split("-")))
    return " ".join(word(i, w) for i, w in enumerate(s.split(" ")))


def _trim_edges(s: str) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"\(\s*\)", " ", s)).replace(" ,", ",").strip()
    while (u := EDGE.sub("", t, count=1).strip()) != t:
        t = u
    return t


def plain_name(raw) -> str:
    """levels.js's plainName: the place, then what the overflow is at; nameCase's output if no code."""
    s = re.sub(r"\s+", " ", "" if raw is None else str(raw)).strip()
    if not s:
        return ""
    t = re.sub(r"\b([A-Za-z])/(?=[A-Za-z]\b)|(\d)/(?=\d)", lambda m: (m[1] or "") + (m[2] or "") + HELD,
               IDS.sub("", s), flags=A).strip()
    shouty = not re.search(r"[a-z]", re.sub(r"\b(?:WwTW|Wwtw|STWs|CSOs)\b", "", t, flags=A))
    parts: list[tuple[str, str]] = []

    def add(p: str, joint: str) -> None:
        asides = []

        def bracket(m: re.Match) -> str:
            inner = m[1]
            if not CODES.search(inner) and not PHRASES.search(inner):
                return m[0]
            if not re.sub(r"[&,\s]|\band\b", "", PHRASES.sub("", CODES.sub("", inner)), flags=re.IGNORECASE | A):
                asides.append(inner)
            return " "
        parts.append((re.sub(r"\(([^)]*)\)", bracket, p), joint))
        parts.extend((a, ", ") for a in asides)

    start, joint = 0, ""
    for m in SEP.finditer(t):
        add(t[start:m.start()], joint)
        joint = "/" if m[0].strip() == "/" else ", "
        start = m.end()
    add(t[start:], joint)

    best, tag, tank, sso = NONE, None, False, False
    places: list[tuple[str, str]] = []
    for part, j in parts:
        found: list[tuple[int, str | None]] = []

        def take(m: re.Match, found: list = found) -> str:
            found.append((_kind_of(m[2]), m[1] or m[3]))
            return " "

        def tanked(m: re.Match) -> str:
            nonlocal tank
            tank = True
            return " "
        rest = _trim_edges(PHRASES.sub(take, CODES.sub(take, TANK.sub(tanked, TECH.sub(" ", part)))))
        for k, n in found:
            if k == SSO:
                sso = True
            if k < best:
                best, tag = k, n or None
            elif k == best and n and not tag:
                tag = n
        if rest and not re.fullmatch(r"(?:[Nn][Oo]\.? ?|#)?\d+[A-Za-z]?", rest):
            places.append((rest, j))
    if best == WORKS and sso:
        tank = True
    if (best == NONE and not tank) or not places or re.fullmatch(r"x+", places[0][0], re.IGNORECASE):
        return name_case(s)

    def cased(p: str) -> str:
        return _title_case(p) if shouty else name_case(p)
    place = cased(places[0][0])
    for p, j in places[1:]:
        mine = [w for w in re.split(r"[^A-Za-z]+", place) if w]
        stems = {w.lower()[:4] for w in mine if len(w) >= 4}

        def had(w: str, stems: set = stems, mine: list = mine) -> bool:
            return w.lower()[:4] in stems if len(w) >= 4 else any(x.lower().startswith(w.lower()) for x in mine)
        words = [w for w in re.split(r"[^A-Za-z0-9]+", p) if w]
        extra = [w for w in words if not re.fullmatch(r"\d+", w) and not had(w)]
        if not extra:   # a part that only repeats the place may still number it
            n = next((w for w in words if re.fullmatch(r"\d+", w)), None)
            if n and not tag:
                tag = n
            continue
        place += j + cased(p)
    if place.count("(") != place.count(")"):
        place = re.sub(r"\s+", " ", re.sub(r"[()]", "", place)).strip()
    place = place[:1].upper() + place[1:]
    if best == NONE:
        words = "storm tank overflow"
    elif not tank:
        words = KINDS[best][0]
    elif best <= PUMP:
        words = re.sub(r" overflow$", " storm tank overflow", KINDS[best][0])
    else:
        words = "storm tank overflow"
    return f"{place.replace(HELD, '/')} {words}{' ' + tag if tag else ''}"


def overflow_names(site_name, site_id=None) -> tuple[str, str]:
    """levels.js's overflowNames: the plain name, and the company's (in normal case) where it says more.
    An overflow with no name is its id, alone."""
    if site_name is None or (isinstance(site_name, float) and math.isnan(site_name)) or not str(site_name).strip():
        return ("" if site_id is None else str(site_id)), ""
    plain, own = plain_name(site_name), name_case(re.sub(r"\s+", " ", str(site_name)).strip())
    return plain, ("" if plain == own else own)
