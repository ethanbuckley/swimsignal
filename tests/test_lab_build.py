"""The Research Lab as the build writes it to lab/: every file a page or script reads is there, and nothing points
back into the repository (prototypes/research-lab/ reads data/research/ as committed; the site cannot)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site  # noqa: E402



@pytest.fixture(scope="module")
def site(tmp_path_factory) -> Path:
    site = tmp_path_factory.mktemp("site")
    assert build_site.write_lab(site) >= 6   # the front page and five exhibits, at least
    return site


def _files(site: Path, *suffixes: str) -> list[Path]:
    lab = site / "lab"
    return [f for f in sorted(lab.rglob("*")) if f.suffix in suffixes and (lab / "data") not in f.parents]


def _local(ref: str) -> bool:
    return not re.match(r"[a-z]+:|#|//", ref) and "${" not in ref


def test_nothing_reaches_into_the_repository(site):
    for f in _files(site, ".html", ".js", ".css"):
        s = f.read_text()
        assert "../../../" not in s and "../src/dipcast" not in s, f


# What a Lab page may link outside lab/: the site's own pages and files, which the rest of the build writes.
SITE_FILES = {"", "index.html", "page.css", "icons/icon.svg", "icons/apple-touch-icon.png", "plan/", "saved/", "verification.html",
              "about.html", "research.html", "feedback.html", "terms.html", "privacy.html", "sampling-planner.html"}


def test_every_read_resolves(site):
    missing, outside = [], set()
    for f in _files(site, ".html", ".js"):
        s, base = f.read_text(), f.parent
        consts = dict(re.findall(r"\b(DATA|PATHS) = '([^']*)'", s))
        refs = [consts[k] + x for k, x in re.findall(r"\b(DATA|PATHS) \+ '([^']+)'", s)]
        refs += re.findall(r"fetch\('([^'$]+)'\)", s)
        refs += re.findall(r"'((?:\.\./)+[^'$]+\.json)'", s)
        if f.suffix == ".html":
            refs += [r for r in re.findall(r'(?:src|href)="([^"]+)"', s) if _local(r)]
        for r in refs:
            p = (base / r.split("?")[0].split("#")[0]).resolve()
            if (site / "lab") not in p.parents and p != (site / "lab").resolve():
                rel = "" if p == site.resolve() else p.relative_to(site.resolve()).as_posix()
                outside.add(rel + "/" if rel and r.split("?")[0].split("#")[0].endswith("/") else rel)
                continue
            if not (p.is_file() or (p / "index.html").is_file()):
                missing.append(f"{f.relative_to(site)}: {r}")
    assert not missing, missing
    assert outside <= SITE_FILES, outside - SITE_FILES   # nothing else leaves the Lab


def test_the_sites_shell(site):
    # The site's stylesheet, header and phone bar on every page, Research Lab marked as the page you are on; the
    # stand-in header a repository preview shows is gone.
    for f in _files(site, ".html"):
        s, up = f.read_text(), "../" * (len(f.relative_to(site).parts) - 1)
        assert f'<link rel="stylesheet" href="{up}page.css">' in s, f
        assert build_site.site_header(up, "lab/") in s and s.count('<header class="top">') == 1, f
        assert f'aria-current="page" href="{up}lab/"' in s and s.count('<nav class="phone-nav" aria-label="Main">') == 1, f
        assert f'<a href="{up}lab/">Research Lab</a>' in s, f   # the phone's More
        nav = re.search(r'<nav class="labnav".*?</nav>', s, re.S).group(0)
        assert nav.count('aria-current="page"') == 1 and nav.count("<a ") == 6, f


def test_exhibits_end_with_the_next_and_the_way_back(site):
    for d in ("lake-from-space", "pollution", "forecasts", "workspace", "sampling"):
        s = (site / "lab" / d / "index.html").read_text()
        assert '<nav class="pager" aria-label="Exhibits">' in s and ">Back to the forecasts</a>" in s, d


def test_covers_are_not_controls(site):
    s = (site / "lab" / "index.html").read_text()
    assert s.count("LAB.drawMap(") == 3 and s.count("inert: true") == 3
    assert s.count('<div class="cover" aria-hidden="true">') == 5 and ".ex .cover * { pointer-events: none; }" in s
    covers = site / "lab" / "assets" / "covers"
    assert sorted(f.name for f in covers.iterdir()) == ["forecasts.jpg", "lake-from-space.jpg", "pollution.jpg", "sampling.jpg", "workspace.jpg"]


def test_lab_links_name_only_what_an_exhibit_holds(tmp_path):
    spots = [{"id": i} for i in ("bw-uke4100-08901", "osm-windermere-waterhead", "bw-ukd1203-45675", "thames-henley")]
    assert build_site.attach_lab_links(spots) == 3
    by = {s["id"]: s.get("lab") for s in spots}
    assert by["bw-uke4100-08901"] == {"bw": "uke4100-08901", "ws": "wharfe-ilkley"}
    assert by["osm-windermere-waterhead"] == {"ws": "windermere"}
    assert by["bw-ukd1203-45675"] == {"lake": "bw-ukd1203-45675", "bw": "ukd1203-45675", "ws": "windermere"}
    assert by["thames-henley"] is None
    assert "lab" in build_site.DETAIL_FIELDS   # a spot's own file, not the list's


def test_no_fonts_of_its_own(site):
    # page.css gives the Lab the site's fonts; lab.css declares none, so there is one copy to keep.
    assert "@font-face" not in (site / "lab" / "lab.css").read_text()


def test_pictures_and_paths_are_copied(site):
    lab = site / "lab"
    imagery = json.loads((lab / "data" / "lake_imagery.v1.json").read_text())
    urls = [sc[k] for x in imagery["sites"] for sc in x["scenes"] for k in ("image_url", "mask_url", "index_url") if sc.get(k)]
    assert urls and all((lab / "data" / u).is_file() for u in urls)
    spots = json.loads((lab / "assets" / "paths" / "index.json").read_text())["spots"]
    assert all((lab / "assets" / "paths" / f"{s['id']}.json").is_file() for s in spots if not s.get("note"))


def test_left_out(site):
    lab = site / "lab"
    assert not list(lab.rglob("shots")) and not list(lab.rglob("*.md"))
    for f in _files(site, ".html"):
        s = f.read_text()
        assert "noindex" not in s and 'name="description"' in s and "prototype" not in s.lower(), f


def test_every_page_is_in_the_sitemap(site):
    pages = build_site.lab_pages()
    assert pages[0] == "lab/" and {"lab/lake-from-space/", "lab/pollution/", "lab/forecasts/", "lab/workspace/", "lab/sampling/"} <= set(pages)
    assert all((site / p / "index.html").is_file() for p in pages)
    assert all(f"<loc>https://example.org/{p}</loc>" in build_site.sitemap("https://example.org/", [], "2026-11-01", extra=pages) for p in pages)


def test_no_lab_no_folder(tmp_path):
    (tmp_path / "lab").mkdir()
    assert build_site.write_lab(tmp_path, lab=tmp_path / "missing") == 0 and not (tmp_path / "lab").exists()
    assert build_site.lab_pages(tmp_path / "missing") == []


def test_refresh_dates_every_part_a_page_names(site):
    doc = json.loads((site / "lab" / "refresh.json").read_text())
    for p in doc["parts"].values():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["as_of"]) and p["label"] and p["refresh"], p
    named = set()
    for f in _files(site, ".html"):
        for m in re.findall(r'data-asof="([^"]+)"', f.read_text()):
            named |= set(m.split(","))
    assert named and named <= set(doc["parts"]), named - set(doc["parts"])
    # the analyses are dated versions, never called out of date; the copied paths are by hand until a build makes them
    assert "stale_days" not in doc["parts"]["forecast-record"] and doc["parts"]["forecast-record"]["outcomes_to"] == "2026-09-30"
    assert doc["parts"]["paths"]["refresh"] == "by hand"


def test_paths_from_the_build_are_dated_as_such(tmp_path):
    build_site.write_lab(tmp_path)
    assert build_site.write_lab_refresh(tmp_path, paths_from_build=True)["parts"]["paths"]["refresh"] == "at every site build"
    assert build_site.write_lab_paths(tmp_path / "none", None, None) == {"skipped": "no Lab in this build"}


# ------------------------------------------------------------------ exhibit 5, sampling gaps
# docs/SAMPLING-GAPS-EXHIBIT-2026-11.md: the sampling planner's own file beside gaps.json; the failed verdict and "never
# tried in real water" beside the comparison; the population and cutoff it covers said on the page.

def test_sampling_reads_the_planners_file_and_its_own(site):
    lab = site / "lab"
    planner = json.loads((lab / "data" / "sampling_planner.v1.json").read_text())
    assert planner["schema"] == "swimsignal.sampling-planner" and planner["field_validation"] is False
    gaps = json.loads((lab / "sampling" / "gaps.json").read_text())
    import lab_sampling_gaps
    assert lab_sampling_gaps.check(gaps) == []   # the same spots and samples as the planner's file
    js = (lab / "sampling" / "sampling.js").read_text()
    assert "DATA + 'sampling_planner.v1.json'" in js and "fetch('gaps.json')" in js


def test_sampling_says_what_it_covers(site):
    # The site's spot list grows after an export: the page names the export's spot count, its date and the last
    # sample, and says spots added since are not in it. Never complete current coverage.
    page = (site / "lab" / "sampling" / "index.html").read_text()
    js = (site / "lab" / "sampling" / "sampling.js").read_text()
    assert 'id="scope"' in page and 'id="pop"' in page
    assert "This export holds the ${G.spots.length} spots in SwimSignal's list on ${LAB.day(G.made)}" in js
    assert "Spots added to the site since are not in it." in js
    assert "$('#scope').textContent" in js and "$('#pop').textContent" in js
    assert "of SwimSignal's ${sp.total} spots" not in js   # a count of "SwimSignal's spots" would read as current
    gaps = json.loads((site / "lab" / "sampling" / "gaps.json").read_text())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", gaps["made"]) and gaps["outcomes_to"] <= "2026-09-30"
    part = json.loads((site / "lab" / "refresh.json").read_text())["parts"]["sampling"]
    assert part["as_of"] == gaps["made"][:10] and part["outcomes_to"] == gaps["outcomes_to"] and "stale_days" not in part


def test_sampling_keeps_the_planners_limits_beside_the_figures(site):
    page = (site / "lab" / "sampling" / "index.html").read_text()
    compare = page[page.index('id="s-compare"'):page.index('id="s-sim"')]
    assert "failed its test against equal coverage" in compare and "no rule here has been tried in real water" in compare
    js = (site / "lab" / "sampling" / "sampling.js").read_text()
    assert "The test needed 60%: it failed." in js and "Made-up worlds, not real water." in js
    assert "No rule for choosing them has been shown to help." in js
    assert "That says nothing about whether the water is clean." in js
    assert not re.search(r"\b(more efficient|recommended|best season|optimal)\b", page + js, re.I)


def test_folded_dates_never_pass_an_export_date_off_as_the_datas(site):
    # An export made in November of samples to September: the folded line gives both (2 Nov 2026, a live check read
    # "samples 2 Nov 2026" for samples to 28 Sept).
    js = (site / "lab" / "lab.js").read_text()
    assert "${p.outcomes_to ? `, outcomes to ${day(p.outcomes_to)}` : ''}`).join(' · ')}</summary>" in js
    doc = json.loads((site / "lab" / "refresh.json").read_text())
    if "sampling" in doc["parts"]:
        assert doc["parts"]["sampling"]["short"] == "sampling export" and doc["parts"]["sampling"].get("outcomes_to")


def test_sampling_never_claims_every_spot(site):
    # Its export holds the spots on its date, not every spot the site has now (2 Nov 2026): the labels say so too.
    for f in ("sampling/index.html", "sampling/sampling.js"):
        p = site / "lab" / f
        if p.is_file():
            assert "every SwimSignal spot" not in p.read_text() and "every spot" not in p.read_text().lower().replace("every spot's", ""), f
