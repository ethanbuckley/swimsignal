"""The site's overflow history pages, spot/<id>/profile/ (docs/MARKETS-2026-10.md, T6), and the page for
clubs, centres and leaders, clubs.html (T7). The profile pages are written from data/upstream/<id>.json and
the annual returns, so these tests give both on disk, made up; the real Ilkley page was checked by hand
against the returns (PR body)."""
import json
import re
import sys
from html import unescape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as bs

from dipcast import profile as pf

SPOTS = [
    {"id": "wharfe-ilkley", "name": "Wharfe & Ilkley", "kind": "river", "upstream_summary": {"overflows": 2}, "days": []},
    {"id": "tarn", "name": "A Tarn", "kind": "lake", "days": [],
     "error": "An isolated lake with no river connection in the network: storm overflows cannot reach it by water."},
    {"id": "beck", "name": "A Beck", "kind": "river", "upstream_summary": {"overflows": 0}, "days": []},
    {"id": "gone", "name": "Lost list", "kind": "river", "upstream_summary": {"overflows": 4}, "days": []},
    {"id": "failed", "name": "No forecast", "kind": "river", "days": [], "error": "forecast failed: open-meteo request failed"},
]


def upstream_file(site: Path) -> None:
    (site / "data" / "upstream").mkdir(parents=True, exist_ok=True)
    rows = [{"site_id": "B2", "site_name": "Bridge Lane/CSO", "company": "Yorkshire Water", "distance_km": 21.8,
             "lake_distance_km": 0.0, "travel_h": 12.1, "weight": 0.003, "has_live": False},
            {"site_id": "A1", "site_name": "GRASSINGTON/STW", "company": "Yorkshire Water", "distance_km": 0.4,
             "lake_distance_km": 0.1, "travel_h": 0.3, "weight": 0.98, "has_live": True}]
    (site / "data" / "upstream" / "wharfe-ilkley.json").write_text(json.dumps({"id": "wharfe-ilkley", "overflows": rows}))


def returns(path: Path) -> Path:
    rows = []
    for y in pf.YEARS:
        rows.append({"site_id": "A1", "year": y, "spills": 10, "spill_hours": 20.0, "edm_operational_pct": 100.0})
        if y >= 2023:
            rows.append({"site_id": "B2", "year": y, "spills": 2, "spill_hours": 5.0, "edm_operational_pct": 67.0})
    pd.DataFrame(rows).to_parquet(path)
    return path


def text(page: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", page.split("<main", 1)[1].split("</main>")[0])))


def test_a_profile_page_joins_the_spots_overflows_to_their_returns(tmp_path):
    upstream_file(tmp_path)
    for s in SPOTS:
        (tmp_path / "spot" / s["id"]).mkdir(parents=True)
    assert bs.write_profiles(tmp_path, SPOTS, token="abcdefghij0123456789", returns=returns(tmp_path / "r.parquet")) == 1
    page = (tmp_path / "spot" / "wharfe-ilkley" / "profile" / "index.html").read_text()
    assert "<title>Overflow history: Wharfe &amp; Ilkley · SwimSignal</title>" in page and '<base href="../../../">' in page
    assert "cloudflareinsights" in page and '<header class="top">' in page and 'class="site-foot"' in page
    words = text(page)
    # The caveat first, before any figure; the credits last; never "safe".
    assert words.index("It is not a water test") < words.index("In short") < words.index("Sources and credits")
    assert pf.CREDITS in words and "safe" not in words.lower()
    assert "2 monitored storm overflows drain into the water within 60 km upstream; 1 of them within 10 km." in words
    assert "1 of them report live" in words and "The nearest is 0.5 km upstream." in words   # river and lake together
    # Each year: 2021 has A1 alone; 2025 both, with hours weighted by reach.
    assert re.search(r"<tr><td>2021</td><td class=\"num\">1</td><td class=\"num\">10</td><td class=\"num\">20</td>", page)
    assert re.search(r"<tr><td>2025</td><td class=\"num\">2</td><td class=\"num\">12</td><td class=\"num\">25</td><td class=\"num\">20</td>", page)
    # The overflows, most reach first: the plain name, then the company's own and the id (levels.js's
    # overflowNames), with the phone layout's labels.
    a1, b2 = page.index("Grassington sewage works overflow"), page.index("Bridge Lane storm overflow")
    assert a1 < b2 and '<span class="muted">Grassington/STW · A1</span>' in page
    assert '<td class="num" data-l="Reach">&lt;1%</td>' in page and '<td class="num" data-l="Monitor uptime 2025">67%</td>' in page
    assert '<td class="num" data-l="Hours away">under 1</td>' in page and '<td class="num" data-l="Spills 2023">2</td>' in page
    # The short pages say why there is no list.
    short = {s["id"]: text((tmp_path / "spot" / s["id"] / "profile" / "index.html").read_text()) for s in SPOTS[1:]}
    assert "No river flows into this lake" in short["tarn"] and pf.OTHER_RISKS in short["tarn"]
    assert "No monitored storm overflow was found within 60 km upstream" in short["beck"] and pf.OTHER_RISKS in short["beck"]
    assert "not in this update" in short["gone"] and "has no forecast in this update" in short["failed"]
    assert all("It is not a water test" in t and "In short" not in t for t in short.values())


def test_without_the_annual_returns_the_pages_still_list_the_overflows(tmp_path):
    upstream_file(tmp_path)
    (tmp_path / "spot" / "wharfe-ilkley").mkdir(parents=True)
    assert bs.write_profiles(tmp_path, SPOTS[:1], returns=tmp_path / "missing.parquet") == 1
    words = text((tmp_path / "spot" / "wharfe-ilkley" / "profile" / "index.html").read_text())
    assert "Grassington/STW" in words and "2021 0 0 0 0" in words


def test_write_pages_writes_a_profile_for_every_spot_page_and_lists_them(tmp_path):
    (tmp_path / "data").mkdir()
    upstream_file(tmp_path)
    bs.write_pages(tmp_path, SPOTS[:3] + [{"id": "Bad Id", "name": "Odd", "kind": "river", "days": []}],
                   root="https://example.org/", day="2026-10-06")
    for i in ("wharfe-ilkley", "tarn", "beck"):
        assert (tmp_path / "spot" / i / "profile" / "index.html").exists(), i
    sm = (tmp_path / "sitemap.xml").read_text()
    assert "<loc>https://example.org/spot/tarn/profile/</loc>" in sm and "<loc>https://example.org/clubs.html</loc>" in sm
    # Linked from the spot's page (its overflows tile) and the organisers' table, for a spot with a page.
    app = (bs.TEMPLATE.parent / "index.html").read_text()
    assert "<a href=\"spot/${d.id}/profile/\">Overflow history, 2021 to 2025</a>" in app
    assert "spot/${esc(s.id)}/profile/\">Overflow history, 2021 to 2025</a>" in (bs.TEMPLATE.parent / "organisers.js").read_text()
    # Not on the data page, which lists data files, and not stored for offline use.
    assert "/profile/" not in (tmp_path / "data.html").read_text() and "profile" not in (bs.TEMPLATE.parent / "sw.js").read_text()


def action_lines() -> dict:
    js = (bs.TEMPLATE.parent / "levels.js").read_text()
    out = {k: re.search(rf"\b{k}: '([^']+)'", js).group(1) for k in ("moderate", "high")}
    out["very high"] = re.search(r"veryHighAction = when => `(Avoid swimming here)\$\{[^}]*\}(: [^`]+)`", js).expand(r"\1\2")
    out["plain"] = re.search(r"PLAIN_ACTION = '([^']+)'", js).group(1)
    out["other"] = re.search(r"OTHER_RISKS = '([^']+)'", js).group(1)
    return out


def test_the_clubs_page_uses_the_sites_own_words_and_says_its_limits_first(tmp_path):
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/", day="2026-10-06")
    page = (tmp_path / "clubs.html").read_text()
    assert "<title>Clubs, centres and leaders · SwimSignal</title>" in page and 'href="/' not in page
    words = text(page)
    for k, line in action_lines().items():
        assert line in words, k
    assert words.index("What it cannot do") < words.index("The same level, different exposure")
    assert "It is a forecast, not a water test." in words and "0800 80 70 60" in words
    for name in ("Swimming", "Ghyll scrambling and gorge walking", "Kayaking, canoeing and paddleboarding",
                 "Dinghy sailing and windsurfing", "Rowing"):
        assert f"<dt>{name}</dt>" in page, name
    # Quotes, word for word as their pages had them on 6 Oct 2026, each linked to its source.
    for q in ('"Has there been heavy rainfall or extended dry periods in recent days?"',
              '"Are there CSOs upstream of your paddling location?"',
              '"No water based activity should proceed if there are any concerns around water contamination in the planned location."'):
        assert q in words, q
    for href in ("https://paddleuk.org.uk/water-quality-dont-get-sick-doing-what-you-love/",
                 "https://www.scouts.org.uk/volunteers/running-your-section/programme-guidance/information-for-volunteers/general-activity-guidance-a-z/general-water-activities/water-safety-waterborne-diseases-and-immersion/",
                 "https://www.rya.org.uk/making-a-difference/water-quality-our-position/"):
        assert f'href="{href}"' in page, href
    for href in ("methods.html#level", "methods.html#actions", "organisers.html", "about.html#embed", "terms.html",
                 "sites.html", "record.html", "coverage.html", "verification.html", "spot/bw-uke4100-08901/profile/"):
        assert f'href="{href}"' in page, href
    # Level words carry "risk"; short sentences, most under 20 words.
    assert not re.search(r"\b(low|moderate|high|very high)\b(?! risk| and| or|,)", words.split("What the levels mean")[1].split("There are four levels")[0])
    sents = [s for s in re.split(r"(?<=[.?!])\s+", words) if len(s.split()) > 2]
    assert sum(len(s.split()) < 20 for s in sents) / len(sents) > 0.75
    # Linked from About and from the home page's foot, beside the organisers' page.
    assert 'href="clubs.html">For clubs, centres and leaders</a>' in (tmp_path / "about.html").read_text()
    assert ('<a href="organisers.html">For event organisers</a> · <a href="clubs.html">For clubs, centres and leaders</a>'
            in (tmp_path / "index.html").read_text())


def test_a_share_is_said_as_the_nearest_simple_fraction():
    said = {p: bs.share_words(p) for p in (0.208, 0.409, 0.5, 0.26, 0.31, 0.34, 0.66, 0.74, 0.12, 0.875, 0.049, 0.951)}
    assert said == {0.208: "about one in five", 0.409: "about two in five", 0.5: "about one in two",
                    0.26: "about one in four", 0.31: "about three in ten", 0.34: "about one in three",
                    0.66: "about two in three", 0.74: "about three in four", 0.12: "about one in ten",
                    0.875: "about nine in ten", 0.049: "fewer than one in twenty", 0.951: "nearly all"}


def test_the_clubs_page_fills_its_warning_figures_from_the_live_scores(tmp_path):
    (tmp_path / "data").mkdir()
    table = {"level": "high", "hit_rate": 0.31, "warnings_true": 0.52, "first_day": "2026-12-29", "last_day": "2027-01-04"}
    (tmp_path / "data" / "verification.json").write_text(json.dumps({"live": {"warning_table": table}}))
    bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/", day="2027-01-05")
    words = text((tmp_path / "clubs.html").read_text())
    assert ("It misses most spills. Its live scores ran from 29 December 2026 to 4 January 2027. At the high risk line, "
            "it warned of about three in ten spills. About one in two of its warnings were followed by a spill.") in words
    # Without the table, or with a field missing, the page's own words stay.
    fallback = "it warned of about one in five spills. About two in five of its warnings were followed by a spill."
    for v in ({}, {"live": {"warning_table": {**table, "hit_rate": None}}}, None):
        f = tmp_path / "data" / "verification.json"
        if v is None:
            f.unlink()
        else:
            f.write_text(json.dumps(v))
        bs.write_pages(tmp_path, SPOTS[:1], root="https://example.org/")
        assert fallback in text((tmp_path / "clubs.html").read_text()), v
