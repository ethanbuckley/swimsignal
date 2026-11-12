"""One foot on every page (12 Nov 2026; docs/DESIGN.md, "One foot, one opening"): the app had 12 links, the prose
pages 7 and the Research Lab 4. Every page now has the same links in the same order. The app's foot leaves out only
Data credits, which the credit line under its links gives."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402

LABELS = [t for _, t in build_site.FOOT_LINKS] + ["Source code"]
PAGES = sorted([*(ROOT / "src/dipcast/pages").glob("*.html"), *(ROOT / "src/dipcast/site").glob("*.html"),
                *(ROOT / "prototypes/research-lab").rglob("index.html")])


def _labels(page: Path) -> list[str] | None:
    foot = re.search(r"<footer\b.*?</footer>", page.read_text(), re.S)
    if not foot:
        return None
    line = next((p for p in re.findall(r"<p[^>]*>(.*?)</p>", foot[0], re.S) if "Terms of use" in p), None)
    return re.findall(r"<a [^>]*>(.*?)</a>", line) if line else []


def test_every_page_with_a_foot_has_the_same_links_in_the_same_order():
    seen = 0
    for page in PAGES:
        labels = _labels(page)
        if labels is None:   # embed.html sits on another site and has no foot
            assert page.name == "embed.html", page
            continue
        want = [t for t in LABELS if t != "Data credits"] if page.name == "index.html" and page.parent.name == "site" else LABELS
        assert labels == want, page
        seen += 1
    assert seen >= 37


def test_the_built_foot_and_the_not_found_page_use_the_same_list():
    line = build_site.foot_links("https://example.org/")
    assert re.findall(r"<a [^>]*>(.*?)</a>", line) == LABELS
    assert 'href="https://example.org/feedback.html?type=spot">Request a spot</a>' in line
    assert build_site.foot_links("https://example.org/") in build_site.not_found_page("https://example.org/")


def test_no_listed_page_is_reached_from_one_page_only():
    """quality.html had one inbound link (About) and data-feed.html one (For organisations)."""
    def linked(name: str) -> set[str]:
        stem = name.removesuffix(".html")
        return {p.name for p in PAGES if p.name != name and p.parent.name != "research-lab"
                and re.search(rf'href="/?{re.escape(stem)}(\.html)?["#?]', p.read_text())}
    for name in ("quality.html", "data-feed.html", "sampling-planner.html"):
        assert len(linked(name)) >= 2, (name, linked(name))
