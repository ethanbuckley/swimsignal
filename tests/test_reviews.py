"""Swimmers' reviews on the static site (src/dipcast/reviews.py): the build publishes what the review
Worker (reviews/) has published, with its photos, from a cache that keeps them between builds; with
the Worker down it publishes the last list again; and the privacy notice and the terms describe
reviews exactly when they are on."""

import json
import sys
from pathlib import Path

import httpx
import pytest

from dipcast import reviews as rv

ROOT = Path(__file__).resolve().parents[1]
URL = "https://swimsignal-reviews.example.workers.dev/"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def review(i, spot="wharfe-burnsall", swam="2026-09-14", photos=0, again=True, **extra):
    return {"id": f"{i:020x}", "spot": spot, "again": again, "swam_on": swam, "text": f"Review {i}", "name": "",
            "photos": [{"w": 1280, "h": 960, "tw": 320, "th": 240}] * photos, "published_at": f"2026-09-{10 + i:02d}T10:00:00Z", **extra}


class Worker:
    """The review Worker's two public answers, and a count of what was asked."""

    def __init__(self, reviews, down=False, bad_photo=None, visits=(), illness=None):
        self.reviews, self.down, self.bad_photo, self.visits, self.asked = reviews, down, bad_photo, list(visits), []
        self.illness = illness

    def __call__(self, url):
        self.asked.append(url)
        if self.down:
            raise httpx.ConnectError("no route to host")
        if url == URL + "published":
            return json.dumps({"generated_at": "2026-10-03T12:00:00Z", "reviews": self.reviews, "visits": self.visits,
                               **({"illness": self.illness} if self.illness is not None else {})}).encode()
        name = url.removeprefix(URL + "photos/")
        return b"<html>not a photo</html>" if name == self.bad_photo else JPEG + name.encode()


def test_off_unless_the_address_is_sound(monkeypatch):
    monkeypatch.delenv(rv.URL_ENV, raising=False)
    assert rv.reviews_url() is None
    for good in (URL, "http://localhost:8787/", "http://127.0.0.1:8787/"):
        monkeypatch.setenv(rv.URL_ENV, good)
        assert rv.reviews_url() == good
    for bad in ("http://swimsignal-reviews.example.workers.dev/", "https://swimsignal-reviews.example.workers.dev",
                'https://x.example/"onload', "https://x.example/path/"):
        monkeypatch.setenv(rv.URL_ENV, bad)
        assert rv.reviews_url() is None, bad


def test_off_writes_a_file_that_says_so_and_nothing_else(tmp_path):
    (tmp_path / "privacy.html").write_text("<h2>The server version</h2>")
    assert rv.write_reviews(tmp_path, "", cache=tmp_path / "cache") == {"on": False}
    assert json.loads((tmp_path / "reviews" / "index.json").read_text())["on"] is False
    assert (tmp_path / "privacy.html").read_text() == "<h2>The server version</h2>"
    assert not (tmp_path / "cache").exists()
    # Switched off after being on: the build's copy of the reviews and their photos goes too.
    rv.write_reviews(tmp_path, URL, get=Worker([review(1, photos=1)]), cache=tmp_path / "cache")
    assert list((tmp_path / "cache" / "photos").iterdir())
    rv.write_reviews(tmp_path, "", cache=tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


def test_published_reviews_and_their_photos_reach_the_site(tmp_path):
    worker = Worker([review(1, swam="2026-08-01", photos=2), review(2, swam="2026-09-20", again=False), review(3, spot="gone-spot", photos=1),
                     {**review(4), "swam_on": "yesterday"}, review(5, swam="2026-09-20")])
    out = rv.write_reviews(tmp_path, URL, spot_ids=["wharfe-burnsall", "another"], get=worker, cache=tmp_path / "cache")
    assert out == {"on": True, "source": "service", "published": 3, "notes": 0, "photos": 2}
    index = json.loads((tmp_path / "reviews" / "index.json").read_text())
    assert index["on"] is True and index["submit"] == URL and index["complete"] is True
    assert list(index["spots"]) == ["wharfe-burnsall"]   # a spot this build does not have is left out
    rows = index["spots"]["wharfe-burnsall"]
    # Newest swim first; the same day, the later published first. The malformed one is left out.
    assert [r["id"] for r in rows] == [f"{5:020x}", f"{2:020x}", f"{1:020x}"]
    assert rows[1]["again"] is False and rows[0]["text"] == "Review 5"
    assert set(rows[0]) == {"id", "again", "swam_on", "text", "name", "photos"}
    assert rows[2]["photos"] == [{"n": 0, "w": 1280, "h": 960, "tw": 320, "th": 240}, {"n": 1, "w": 1280, "h": 960, "tw": 320, "th": 240}]
    photos = sorted(p.name for p in (tmp_path / "reviews" / "photos").iterdir())
    one = f"{1:020x}"
    assert photos == [f"{one}-0-t.jpg", f"{one}-0.jpg", f"{one}-1-t.jpg", f"{one}-1.jpg"]
    assert (tmp_path / "reviews" / "photos" / f"{one}-0.jpg").read_bytes().startswith(b"\xff\xd8\xff")
    assert not any("gone-spot" in u or f"{3:020x}" in u for u in worker.asked)


def visit(i, spot="wharfe-burnsall", seen="2026-10-02", until="2026-10-03", kinds=("busy",), photos=0, **extra):
    return {"id": f"{100 + i:020x}", "spot": spot, "seen_on": seen, "until": until, "kinds": list(kinds), "text": "", "confirmed_on": None,
            "confirmations": 0, "verified": "", "photos": [{"w": 1280, "h": 960, "tw": 320, "th": 240}] * photos, **extra}


def test_notes_on_a_visit_reach_the_site_until_their_last_day(tmp_path):
    notes = [visit(1, kinds=("steps", "busy"), until="2026-11-01", photos=1), visit(2, seen="2026-10-03"),
             visit(3, until="2026-10-02"),                               # ended yesterday
             visit(4, spot="gone-spot"), {**visit(5), "kinds": []},     # a spot not built; no ticks
             visit(6, kinds=("algae",), until="2026-10-09", verified="EA notice, 3 Oct")]
    out = rv.write_reviews(tmp_path, URL, spot_ids=["wharfe-burnsall"], get=Worker([], visits=notes), cache=tmp_path / "cache",
                           today="2026-10-03")
    assert out["notes"] == 3 and out["photos"] == 1
    rows = json.loads((tmp_path / "reviews" / "index.json").read_text())["visits"]["wharfe-burnsall"]
    assert [r["id"] for r in rows] == [f"{102:020x}", f"{106:020x}", f"{101:020x}"]   # newest visit first
    assert rows[1]["verified"] == "EA notice, 3 Oct" and rows[2]["kinds"] == ["steps", "busy"]
    assert set(rows[0]) == {"id", "kinds", "seen_on", "confirmed_on", "confirmations", "until", "text", "verified", "photos"}
    assert sorted(p.name for p in (tmp_path / "reviews" / "photos").iterdir()) == [f"{101:020x}-0-t.jpg", f"{101:020x}-0.jpg"]
    # The next day only the lasting ones are left, and the ended note's photo leaves the cache with it.
    rv.write_reviews(tmp_path, URL, spot_ids=["wharfe-burnsall"], get=Worker([], visits=notes), cache=tmp_path / "cache", today="2026-11-02")
    assert json.loads((tmp_path / "reviews" / "index.json").read_text())["visits"] == {}
    assert not list((tmp_path / "cache" / "photos").iterdir())


def test_photos_are_fetched_once_and_leave_with_their_review(tmp_path):
    cache = tmp_path / "cache"
    worker = Worker([review(1, photos=1), review(2, photos=1)])
    rv.write_reviews(tmp_path / "site", URL, get=worker, cache=cache)
    assert len(worker.asked) == 5   # the list, and two files for each of two photos
    worker.asked.clear()
    rv.write_reviews(tmp_path / "site", URL, get=worker, cache=cache)
    assert worker.asked == [URL + "published"]   # the photos come from the cache
    worker.reviews = [review(2, photos=1)]   # the first was deleted
    rv.write_reviews(tmp_path / "site", URL, get=worker, cache=cache)
    gone = f"{1:020x}"
    assert not list(cache.glob(f"photos/{gone}-*")) and not list((tmp_path / "site" / "reviews" / "photos").glob(f"{gone}-*"))
    assert len(list((tmp_path / "site" / "reviews" / "photos").iterdir())) == 2


def test_with_the_service_down_the_last_list_is_published_again_marked_incomplete(tmp_path):
    cache = tmp_path / "cache"
    rv.write_reviews(tmp_path, URL, get=Worker([review(1, photos=1)]), cache=cache)
    out = rv.write_reviews(tmp_path, URL, get=Worker([], down=True), cache=cache)
    assert out["source"] == "cache" and out["warning"].endswith("did not answer (no route to host); publishing the last list it gave")
    index = json.loads((tmp_path / "reviews" / "index.json").read_text())
    assert index["complete"] is False and len(index["spots"]["wharfe-burnsall"]) == 1
    assert len(list((tmp_path / "reviews" / "photos").iterdir())) == 2   # from the cache
    # Never reached and nothing kept: no reviews, and the page is told why.
    out = rv.write_reviews(tmp_path, URL, get=Worker([], down=True), cache=tmp_path / "empty")
    assert out["source"] == "none" and out["published"] == 0 and "no earlier list is kept" in out["warning"]
    assert json.loads((tmp_path / "reviews" / "index.json").read_text())["complete"] is False


def test_a_file_that_is_not_a_photo_is_left_out(tmp_path):
    one = f"{1:020x}"
    out = rv.write_reviews(tmp_path, URL, get=Worker([review(1, photos=2)], bad_photo=f"{one}-1-t.jpg"), cache=tmp_path / "cache")
    assert out["photos"] == 1 and "1 photo could not be fetched" in out["warning"]
    rows = json.loads((tmp_path / "reviews" / "index.json").read_text())["spots"]["wharfe-burnsall"]
    assert [p["n"] for p in rows[0]["photos"]] == [0]
    assert not (tmp_path / "cache" / "photos" / f"{one}-1-t.jpg").exists()


@pytest.mark.parametrize("push", [False, True])
def test_the_privacy_notice_and_terms_describe_reviews_only_when_they_are_on(tmp_path, push):
    bs = _build_site()
    spots = [{"id": "wharfe-burnsall", "name": "Burnsall", "kind": "river", "upstream_summary": {"overflows": 3}, "days": []}]
    bs.write_pages(tmp_path, spots, root="https://example.org/", push=push)
    before = {p: (tmp_path / p).read_text() for p in ("privacy.html", "terms.html")}
    for page, html in before.items():   # every anchor is still in the pages, so no section can go missing
        assert 'id="reviews"' not in html, page
    assert rv.SHORT_VERSION_BEFORE in before["privacy.html"] and rv.PRIVACY_SECTION_BEFORE in before["privacy.html"]
    assert rv.TERMS_SECTION_BEFORE in before["terms.html"]
    holds = rv.HOLDS_NONE[0 if push else 1]
    assert holds[0] in before["privacy.html"]
    rv.write_reviews(tmp_path, URL, get=Worker([]), cache=tmp_path / "cache")
    privacy, terms = (tmp_path / "privacy.html").read_text(), (tmp_path / "terms.html").read_text()
    assert privacy.count('<h2 id="reviews">Reviews</h2>') == 1 and terms.count('<h2 id="reviews">Reviews</h2>') == 1
    assert privacy.index('id="reviews"') < privacy.index(rv.PRIVACY_SECTION_BEFORE)
    assert holds[1] in privacy and holds[0] not in privacy
    assert rv.SHORT_VERSION_LINE in privacy
    assert 'href="terms.html#reviews"' in privacy and 'href="privacy.html' not in terms.split('id="reviews"')[1].split("</ul>")[0]
    assert ("Alerts" in privacy.split("holds none")[1].split(";")[0]) is push
    # Once only: a page that has its section is left as it is.
    assert rv.with_reviews(privacy, "privacy.html") == privacy and rv.with_reviews(terms, "terms.html") == terms


def test_the_page_loads_the_reviews_script_from_its_build(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "a", "name": "A", "kind": "river", "days": []}], root="https://example.org/")
    stamp = bs.shell_stamp()
    page = (tmp_path / "index.html").read_text()
    sw = (tmp_path / "sw.js").read_text()
    for script in ("reviews.js", "visits.js", "illness.js"):   # the notes and the illness reports after the reviews, whose parts they use
        assert f'<script src="{script}?v={stamp}">' in page
        assert (tmp_path / script).read_bytes() == (bs.TEMPLATE.parent / script).read_bytes()
        assert f"`{script}?v=${{BUILD}}`" in sw
    assert page.index('src="reviews.js') < page.index('src="visits.js') < page.index('src="illness.js')
    assert "/reviews/photos/" in sw


def test_a_failing_photo_service_costs_the_build_little(tmp_path):
    # Every photo fails: after three failures in a row the build stops asking, and publishes the
    # reviews without their photos.
    worker = Worker([review(i, photos=3) for i in range(1, 6)], bad_photo="*")
    worker_get = lambda url: (_ for _ in ()).throw(httpx.ReadTimeout("slow")) if "/photos/" in url else worker(url)
    out = rv.write_reviews(tmp_path, URL, get=worker_get, cache=tmp_path / "cache")
    assert out["published"] == 5 and out["photos"] == 0
    assert "kept failing" in out["warning"]
    # Out of time: past the budget, no more photos are asked for.
    clock = iter([0, 0] + [rv.PHOTO_BUDGET_S + 1] * 100)
    worker = Worker([review(i, photos=1) for i in range(1, 4)])
    out = rv.write_reviews(tmp_path, URL, get=worker, cache=tmp_path / "cache2", now=lambda: next(clock))
    asked = [u for u in worker.asked if "/photos/" in u]
    assert len(asked) == 1 and "ran out of time" in out["warning"]


# ---- reports of illness after a swim: counts only, from five, and their sections only while they are on

ILLNESS = {"on": True, "min": 5, "through": "2026-10-03",
           "spots": {"wharfe-burnsall": {"d30": 6, "d365": 11}, "another": {"d30": None, "d365": 5}}}


def test_the_build_and_the_service_hold_the_same_threshold():
    import re
    rules = (ROOT / "reviews" / "src" / "rules.js").read_text()
    assert int(re.search(r"ILLNESS_MIN = (\d+)", rules).group(1)) == rv.ILLNESS_MIN


def test_only_counts_of_five_or_more_reach_the_site_even_if_the_service_sent_less():
    sent = {**ILLNESS, "spots": {**ILLNESS["spots"], "small": {"d30": 2, "d365": 3}, "odd": {"d30": 4, "d365": 7},
                                 "bad": {"d365": "many"}, "../x": {"d30": None, "d365": 9}, "gone-spot": {"d30": None, "d365": 8}}}
    out = rv.site_illness({"illness": sent}, {"wharfe-burnsall", "another", "small", "odd", "bad", "../x"})
    assert out == {"on": True, "min": 5, "through": "2026-10-03",
                   "spots": {"another": {"d30": None, "d365": 5}, "odd": {"d30": None, "d365": 7}, "wharfe-burnsall": {"d30": 6, "d365": 11}}}
    # A Worker set to a higher threshold is followed; a lower one is not.
    assert list(rv.site_illness({"illness": {**ILLNESS, "min": 10}})["spots"]) == ["wharfe-burnsall"]
    assert rv.site_illness({"illness": {**ILLNESS, "min": 1}})["min"] == 5
    assert rv.site_illness({"illness": {"on": False}}) == {"on": False}
    assert rv.site_illness({}) is None


def _pages(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, [{"id": "wharfe-burnsall", "name": "Burnsall", "kind": "river", "days": []}], root="https://example.org/")
    return {p: (tmp_path / p).read_text() for p in ("privacy.html", "terms.html", "data.html")}


def test_with_reports_on_the_counts_and_every_section_are_published(tmp_path):
    before = _pages(tmp_path)
    for anchor in (rv.DATA_ROW_BEFORE, rv.DATA_SECTION_BEFORE):   # a rewrite of the data page cannot drop the sections unnoticed
        assert anchor in before["data.html"], anchor
    assert rv.ILLNESS_HOLDS_BEFORE in rv.with_reviews(before["privacy.html"], "privacy.html")
    out = rv.write_reviews(tmp_path, URL, spot_ids=["wharfe-burnsall"], get=Worker([], illness=ILLNESS), cache=tmp_path / "cache")
    assert out["illness"] == {"on": True, "spots_shown": 1}
    index = json.loads((tmp_path / "reviews" / "index.json").read_text())
    assert index["illness"] == {"on": True, "min": 5, "through": "2026-10-03", "spots": {"wharfe-burnsall": {"d30": 6, "d365": 11}}}
    data = json.loads((tmp_path / "data" / "illness.json").read_text())
    assert data["spots"] == index["illness"]["spots"] and data["min"] == 5 and "Unverified" in data["note"]
    privacy, terms, page = ((tmp_path / p).read_text() for p in ("privacy.html", "terms.html", "data.html"))
    assert privacy.count('<h2 id="illness">') == 1 and privacy.index('id="reviews"') < privacy.index('id="illness"') < privacy.index(rv.PRIVACY_SECTION_BEFORE)
    assert "Article" in privacy and "9(2)(a)" in privacy and "https://111.nhs.uk/" in privacy
    assert rv.ILLNESS_HOLDS_AFTER in privacy and rv.ILLNESS_SHORT_LINE in privacy
    assert terms.count('<h3 id="illness">') == 1 and terms.index('id="visit-notes"') < terms.index('id="illness"')
    assert page.count('data-file="illness.json"') == 1 and page.count('id="illness-json"') == 1
    assert page.index('data-file="illness.json"') < page.index("</tbody></table></div>") and page.index('id="illness-json"') < page.index('id="credits"')
    assert 'privacy.html#illness' in page and '<td class="num">1 kB</td>' in page.split('data-file="illness.json"')[1].split("</tr>")[0]
    # Once only.
    for name, html in (("privacy.html", privacy), ("terms.html", terms), ("data.html", page)):
        assert rv.with_illness(html, name, size=500) == html


def test_with_reports_off_but_held_only_the_privacy_section_stays(tmp_path):
    _pages(tmp_path)
    (tmp_path / "data" / "illness.json").write_text("{}")   # from an earlier build, when reports were on
    out = rv.write_reviews(tmp_path, URL, get=Worker([], illness={"on": False}), cache=tmp_path / "cache")
    assert out["illness"] == {"on": False, "spots_shown": 0}
    assert "illness" not in json.loads((tmp_path / "reviews" / "index.json").read_text())
    assert not (tmp_path / "data" / "illness.json").exists()
    assert 'id="illness"' in (tmp_path / "privacy.html").read_text()
    assert 'id="illness"' not in (tmp_path / "terms.html").read_text() and "illness" not in (tmp_path / "data.html").read_text()


def test_with_reports_never_on_there_is_no_trace_of_them(tmp_path):
    _pages(tmp_path)
    out = rv.write_reviews(tmp_path, URL, get=Worker([]), cache=tmp_path / "cache")
    assert "illness" not in out
    assert "illness" not in json.loads((tmp_path / "reviews" / "index.json").read_text())
    assert not (tmp_path / "data" / "illness.json").exists()
    for page in ("privacy.html", "terms.html", "data.html"):
        assert "illness" not in (tmp_path / page).read_text().lower(), page
    # Reviews switched off altogether: a data file left from before goes too.
    (tmp_path / "data" / "illness.json").write_text("{}")
    rv.write_reviews(tmp_path, "", cache=tmp_path / "cache")
    assert not (tmp_path / "data" / "illness.json").exists()
