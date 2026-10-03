"""Swimmers' reviews on the static site. reviews/ is the Cloudflare Worker that takes them in and
holds each one until the operator publishes it; this module brings the published ones into the site.

Each build asks the Worker for the published reviews (GET <url>published) and their photos, and
writes them under site/reviews/: index.json, every published review by spot, and photos/, each
photo and its thumbnail. So a visitor who reads reviews asks nothing of the Worker: the files come
from GitHub Pages with the rest of the site, and the page keeps the rule that nothing is fetched
from another site but the map's tiles (docs/DESIGN.md, rule 8). The cost is a delay: a review
published on the moderation page appears at the next build.

The photos are kept between builds in CACHE/reviews (the workflow keeps CACHE with the state), so a
build downloads only the new ones, and one whose review has gone is deleted from the cache too. If
the Worker cannot be reached, the last list it gave (kept beside them) is published again, marked
incomplete; without one, the page says the reviews could not be updated.

The same Worker takes quick notes on a visit (what a spot was like today or yesterday), and the build
publishes the ones still showing in the same file, under "visits", their photos beside the reviews'.
Each note carries `until`, its last day; the build leaves out notes past it, and the page drops each
tick on its own day (visits.js), so a site that is not rebuilt still stops showing them.

Off until the repository variable DIPCAST_REVIEWS_URL is set (reviews/README.md). Then the page
shows the tile, and the privacy notice and the terms gain their reviews sections (with_reviews).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from dipcast import config

log = logging.getLogger(__name__)

URL_ENV = "DIPCAST_REVIEWS_URL"
CACHE = config.CACHE / "reviews"
REVIEW_ID = re.compile(r"[0-9a-f]{20}")
SPOT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")   # the site's rule for a spot's id
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
KIND = re.compile(r"[a-z-]{1,24}")   # a tick's id (reviews/src/rules.js, VISIT_KINDS); the page skips one it does not know
MAX_PHOTO_BYTES = 2_000_000   # more than the Worker accepts (1.5 MB), so only a broken file is refused
# A slow or failing Worker costs the build at most this long in photos, and photos stop after this many
# failures in a row; the reviews still publish, without the photos not fetched, and the next build
# tries those again. The job's limit is 25 minutes, and the forecasts need most of it.
PHOTO_BUDGET_S, PHOTO_FAILURES = 120, 3


def reviews_url() -> str | None:
    """The Worker's address from DIPCAST_REVIEWS_URL, or None (reviews off). An https address ending in
    a slash, or http://localhost or 127.0.0.1 for trying it on this computer (reviews/README.md)."""
    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return None
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?/|http://(localhost|127\.0\.0\.1)(:\d+)?/", url):
        log.warning("%s must be https://host/ (or http://localhost:port/ on this computer): reviews left off", URL_ENV)
        return None
    return url


def _get(url: str, timeout: float = 20, tries: int = 2) -> bytes:
    """One file from the Worker: a second try after a network failure or a 5xx, none after a 4xx."""
    for attempt in range(tries):
        try:
            r = httpx.get(url, timeout=httpx.Timeout(timeout, connect=8))
            r.raise_for_status()
            return r.content
        except httpx.HTTPError as e:
            if attempt == tries - 1 or (isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500):
                raise
            time.sleep(2 * 2**attempt)
    raise AssertionError("unreachable")


def site_entries(published: dict, spot_ids: set[str] | None = None) -> dict[str, list[dict]]:
    """The published reviews by spot, as the page lists them: newest swim first, and only what the page
    shows. A review that is malformed, or for a spot this build does not have, is left out."""
    out: dict[str, list[dict]] = {}
    for r in published.get("reviews") or []:
        try:
            rid, spot, swam = str(r["id"]), str(r["spot"]), str(r["swam_on"])
            if not (REVIEW_ID.fullmatch(rid) and SPOT_ID.fullmatch(spot) and DAY.fullmatch(swam)):
                raise ValueError("bad id, spot or day")
            photos = [{"n": n, "w": int(p["w"]), "h": int(p["h"]), "tw": int(p["tw"]), "th": int(p["th"])}
                      for n, p in enumerate((r.get("photos") or [])[:3])]
            item = {"id": rid, "again": r["again"] is True, "swam_on": swam, "text": str(r.get("text") or ""),
                    "name": str(r.get("name") or ""), "photos": photos, "_at": str(r.get("published_at") or "")}
        except (KeyError, TypeError, ValueError) as e:
            log.warning("a published review was left out: %s", e)
            continue
        if spot_ids is None or spot in spot_ids:
            out.setdefault(spot, []).append(item)
    for items in out.values():
        items.sort(key=lambda x: (x["swam_on"], x["_at"]), reverse=True)
        for x in items:
            del x["_at"]
    return dict(sorted(out.items()))


def london_today() -> str:
    return datetime.now(ZoneInfo("Europe/London")).date().isoformat()


def site_visits(published: dict, spot_ids: set[str] | None = None, today: str | None = None) -> dict[str, list[dict]]:
    """The notes on a visit still showing, by spot, newest visit first: what the page needs and no
    more. A malformed note, one for a spot this build does not have, or one past its last day is left out."""
    today = today or london_today()
    out: dict[str, list[dict]] = {}
    for v in published.get("visits") or []:
        try:
            vid, spot, seen, until = str(v["id"]), str(v["spot"]), str(v["seen_on"]), str(v["until"])
            confirmed = v.get("confirmed_on")
            if not (REVIEW_ID.fullmatch(vid) and SPOT_ID.fullmatch(spot) and DAY.fullmatch(seen) and DAY.fullmatch(until)
                    and (confirmed is None or DAY.fullmatch(str(confirmed)))):
                raise ValueError("bad id, spot or day")
            kinds = [str(k) for k in v["kinds"] if KIND.fullmatch(str(k))]
            if not kinds:
                raise ValueError("no ticks")
            photos = [{"n": n, "w": int(p["w"]), "h": int(p["h"]), "tw": int(p["tw"]), "th": int(p["th"])}
                      for n, p in enumerate((v.get("photos") or [])[:1])]
            item = {"id": vid, "kinds": kinds, "seen_on": seen, "confirmed_on": confirmed, "confirmations": int(v.get("confirmations") or 0),
                    "until": until, "text": str(v.get("text") or ""), "verified": str(v.get("verified") or ""), "photos": photos}
        except (KeyError, TypeError, ValueError) as e:
            log.warning("a note on a visit was left out: %s", e)
            continue
        if until >= today and (spot_ids is None or spot in spot_ids):
            out.setdefault(spot, []).append(item)
    for items in out.values():
        items.sort(key=lambda x: (x["seen_on"], x["id"]), reverse=True)
    return dict(sorted(out.items()))


def _is_jpeg(data: bytes) -> bool:
    return 3 < len(data) <= MAX_PHOTO_BYTES and data[:3] == b"\xff\xd8\xff"


def write_reviews(site: Path, url: str | None = None, *, spot_ids=None, fetch: bool = True, get=_get,
                  cache: Path | None = None, now=time.monotonic, today: str | None = None) -> dict:
    """site/reviews/: index.json and the photos, and the reviews sections of the privacy notice and the
    terms (written by write_pages before this). Returns what the build log reports. With reviews off,
    index.json says so, nothing else is written, and the cache is emptied: reviews switched off leave
    no copy behind. fetch=False (a build without --refresh) asks the Worker for nothing and publishes
    the cached list and photos."""
    url = reviews_url() if url is None else url
    cache = CACHE if cache is None else cache
    out = site / "reviews"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    if not url:
        shutil.rmtree(cache, ignore_errors=True)
        (out / "index.json").write_text(json.dumps({"generated_at": generated, "on": False}))
        return {"on": False}
    photos_cache = cache / "photos"
    photos_cache.mkdir(parents=True, exist_ok=True)
    report: dict = {"on": True, "source": "service"}
    published = None
    if fetch:
        try:
            published = json.loads(get(url + "published"))
            if not isinstance(published, dict) or not isinstance(published.get("reviews"), list):
                raise TypeError("not a list of reviews")
            (cache / "published.json").write_text(json.dumps(published))
        except Exception as e:  # noqa: BLE001 - reviews beside the forecast must not sink the build
            published = None
            report["warning"] = f"reviews: the review service did not answer ({e})"
    if published is None:
        try:
            published = json.loads((cache / "published.json").read_text())
            report["source"] = "cache"
        except (OSError, ValueError):
            published = {"reviews": []}
            report["source"] = "none"
        if fetch:
            report["warning"] += ("; publishing the last list it gave" if report["source"] == "cache"
                                  else "; no earlier list is kept, so the site shows none this time")
    ids = None if spot_ids is None else set(map(str, spot_ids))
    spots, visits = site_entries(published, ids), site_visits(published, ids, today)

    wanted, missing, failed, stop = set(), 0, 0, now() + PHOTO_BUDGET_S
    for items in [*spots.values(), *visits.values()]:
        for r in items:
            kept = []
            for p in r["photos"]:
                names = [f"{r['id']}-{p['n']}.jpg", f"{r['id']}-{p['n']}-t.jpg"]
                for name in names:
                    f = photos_cache / name
                    if f.exists() or not fetch or failed >= PHOTO_FAILURES or now() > stop:
                        continue
                    try:
                        data = get(url + "photos/" + name)
                        if not _is_jpeg(data):
                            raise ValueError("not a JPEG")
                        f.write_bytes(data)
                        failed = 0
                    except Exception as e:  # noqa: BLE001 - the review is shown without that photo
                        failed += 1
                        log.warning("review photo %s: %s", name, e)
                if all((photos_cache / name).exists() for name in names):
                    kept.append(p)
                    wanted.update(names)
                else:
                    missing += 1
            r["photos"] = kept
    for f in photos_cache.glob("*.jpg"):   # a deleted review's photos leave the cache too
        if f.name not in wanted:
            f.unlink()
    (out / "photos").mkdir()
    for name in sorted(wanted):
        shutil.copyfile(photos_cache / name, out / "photos" / name)
    complete = report["source"] == "service" or not fetch
    (out / "index.json").write_text(json.dumps({"generated_at": generated, "on": True, "submit": url, "complete": complete,
                                                "spots": spots, "visits": visits}, ensure_ascii=False, separators=(",", ":")))
    for page in ("privacy.html", "terms.html"):
        p = site / page
        if p.exists():
            p.write_text(with_reviews(p.read_text(), page))
    report.update(published=sum(len(v) for v in spots.values()), notes=sum(len(v) for v in visits.values()), photos=len(wanted) // 2)
    if missing:
        why = ("; the photo service kept failing, so the rest waited" if failed >= PHOTO_FAILURES
               else "; the photos ran out of time" if now() > stop else "")
        report.setdefault("warning", f"reviews: {missing} photo{'' if missing == 1 else 's'} could not be fetched and "
                                     f"{'is' if missing == 1 else 'are'} left out until the next build{why}")
    return report


# ------------------------------------------------------------------------------ the pages' words
# With reviews on, the privacy notice gains a section on them, a line in its short version, and the
# end of "SwimSignal holds none" (the sentence alerts also change, so both of its forms are here);
# the terms gain the review rules. A test checks that every anchor is still in the pages, so a rewrite
# of a page cannot leave a reviews section out unnoticed.

PRIVACY_SECTION_BEFORE = "<h2>The server version</h2>"
TERMS_SECTION_BEFORE = "<h2>Changes to these terms</h2>"
SHORT_VERSION_BEFORE = "<li>Opening the site sends your IP address"
SHORT_VERSION_LINE = ("<li>If you write a review, it is checked, then published on the spot's page with the name you chose. "
                      "A quick note on a visit is published without a name, and is deleted a few days to a month later. "
                      "You can delete either from the browser you sent it from.</li>\n")
HOLDS_NONE = [   # (as the notice has it, with reviews on); with alerts on first, as the push swap leaves it
    ("SwimSignal holds none except, if you turn on alerts, the record described under Alerts, which turning them off deletes;",
     ("SwimSignal holds none except, if you turn on alerts, the record described under Alerts, which turning them off deletes, "
      "and the reviews people send, described under Reviews;")),
    ("SwimSignal holds none, as described above;",
     "SwimSignal holds none except the reviews people send, described under Reviews;"),
]

REVIEWS_PRIVACY = (
    '<h2 id="reviews">Reviews</h2>\n'
    "<p>If you write a review of a spot, your browser sends SwimSignal's review service what you entered: whether you "
    "would swim there again, the day you swam, what you wrote, the name you chose to show, if any, and any photos. Before "
    "sending, the page shrinks each photo and saves it again on your device, which leaves out its location and the other "
    "details your camera recorded; the service removes any such details that remain. The service records when the review "
    "arrived. To limit how many reviews and reports can come from one connection, it counts them under a scrambled form "
    "of your IP address, made with a secret key, and deletes the counts within three days; it does not store the address "
    "itself.</p>\n"
    "<p>The operator reads each review before it is published, and deletes one that breaks the "
    '<a href="terms.html#reviews">review rules</a>. A published review, with its name and photos, appears on the spot\'s '
    "page and in the site's public files, for anyone to see. The basis is your consent: you choose to send a review, and "
    "you can withdraw it by deleting the review.</p>\n"
    "<p>Your browser keeps a copy of your review, and a key to it, in its local storage, so that it can show you the "
    "review while it waits and let you delete it at any time. While it waits, the spot's page asks the review service "
    "whether it is still waiting, sending only the review's identifier. Deleting it removes it from the review service "
    "at once and from the site at its next update, within a few hours; the copy the site's build keeps for its own use, "
    "which is not published, is gone within about a week. A browser can forget the key: Safari, for one, clears a "
    "site's storage after seven days without a visit, unless the site is on your Home Screen. Then, or from another "
    "device, email the operator to have the review deleted. If you report a review, the service keeps the reason you "
    "chose and the time, and nothing about you, until the operator has dealt with it.</p>\n"
    "<p>The review service runs on Cloudflare Workers, with the reviews in a Cloudflare D1 database and the photos in "
    "Workers KV. Cloudflare may handle them outside the UK under its own safeguards, and it sees your IP address when you "
    "send, delete or report a review, and when the page asks after one you sent, as any web server would; "
    '<a href="https://www.cloudflare.com/privacypolicy/">Cloudflare\'s privacy policy</a> applies to that. Published '
    "reviews and their photos are served by GitHub with the rest of the site, so reading them sends nothing to "
    "Cloudflare.</p>\n"
    '<h3 id="visit-notes">Notes on a visit</h3>\n'
    "<p>If you leave a quick note on what a spot was like, your browser sends the review service the spot, whether you "
    "were there today or yesterday, the things you ticked, any words you added and any photo, prepared as a review's "
    "photos are. A note has no name. A note of ticks alone is published on the spot's page at the site's next update "
    "without being read first; one with words or a photo is read by the operator first. If another swimmer says a note "
    "is still right, their browser sends only the note's identifier.</p>\n"
    "<p>Each thing you tick is shown for a set time: a day or two for how busy it was or what the water looked like, a "
    "week for algae, and up to a month for damage, closures and signs, which starts again if another swimmer confirms "
    "it. When everything on a note has ended, the review service deletes the note and its photo within two days, and "
    "the site drops it at its next update. Your browser keeps a copy and a key, so that you can delete the note sooner, "
    "as with a review. The rest of this section applies to notes as it does to reviews.</p>\n\n")

REVIEWS_TERMS = (
    '<h2 id="reviews">Reviews</h2>\n'
    "<p>You can review a spot you have swum at: say whether you would swim there again, when you swam and what it was "
    "like, and add up to three photos. We read every review before it is published, and we may decline or remove any "
    "review at any time without giving a reason.</p>\n"
    "<p>By sending a review you confirm that:</p>\n<ul>\n"
    "<li>it is your own honest account of swimming at that spot;</li>\n"
    "<li>you took the photos, and anyone who can be recognised in them has agreed to their being published;</li>\n"
    "<li>it does not name or identify anyone else, and makes no claim about a person or business that you could not "
    "back up;</li>\n"
    "<li>it contains nothing unlawful, hateful, threatening or sexual, no advertising and no web addresses.</li>\n</ul>\n"
    "<p>You keep the rights in what you write and in your photos. You give us permission to publish them on SwimSignal, "
    'with the name you chose or as "A swimmer", for as long as the review is up, and to resize them. They are not part '
    'of the data that may be reused under "Using the site, its data and its code". You can delete your review from the '
    "browser you sent it from, or by emailing us.</p>\n"
    "<p>Reviews are swimmers' own views, not ours. A review is one person's day at the water: it is not a water test, "
    "it does not change the forecast, and a good review does not mean the water is clean or safe when you go. If you "
    "think a review breaks these rules, use Report beside it, or email us.</p>\n"
    '<h3 id="visit-notes">Notes on a visit</h3>\n'
    "<p>You can also leave a quick note on a spot you were at today or yesterday: tick what you found, and add a few "
    "words or one photo if you like. A note of ticks alone appears at the site's next update without being read first; "
    "one with words or a photo is read before it appears. The rules for reviews apply to notes too, and we may remove "
    "any note at any time.</p>\n"
    "<p>A note says what one person found on one day, and it ends after a set time. A note of pollution or algae is what "
    "one swimmer saw, not a test, and the site says so unless we have verified it from an official source, which we "
    "name. Notes never change the forecast, and a good note does not mean a warning has ended. If you think the water is "
    "polluted, report it to the Environment Agency on 0800 80 70 60 or, in Wales, to Natural Resources Wales on "
    "0300 065 3000, both at any hour.</p>\n\n")


def with_reviews(html: str, page: str) -> str:
    """privacy.html or terms.html with its reviews sections; any other page, or one that has them, as it is."""
    if 'id="reviews"' in html:
        return html
    if page == "terms.html":
        return html.replace(TERMS_SECTION_BEFORE, REVIEWS_TERMS + TERMS_SECTION_BEFORE, 1)
    if page != "privacy.html":
        return html
    html = html.replace(SHORT_VERSION_BEFORE, SHORT_VERSION_LINE + SHORT_VERSION_BEFORE, 1)
    for before, after in HOLDS_NONE:
        if before in html:
            html = html.replace(before, after, 1)
            break
    else:
        log.warning("privacy notice: no 'SwimSignal holds none' sentence to add the reviews to")
    return html.replace(PRIVACY_SECTION_BEFORE, REVIEWS_PRIVACY + PRIVACY_SECTION_BEFORE, 1)
