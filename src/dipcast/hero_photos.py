"""The photo that opens a place, for the redesign preview (src/dipcast/site/preview/; docs/DESIGN.md, "A redesign
kept as a preview").

The live page picks it in the browser from a spot's own file (guide.js, guideHero). The preview's lists show a
photo beside every place, and reading 133 files for that would be 133 requests, so the build writes one small index
by the same rule: the guide's first overview photo that is a historical one, carries no labels, and has a credit
and a date. Standard library only, so the local preview server (scripts/preview_redesign.py) can use it without the
build's dependencies.
"""

from __future__ import annotations

import re

FILE = re.compile(r"[a-z0-9][a-z0-9-]{0,78}\.jpe?g")   # guide.js, guideFile
LICENCES = {"https://creativecommons.org/licenses/by-sa/2.0/": "CC BY-SA 2.0"}   # guide.js, GUIDE_LICENCES


def hero(photos: list[dict] | None) -> dict | None:
    """One guide's opening photo as the preview reads it, or None. A photo's size is `w` and `h` in a spot's
    published guide and `width` and `height` in guides/<id>.toml; either is read."""
    for p in photos or []:
        if (p.get("topic") == "overview" and p.get("status") == "historical" and not p.get("labels")
                and p.get("credit") and p.get("taken") and FILE.fullmatch(str(p.get("file") or ""))):
            return {"file": p["file"], "w": p.get("w") or p.get("width") or 640, "h": p.get("h") or p.get("height") or 480,
                    "credit": p["credit"], "taken": str(p["taken"])[:10], "caption": p.get("caption", ""),
                    "title": p.get("title", ""), "source": p.get("source", ""), "licence": p.get("licence", ""),
                    "licence_name": LICENCES.get(p.get("licence", ""), "")}
    return None


def index(results: list[dict]) -> dict[str, dict]:
    """{spot id: its opening photo} for the spots that have one."""
    out = {}
    for r in results:
        h = hero((r.get("guide") or {}).get("photos"))
        if h and r.get("id"):
            out[r["id"]] = h
    return out
