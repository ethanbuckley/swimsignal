"""Choose the spots for a comprehension session (docs/COMPREHENSION-TEST-2026-10.md, section 3) on the
morning it runs, since levels change. Task 2 needs a spot whose headline is low risk with overflows
upstream; task 3 a spot whose page has at least one gap. Reads the published forecast and each spot's
built page, so the headline is the one a participant will see; writes nothing.

    uv run python scripts/pick_test_spots.py --area "Cumbria and the Lake District"

--spots and --pages read a local build instead (site/data/spots.json and site/spot/<id>/index.html).
Note the spot, its headline and the issue time in the session record.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SITE = "https://swimsignal.co.uk/"
USER_AGENT = "SwimSignal comprehension-test spot picker (github.com/ethanbuckley/swimsignal)"
HEADLINE = re.compile(r'id="risk-headline">(.*?)</h2>', re.S)
# The gaps task 3 counts, each as the spot page words it (levels.js, experience.js, index.html), and the
# rule the page itself uses for it. A participant who names any of them has named a gap.
GAPS = {
    "no_live_feed": "an overflow upstream with no live feed",
    "ecoli_out_of_season": "the E. coli estimate is untested this month",
    "ea_advice_not_checked": "today's EA advice not checked",
    "access_unconfirmed": "permission to swim not confirmed",
    "no_access_info": "no access information",
    "lake_no_ecoli": "no E. coli estimate on a lake",
}


def headline(page: str) -> str | None:
    """The spot page's headline as built (prerender_spots), in plain text; None for a page without one."""
    m = HEADLINE.search(page)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None


def gaps(spot: dict) -> list[str]:
    """The keys of GAPS that hold for a spot today, by the page's own rules: a feed missing upstream
    (upstream_summary), the E. coli figure on a river outside May to September (levels.js ecoliTested and
    ecoliUntested), a designated bathing water's advice (levels.js eaUnchecked), and access as
    experience.js words it (an access check, else a guide's facts)."""
    out = []
    up = spot.get("upstream_summary") or {}
    if (up.get("without_live_feed") or 0) > 0:
        out.append("no_live_feed")
    days = spot.get("days") or []
    lake = (spot.get("location") or {}).get("mode") == "lake"
    today = days[0] if days else {}
    if days and not lake and today.get("p_ecoli_gt900") is not None and today.get("in_validated_season") is False:
        out.append("ecoli_out_of_season")
    if days and lake:
        out.append("lake_no_ecoli")
    if not spot.get("unlisted") and spot.get("source") == "designated" and spot.get("classification"):
        out.append("ea_advice_not_checked")
    access = spot.get("access") or {}
    if access.get("status") in ("unconfirmed", "restricted_guidance"):
        out.append("access_unconfirmed")
    elif not access and not (spot.get("guide") or {}).get("facts"):
        out.append("no_access_info")
    return out


def candidates(spots: list[dict], headlines: dict[str, str | None], area: str) -> dict:
    """The area's spots for each task. Task 2: a headline starting "Low risk" and at least one monitored
    overflow upstream, fewest gaps first, so the page's answer is the thing tested. Task 3: at least one
    gap other than the lake's missing estimate (every lake has that one), most gaps first. A spot whose
    page could not be read, or has no headline, is in neither list: a participant would meet a broken
    page. It is named under "unreadable" instead."""
    rows, unreadable = [], []
    for s in spots:
        if s.get("area") != area:
            continue
        if not headlines.get(s["id"]):
            unreadable.append({"id": s["id"], "name": s["name"]})
            continue
        up = (s.get("upstream_summary") or {}).get("overflows") or 0
        rows.append({"id": s["id"], "name": s["name"], "kind": s.get("kind"), "headline": headlines[s["id"]],
                     "overflows": up, "gaps": gaps(s)})
    low = [r for r in rows if r["headline"].startswith("Low risk") and r["overflows"] > 0]
    gapped = [r for r in rows if set(r["gaps"]) - {"lake_no_ecoli"}]
    return {"area": area, "spots": len(rows) + len(unreadable), "unreadable": unreadable,
            "task2": sorted(low, key=lambda r: (len(r["gaps"]), r["name"])),
            "task3": sorted(gapped, key=lambda r: (-len(r["gaps"]), r["name"]))}


def report(picked: dict, generated_at: str | None) -> str:
    """Markdown for the session record: the issue time, then each task's spots."""
    lines = [f"# Test spots, {picked['area']}", "",
             f"Forecast issued {generated_at or 'unknown'}. {picked['spots']} spots in the area. "
             "Check the spot pages again just before the session: a build may have changed a level.", ""]
    if picked["unreadable"]:
        lines += ["**Warning: these pages could not be read or have no headline, so they are left out of both "
                  "lists. Open each one before the session; do not use it until it shows its answer:** "
                  + ", ".join(f"{r['name']} ({SITE}spot/{r['id']}/)" for r in picked["unreadable"]), ""]
    for task, title in (("task2", "Task 2: low risk with overflows upstream"), ("task3", "Task 3: a page with gaps")):
        lines += [f"## {title}", ""]
        if not picked[task]:
            lines += ["None today. " + ("Use a spot from a neighbouring area, and say so in the record." if task == "task2"
                                       else "Choose any spot and count only what its page shows."), ""]
            continue
        lines += ["| Spot | Page | Headline | Overflows upstream | Gaps |", "|---|---|---|---:|---|"]
        for r in picked[task][:5]:
            lines.append(f"| {r['name']} | {SITE}spot/{r['id']}/ | {r['headline'] or 'not built'} | {r['overflows']} | "
                         f"{'; '.join(GAPS[g] for g in r['gaps']) or 'none'} |")
        lines.append("")
    return "\n".join(lines)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:   # noqa: S310 (the site's own https pages)
        return r.read().decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--area", required=True, help="an area heading from spots.html, e.g. 'Cumbria and the Lake District'")
    ap.add_argument("--spots", type=Path, help="a local spots.json instead of the published one")
    ap.add_argument("--pages", type=Path, help="a local site/spot directory instead of the published pages")
    a = ap.parse_args(argv)
    data = json.loads(a.spots.read_text() if a.spots else _get(f"{SITE}data/spots.json"))
    spots = data["spots"]
    if not any(s.get("area") == a.area for s in spots):
        known = sorted({s.get("area") for s in spots if s.get("area")})
        print(f"No spots in area {a.area!r}. Areas: {', '.join(known)}", file=sys.stderr)
        return 2
    heads = {}
    for s in spots:
        if s.get("area") != a.area:
            continue
        try:
            page = (a.pages / s["id"] / "index.html").read_text() if a.pages else _get(f"{SITE}spot/{s['id']}/")
        except OSError:
            page = ""
        heads[s["id"]] = headline(page)
    picked = candidates(spots, heads, a.area)
    if picked["unreadable"]:
        print("warning: no readable headline for " + ", ".join(r["id"] for r in picked["unreadable"])
              + "; left out of both lists", file=sys.stderr)
    print(report(picked, data.get("generated_at")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
