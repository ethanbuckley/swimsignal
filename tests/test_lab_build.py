"""The Research Lab as the build writes it to lab/: every file a page or script reads is there, and nothing points
back into the repository (prototypes/research-lab/ reads data/research/ as committed; the site cannot)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site  # noqa: E402

FONTS = build_site.STATIC / "fonts"


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> Path:
    site = tmp_path_factory.mktemp("site")
    assert build_site.write_lab(site) >= 4   # the front page and three exhibits, at least
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


def test_every_read_resolves(site):
    missing = []
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
                assert p == site.resolve(), f"{f}: {r} leaves the Lab"   # only the brand link, to the site's root
                continue
            if not (p.is_file() or (p / "index.html").is_file()):
                missing.append(f"{f.relative_to(site)}: {r}")
    assert not missing, missing


def test_fonts_are_the_sites(site):
    css = (site / "lab" / "lab.css").read_text()
    urls = re.findall(r"url\(['\"]?([^'\")]+\.(?:woff2?|ttf|otf))", css)
    assert urls
    for u in urls:
        assert u.startswith("../fonts/") and (FONTS / u.split("?")[0][len("../fonts/"):]).is_file(), u


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
    assert pages[0] == "lab/" and {"lab/lake-from-space/", "lab/pollution/", "lab/forecasts/"} <= set(pages)
    assert all((site / p / "index.html").is_file() for p in pages)
    assert all(f"<loc>https://example.org/{p}</loc>" in build_site.sitemap("https://example.org/", [], "2026-11-01", extra=pages) for p in pages)


def test_no_lab_no_folder(tmp_path):
    (tmp_path / "lab").mkdir()
    assert build_site.write_lab(tmp_path, lab=tmp_path / "missing") == 0 and not (tmp_path / "lab").exists()
    assert build_site.lab_pages(tmp_path / "missing") == []
