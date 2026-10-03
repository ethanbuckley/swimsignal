"""Practical guides: where to park, the path to the water, where to get in and out, toilets,
changing, fees and opening times. The questions a pollution forecast cannot answer.

One file per spot, guides/<spot id>.toml, written by hand (guides/README.md has the format and
how to check a fact). Every fact says where it came from, and the page shows it:

- **confirmed**: the landowner's, operator's or council's own published page says so (``source``,
  an https address), or someone from SwimSignal saw it on site (``seen``, the day). A desk check of
  a page is not an inspection: the page says which it was.
- **suggested**: a swimmer told us (``from``, who, in words they agreed to; ``on``, the day). It
  has not been checked, and the page says so beside it.

Photos sit in guides/photos/, with a caption, who took them, the day, and up to nine numbered
labels placed on the picture as percentages across and down. The build copies the photos a guide
uses into site/guides/photos/ and attaches each guide to its spot in spots.json.

A file that breaks these rules is left out of the build with a warning, rather than stopping the
forecasts publishing; tests/test_guides.py checks every file in guides/ before a build runs.
"""

from __future__ import annotations

import logging
import re
import shutil
import tomllib
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dipcast import config

log = logging.getLogger(__name__)

GUIDES = config.ROOT / "guides"
# The topics, in the order a swimmer meets them, and their headings on the page (guide.js keeps
# the same list). Anything else in a file is an error, so a typo cannot hide a fact.
TOPICS = {
    "parking": "Parking",
    "path": "Path to the water",
    "entry": "Getting in",
    "exit": "Getting out",
    "toilets": "Toilets",
    "changing": "Changing",
    "fees": "Fees and booking",
    "hours": "Opening times",
    "rules": "Who can swim",
}
STATUSES = ("confirmed", "suggested")
HOW = ("desk", "visit")
MAX_TEXT, MAX_CAPTION, MAX_LABEL, MAX_LABELS, MAX_PHOTOS = 400, 160, 60, 9, 6
SPOT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")   # the site's rule for a spot's id
PHOTO = re.compile(r"[a-z0-9][a-z0-9-]{0,78}\.jpe?g")
HTTPS = re.compile(r"https://[^\s<>\"']+")


class GuideError(ValueError):
    pass


def _day(v, what: str, today: date) -> str:
    """A TOML date (written bare, 2026-10-03), not later than today, as an ISO string."""
    if not isinstance(v, date):
        raise GuideError(f"{what} must be a date written as 2026-10-03, not {v!r}")
    if v > today:
        raise GuideError(f"{what} is in the future ({v})")
    return v.isoformat()


def _text(v, what: str, limit: int) -> str:
    if not isinstance(v, str) or not v.strip():
        raise GuideError(f"{what} is missing")
    v = " ".join(v.split())
    if len(v) > limit:
        raise GuideError(f"{what} is {len(v)} characters; keep it under {limit}")
    return v


def _only(d: dict, keys: set[str], what: str) -> None:
    extra = set(d) - keys
    if extra:
        raise GuideError(f"{what} has unknown field(s): {', '.join(sorted(extra))}")


def _provenance(raw: dict, what: str, today: date) -> dict:
    """Who says so: a published page or a visit (confirmed), or a swimmer (suggested)."""
    status = raw.get("status")
    if status not in STATUSES:
        raise GuideError(f"{what}: status must be confirmed or suggested, not {status!r}")
    out = {"status": status}
    if status == "confirmed":
        if "from" in raw or "on" in raw:
            raise GuideError(f"{what}: from and on are for a swimmer's suggestion, not a confirmed fact")
        if "source" in raw:
            if not isinstance(raw["source"], str) or not HTTPS.fullmatch(raw["source"]):
                raise GuideError(f"{what}: source must be an https address")
            out["source"] = raw["source"]
            out["source_name"] = _text(raw.get("source_name"), f"{what}: source_name (who publishes the page)", 80)
        if "seen" in raw:
            out["seen"] = _day(raw["seen"], f"{what}: seen", today)
        if "source" not in out and "seen" not in out:
            raise GuideError(f"{what}: a confirmed fact needs a source page or the day it was seen on site")
    else:
        if {"source", "source_name", "seen"} & set(raw):
            raise GuideError(f"{what}: a swimmer's suggestion has from and on, not a source; once checked it becomes confirmed")
        out["from"] = _text(raw.get("from"), f"{what}: from (who suggested it)", 80)
        out["on"] = _day(raw.get("on"), f"{what}: on", today)
    return out


def parse_guide(raw: dict, spot_id: str, photos_dir: Path, today: date | None = None) -> dict:
    """One guide file, read and checked, in the shape the page draws. Raises GuideError."""
    today = today or datetime.now(ZoneInfo("Europe/London")).date()
    _only(raw, {"checked", "how", "fact", "photo"}, "the guide")
    guide = {"checked": _day(raw.get("checked"), "checked", today)}
    if raw.get("how") not in HOW:
        raise GuideError(f"how must be desk (from published pages) or visit (someone went), not {raw.get('how')!r}")
    guide["how"] = raw["how"]
    facts = raw.get("fact") or []
    if not isinstance(facts, list) or not facts:
        raise GuideError("a guide needs at least one [[fact]]")
    guide["facts"] = []
    for i, f in enumerate(facts, 1):
        what = f"fact {i}"
        if not isinstance(f, dict):
            raise GuideError(f"{what} is not a table")
        _only(f, {"topic", "text", "status", "source", "source_name", "seen", "from", "on", "lat", "lon"}, what)
        if f.get("topic") not in TOPICS:
            raise GuideError(f"{what}: topic must be one of {', '.join(TOPICS)}, not {f.get('topic')!r}")
        fact = {"topic": f["topic"], "text": _text(f.get("text"), f"{what}: text", MAX_TEXT), **_provenance(f, what, today)}
        if ("lat" in f) != ("lon" in f):
            raise GuideError(f"{what}: give both lat and lon, or neither")
        if "lat" in f:
            lat, lon = f["lat"], f["lon"]
            if not all(isinstance(x, (int, float)) for x in (lat, lon)) or not (49.8 < lat < 55.9 and -6.5 < lon < 2.0):
                raise GuideError(f"{what}: lat and lon must be decimal degrees in England")
            fact["lat"], fact["lon"] = round(float(lat), 5), round(float(lon), 5)
        guide["facts"].append(fact)
    # Facts in the order of the topics; within a topic, confirmed before suggested, as written.
    order = list(TOPICS)
    guide["facts"].sort(key=lambda f: (order.index(f["topic"]), f["status"] != "confirmed"))
    photos = raw.get("photo") or []
    if not isinstance(photos, list) or len(photos) > MAX_PHOTOS:
        raise GuideError(f"up to {MAX_PHOTOS} [[photo]] tables")
    guide["photos"] = []
    for i, p in enumerate(photos, 1):
        what = f"photo {i}"
        if not isinstance(p, dict):
            raise GuideError(f"{what} is not a table")
        _only(p, {"file", "caption", "credit", "taken", "width", "height", "status", "from", "on", "seen",
                  "source", "source_name", "label"}, what)
        name = p.get("file")
        if not isinstance(name, str) or not PHOTO.fullmatch(name):
            raise GuideError(f"{what}: file must be a lower-case name ending .jpg in guides/photos/")
        if not (photos_dir / name).is_file():
            raise GuideError(f"{what}: guides/photos/{name} does not exist")
        w, h = p.get("width"), p.get("height")
        if not all(isinstance(x, int) and 0 < x <= 4000 for x in (w, h)):
            raise GuideError(f"{what}: width and height in pixels are needed, so the page keeps its place while it loads")
        photo = {"file": name, "w": w, "h": h, "caption": _text(p.get("caption"), f"{what}: caption", MAX_CAPTION),
                 "credit": _text(p.get("credit"), f"{what}: credit (who took it)", 80),
                 "taken": _day(p.get("taken"), f"{what}: taken", today), **_provenance(p, what, today), "labels": []}
        labels = p.get("label") or []
        if not isinstance(labels, list) or len(labels) > MAX_LABELS:
            raise GuideError(f"{what}: up to {MAX_LABELS} labels")
        for n, lab in enumerate(labels, 1):
            lw = f"{what}, label {n}"
            if not isinstance(lab, dict):
                raise GuideError(f"{lw} is not a table")
            _only(lab, {"x", "y", "text"}, lw)
            x, y = lab.get("x"), lab.get("y")
            if not all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in (x, y)):
                raise GuideError(f"{lw}: x and y are percentages across and down the photo, 0 to 100")
            photo["labels"].append({"x": round(float(x), 1), "y": round(float(y), 1), "text": _text(lab.get("text"), f"{lw}: text", MAX_LABEL)})
        guide["photos"].append(photo)
    return guide


def load_guides(spot_ids: set[str] | None = None, root: Path = GUIDES, today: date | None = None) -> tuple[dict[str, dict], list[str]]:
    """Every guide in guides/, by spot id, and a warning for each file left out."""
    guides, warnings = {}, []
    for path in sorted(root.glob("*.toml")) if root.is_dir() else []:
        sid = path.stem
        try:
            if not SPOT_ID.fullmatch(sid):
                raise GuideError("the file name must be the spot's id")
            if spot_ids is not None and sid not in spot_ids:
                raise GuideError("no spot has this id")
            with path.open("rb") as fh:
                guides[sid] = parse_guide(tomllib.load(fh), sid, root / "photos", today)
        except (GuideError, tomllib.TOMLDecodeError) as e:
            warnings.append(f"guide {path.name} left out: {e}")
    return guides, warnings


def attach_guides(results: list[dict], root: Path = GUIDES, today: date | None = None) -> dict:
    """Each spot's guide onto its forecast, for spots.json. Returns the count and any warnings."""
    guides, warnings = load_guides({r["id"] for r in results}, root, today)
    for r in results:
        if r["id"] in guides:
            r["guide"] = guides[r["id"]]
    for w in warnings:
        log.warning("%s", w)
    return {"guides": len(guides), "warnings": warnings}


def copy_photos(site: Path, results: list[dict], root: Path = GUIDES) -> int:
    """The photos the published guides use, into site/guides/photos/; no others."""
    out = site / "guides" / "photos"
    if out.exists():
        shutil.rmtree(out)
    names = {p["file"] for r in results for p in (r.get("guide") or {}).get("photos", [])}
    if names:
        out.mkdir(parents=True)
    for name in names:
        shutil.copy(root / "photos" / name, out / name)
    return len(names)
