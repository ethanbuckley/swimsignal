"""A spot's opening: two or three sentences of plain fact about the place, for its page, its description in a
search result and its structured data (docs/DESIGN.md, "A spot's opening").

The first part is written by hand in guides/openings/openings.toml: the water and how people reach it, each from a page
the entry cites (the landowner's, a council's, a national park's, the Environment Agency's bathing water profile),
or from what the site already shows (the river, the lake and its size). The second is one sentence the build writes
from this run's own trace of the river network: how many monitored storm overflows are upstream, whose they are,
how many report live, and the nearest. It is written each build, so it cannot go stale, and where the trace finds
nothing it says what was not traced rather than calling the water clean.

No sentence says the water is safe, clean or low risk: an opening describes the place, and the forecast says the
rest. tests/test_openings.py checks the file before a build, and a bad entry is left out with a warning, as a
guide is.
"""

from __future__ import annotations

import logging
import re
import tomllib
from datetime import date
from pathlib import Path

from dipcast import config
from dipcast.overflow_names import plain_name

log = logging.getLogger(__name__)

OPENINGS = config.ROOT / "guides" / "openings" / "openings.toml"
MAX_PLACE = 330   # the hand-written part: one or two sentences
HTTPS = re.compile(r"https://[^\s<>\"']+")
SPOT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
# Words an opening may not use: a safety claim, a verdict on the water, or the tone of an advert. The forecast,
# not the opening, says how the water is; "popular" and the like are a claim nobody here measured.
BANNED = re.compile(r"\b(safe(?:ly|ty)?|clean(?:est)?|clear water|low[- ]risk|risk[- ]free|pristine|unspoil(?:t|ed)|idyllic|"
                    r"stunning|beautiful|breathtaking|perfect|ideal|best|famous|popular|must[- ]visit|hidden gem|crystal)\b",
                    re.IGNORECASE)


class OpeningError(ValueError):
    pass


def sentences(text: str) -> int:
    """How many sentences: full stops, question and exclamation marks that end a sentence (not "St." or "1.5")."""
    return len(re.findall(r"[.!?](?=\s+[A-Z]|\s*$)", text.strip()))


def company(name) -> str:
    """A company's name as the pages write it, with Dŵr Cymru's circumflex (profile.company_name, levels.js)."""
    return re.sub(r"\bDwr Cymru\b", "Dŵr Cymru", str(name or ""))


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def upstream_sentence(spot: dict) -> str:
    """One sentence on what this build's trace found upstream. "" where the forecast failed for another reason, so
    nothing is said rather than something wrong."""
    err = str(spot.get("error") or "")
    if err.startswith("An isolated lake"):   # levels.js, ISOLATED_WHY
        return ("The river network SwimSignal traces draws no river or beck into this lake, so no monitored storm overflow "
                "can be traced to it; small becks it does not draw are not checked.")
    if err:
        return ""
    up = spot.get("upstream_summary") or {}
    n, km = up.get("overflows"), f"{config.MAX_UPSTREAM_KM:g}"
    if n is None:
        return ""
    if n == 0:
        return (f"SwimSignal's trace of the river network finds no monitored storm overflow within {km} km upstream; "
                "farm runoff, wildlife and other bathers are not traced.")
    cos = [company(c) for c in up.get("companies") or [] if c]
    live, s = up.get("with_live_feed"), "" if n == 1 else "s"
    whose = f", {'all ' if n > 1 and len(cos) == 1 else ''}run by {_and(cos)}" if cos else ""
    parts = [f"SwimSignal's trace of the river network finds {'one' if n == 1 else n} monitored storm overflow{s} within {km} km upstream{whose}"]
    # By water: along the river, then across any lake on the way (profile.km_upstream), as the trace counts it.
    by_water = lambda c: float(c.get("distance_km") or 0) + float(c.get("lake_distance_km") or 0)   # noqa: E731
    near = min((c for c in spot.get("contributors") or [] if isinstance(c.get("distance_km"), (int, float))),
               key=by_water, default=None)
    if near and plain_name(near.get("site_name")):
        d, lake = by_water(near), spot.get("kind") == "lake"
        where = (("under 100 m away by water" if lake else "under 100 m upstream") if d < 0.1
                 else f"{d:.1f} km away by water" if lake else f"{d:.1f} km upstream")
        parts.append(f"the nearest, {plain_name(near['site_name'])}, is {where}" if n > 1 else f"it is {plain_name(near['site_name'])}, {where}")
    if isinstance(live, int) and live < n:
        parts.append("it does not report live" if n == 1 else "none of them reports live" if live == 0
                     else f"{n - live} of the {n} do not report live")
    return parts[0] + ("; " + parts[1] if len(parts) > 1 else "") + (", and " + parts[2] if len(parts) > 2 else "") + "."


def parse_entry(raw: dict, what: str) -> dict:
    """One spot's hand-written part, checked: {"place", "sources": [{"name", "url"}], "checked"}. Raises OpeningError."""
    if not isinstance(raw, dict):
        raise OpeningError(f"{what} is not a table")
    if set(raw) - {"text", "sources", "checked"}:
        raise OpeningError(f"{what}: only text, sources and checked, not {', '.join(sorted(set(raw) - {'text', 'sources', 'checked'}))}")
    if not isinstance(raw.get("checked"), date):
        raise OpeningError(f"{what}: checked, the day its pages were last read, is needed (a bare date)")
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise OpeningError(f"{what}: text is needed")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_PLACE:
        raise OpeningError(f"{what}: text is {len(text)} characters; at most {MAX_PLACE}")
    if not 1 <= sentences(text) <= 2:
        raise OpeningError(f"{what}: text is one or two sentences, ending with a full stop")
    if m := BANNED.search(text):
        raise OpeningError(f"{what}: {m[0]!r} is a verdict or an advert's word, not a fact about the place")
    sources = raw.get("sources")
    if not isinstance(sources, list) or not sources:
        raise OpeningError(f"{what}: sources, the pages its facts come from, are needed")
    out = []
    for i, s in enumerate(sources, 1):
        if not isinstance(s, dict) or set(s) != {"name", "url"} or not isinstance(s["name"], str) or not s["name"].strip():
            raise OpeningError(f"{what}: source {i} is {{ name = ..., url = ... }}")
        if not isinstance(s["url"], str) or not HTTPS.fullmatch(s["url"]):
            raise OpeningError(f"{what}: source {i} needs an https url")
        out.append({"name": s["name"].strip(), "url": s["url"]})
    return {"place": text, "sources": out, "checked": raw["checked"].isoformat()}


def load_openings(spot_ids: set[str] | None = None, path: Path = OPENINGS) -> tuple[dict[str, dict], list[str]]:
    """Every entry in guides/openings/openings.toml by spot id, and a warning for each one left out."""
    if not path.is_file():
        return {}, []
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        return {}, [f"{path.name} left out: {e}"]
    out, warnings = {}, []
    for sid, entry in raw.items():
        try:
            if not SPOT_ID.fullmatch(sid):
                raise OpeningError("not a spot id")
            if spot_ids is not None and sid not in spot_ids:
                raise OpeningError("no spot has this id")
            out[sid] = parse_entry(entry, sid)
        except OpeningError as e:
            warnings.append(f"opening {sid} left out: {e}")
    return out, warnings


def attach_openings(results: list[dict], path: Path = OPENINGS) -> dict:
    """Each listed spot's opening onto its forecast: {"place", "upstream", "text", "sources", "checked"}. text is the
    two joined, for the page's description. Returns the count and any warnings."""
    entries, warnings = load_openings({r["id"] for r in results}, path)
    n = 0
    for r in results:
        e = entries.get(r["id"])
        if not e:
            continue
        up = upstream_sentence(r)
        r["opening"] = {**e, "upstream": up, "text": f"{e['place']} {up}".strip()}
        n += 1
    for w in warnings:
        log.warning("%s", w)
    return {"openings": n, "warnings": warnings}
