"""Action counts (actions/, the Worker; countAction in src/dipcast/site/index.html): off until DIPCAST_ACTIONS_URL is
set; then the app's head names the Worker and the privacy notice says what is counted. The Worker's own tests are in
actions/test (node --test); the page's in tests/site_action_counts.test.cjs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://swimsignal-actions.swimsignal-push.workers.dev/"
SPOTS = [{"id": "a", "name": "A", "kind": "river", "days": []}]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_off_unless_the_worker_address_is_set(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.ACTIONS_URL_ENV, raising=False)
    assert bs.actions_url() is None
    monkeypatch.setenv(bs.ACTIONS_URL_ENV, URL)
    assert bs.actions_url() == URL
    for bad in ("http://example.org/", "https://example.org/x", 'https://a"b/', "javascript:alert(1)//"):
        monkeypatch.setenv(bs.ACTIONS_URL_ENV, bad)
        assert bs.actions_url() is None


def test_off_the_app_names_no_worker_and_the_notice_is_unchanged(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/")
    for page in ("index.html", "plan/index.html", "saved/index.html", "spot/a/index.html"):
        assert "swimsignal-actions" not in (tmp_path / page).read_text(), page
    privacy = (tmp_path / "privacy.html").read_text()
    assert 'id="action-counts"' not in privacy and "Last updated 31 October 2026." in privacy
    assert "There is no analytics script and no third-party tracking." in privacy


def test_on_the_app_names_the_worker_and_the_notice_says_what_is_counted(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, root="https://example.org/", actions=URL)
    meta = f'<meta name="swimsignal-actions" content="{URL}">'
    for page in ("index.html", "plan/index.html", "saved/index.html", "spot/a/index.html"):
        assert (tmp_path / page).read_text().count(meta) == 1, page
    privacy = (tmp_path / "privacy.html").read_text()
    assert privacy.index('<h2 id="action-counts">Action counts</h2>') < privacy.index("<h2>The server version</h2>")
    assert "Last updated 31 October 2026 (action counts)." in privacy
    assert "There is no analytics script" not in privacy
    assert "There is no third-party tracking. Eleven actions" in privacy
    for words in ("not your IP address", "no cookie and no identifier", "Nothing is stored on your device",
                  "Don't count my visits", "Global Privacy Control", "how often eleven things",
                  "for a date", "back to low risk", '"Log a swim here" pressed', "spill feed on the home page",
                  "search opened on a phone", "a day picked on a phone's map", "for the first three, which spot"):
        assert words in privacy, words
    assert "(action counts)" not in (tmp_path / "terms.html").read_text()


def test_with_the_page_view_counter_too_both_are_described(tmp_path):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOTS, token="abcdefghij0123456789", root="https://example.org/", actions=URL)
    privacy = (tmp_path / "privacy.html").read_text()
    assert "Last updated 31 October 2026 (page-view counter, action counts)." in privacy
    assert "Cloudflare Web Analytics" in privacy
    assert "are also counted as daily totals that hold nothing about who did them (see Action counts). There is no other analytics or tracking." in privacy


def test_the_notice_names_as_many_actions_as_the_worker_takes():
    """The privacy section's count and its "for the first three, which spot" follow actions/src/index.js."""
    import re
    bs = _build_site()
    worker = (ROOT / "actions" / "src" / "index.js").read_text()
    events = re.findall(r"'(\w+)'", re.search(r"export const EVENTS = \[([^\]]*)\]", worker)[1])
    with_spot = re.findall(r"'(\w+)'", re.search(r"const WITH_SPOT = new Set\(\[([^\]]*)\]\)", worker)[1])
    words = {5: "five", 11: "eleven"}
    assert len(events) in words, "say the new number in ACTIONS_PRIVACY and ACTIONS_SWAPS, then add it here"
    assert f"how often {words[len(events)]} things" in bs.ACTIONS_PRIVACY
    assert all(f"{words[len(events)].capitalize()} actions" in new for _, new in bs.ACTIONS_SWAPS)
    assert with_spot == events[:3] and "for the first three, which spot" in bs.ACTIONS_PRIVACY


def test_every_sentence_it_swaps_is_in_the_notice_or_the_counters_text():
    bs = _build_site()
    source = (bs.STATIC / "privacy.html").read_text()
    assert bs.ACTIONS_SWAPS[0][0] in source
    assert bs.ACTIONS_SWAPS[1][0] in bs.WITH_COUNTER[1]
    assert "<h2>The server version</h2>" in source


def test_the_build_workflow_passes_the_variable():
    assert "DIPCAST_ACTIONS_URL: ${{ vars.DIPCAST_ACTIONS_URL }}" in (ROOT / ".github" / "workflows" / "site.yml").read_text()
