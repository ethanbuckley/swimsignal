"""Email alerts (push/src/email.js) in the build: off unless DIPCAST_EMAIL_URL is set, and the privacy
notice describes them only when they are on, alone or beside browser alerts, without breaking the
sentences the reviews section changes after it."""

import sys
from pathlib import Path

from dipcast import reviews as rv

ROOT = Path(__file__).resolve().parents[1]
SPOT = [{"id": "a", "name": "A", "kind": "river", "upstream_summary": {"overflows": 1}, "days": []}]


def _build_site():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    return build_site


def test_email_alerts_are_off_unless_the_address_is_sound(monkeypatch):
    bs = _build_site()
    monkeypatch.delenv(bs.EMAIL_URL_ENV, raising=False)
    assert bs.email_config() is None
    monkeypatch.setenv(bs.EMAIL_URL_ENV, "https://swimsignal-push.example.workers.dev/")
    assert bs.email_config() == {"url": "https://swimsignal-push.example.workers.dev/"}
    for bad in ("http://swimsignal-push.example.workers.dev/", "https://swimsignal-push.example.workers.dev", 'https://x.example/"'):
        monkeypatch.setenv(bs.EMAIL_URL_ENV, bad)
        assert bs.email_config() is None, bad


def _privacy(tmp_path, **kw):
    bs = _build_site()
    bs.write_pages(tmp_path, SPOT, root="https://example.org/", **kw)
    return bs, (tmp_path / "privacy.html").read_text()


def test_the_privacy_notice_has_no_email_section_while_email_is_off(tmp_path):
    bs, off = _privacy(tmp_path)
    assert 'id="email-alerts"' not in off and bs.EMAIL_SHORT_LINE not in off
    _, push = _privacy(tmp_path, push=True)
    assert 'id="email-alerts"' not in push and bs.EMAIL_OFFLINE_SWAP not in push


def test_email_alone_gets_an_alerts_section_with_email_in_it(tmp_path):
    bs, html = _privacy(tmp_path, email=True)
    assert "If alerts are added" not in html and "push address" not in html
    assert html.count("<h2>Alerts</h2>") == 1 and html.index("<h2>Alerts</h2>") < html.index('<h3 id="email-alerts">')
    assert bs.EMAIL_PRIVACY.strip() in html
    for before, after in bs.PUSH_SWAPS[:3]:   # the saved spots leave the device, and the record is under Alerts
        assert after in html and before not in html
    assert bs.PUSH_SWAPS[3][0] in html, "email alerts do not need the offline copy"
    assert bs.PUSH_SWAPS[0][1] + "\n" + bs.EMAIL_SHORT_LINE in html
    # The reviews section's change to "SwimSignal holds none" still finds its sentence.
    assert rv.HOLDS_NONE[0][0] in html
    assert rv.HOLDS_NONE[0][1] in rv.with_reviews(html, "privacy.html")


def test_push_and_email_together(tmp_path):
    bs, html = _privacy(tmp_path, push=True, email=True)
    assert html.count("<h2>Alerts</h2>") == 1
    assert html.index("push address") < html.index('<h3 id="email-alerts">') < html.index("<h2>The server version</h2>")
    for before, after in bs.PUSH_SWAPS[:3]:
        assert after in html and before not in html
    assert bs.EMAIL_OFFLINE_SWAP in html and bs.PUSH_SWAPS[3][1] not in html and bs.PUSH_SWAPS[3][0] not in html
    assert rv.HOLDS_NONE[0][0] in html and rv.PRIVACY_SECTION_BEFORE in html and rv.SHORT_VERSION_BEFORE in html


def test_the_email_section_says_what_the_worker_does():
    bs = _build_site()
    text = bs.EMAIL_PRIVACY
    # The facts the Worker's code and tests hold it to (push/src/email.js, push/test/email.test.js).
    for words in ("deleted after two days", "your address, the identifiers of those spots and the time you confirmed",
                  "at most once a day for each spot", "no images, no pixels", "unsubscribe link in every email",
                  "deletes your address and your list of spots at once", "for an hour under a scrambled form of your IP address",
                  "the IP address itself is not stored", "Resend (Plus Five Five, Inc.)", "UK's addendum",
                  "cannot be delivered for good, or you mark one as spam"):
        assert words in text, words
