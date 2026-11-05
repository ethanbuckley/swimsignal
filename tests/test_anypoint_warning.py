"""A click-anywhere failure is a build health warning, not only an annotation on the run.

From 26 Oct 2026 11:04 UTC scripts/build_any_point.py failed at every build (the clock change, PR #413)
and spots.json's build.warnings stayed empty: write_any_point runs after the build's warnings are
announced, so its warning reached the run's annotations alone. No test here builds anything: the
click-anywhere script is replaced by a stub in a temporary root."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bs(monkeypatch, tmp_path):
    """build_site with the click-anywhere script read from tmp_path/scripts and no model, network or overflows
    loaded; the announced warnings in bs.said."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    from dipcast.model import forecast
    said = []
    monkeypatch.setattr(build_site, "announce", said.append)
    monkeypatch.setattr(build_site, "ROOT", tmp_path)
    monkeypatch.setattr(build_site, "_net", lambda: None)
    monkeypatch.setattr(build_site, "_overflows", lambda: None)
    monkeypatch.setattr(forecast, "_model", lambda: None)
    (tmp_path / "scripts").mkdir()
    build_site.said = said
    return build_site


def _stub(tmp_path, body: str) -> None:
    (tmp_path / "scripts" / "build_any_point.py").write_text(
        "def build(site, net, ov, probabilities, credits):\n" + body + "\n")


def test_a_click_anywhere_failure_goes_into_the_build_health_warnings(bs, tmp_path):
    _stub(tmp_path, "    (site / 'data' / 'anypoint').mkdir(parents=True)\n"
                    "    raise ValueError(\"Cannot infer dst time from 2026-10-25 01:00:00\")")
    site, warnings = tmp_path / "site", ["an earlier warning"]
    assert bs.write_any_point(site, {}, warnings) is None
    w = "click-anywhere data not written: Cannot infer dst time from 2026-10-25 01:00:00"
    assert warnings == ["an earlier warning", w]
    assert bs.said == [w]                                   # the run's annotation, as before
    assert not (site / "data" / "anypoint").exists()        # never half a set of files


def test_a_click_anywhere_success_adds_no_warning(bs, tmp_path):
    _stub(tmp_path, "    return {'overflows': 3}")
    warnings = []
    assert bs.write_any_point(tmp_path / "site", {}, warnings) == {"overflows": 3}
    assert warnings == [] and bs.said == []


def test_a_push_of_any_script_the_build_runs_rebuilds_the_site():
    """site.yml's push paths name every file under scripts/ that build_site.py runs: PR #413 fixed
    build_any_point.py on 27 Oct 2026 and its merge did not rebuild the site."""
    import re
    run = set(re.findall(r'ROOT / "scripts" / "([^"]+)"', (ROOT / "scripts" / "build_site.py").read_text()))
    assert {"build_any_point.py", "alerts.js", "prerender_spots.js", "prerender_verification.js"} <= run
    wf = (ROOT / ".github" / "workflows" / "site.yml").read_text()
    # The push block's flow list (no YAML parser among the dependencies): from "paths: [" to "]".
    block = wf[wf.index("\n  push:"):wf.index("\nconcurrency:")]
    listed = block[block.index("paths: [") + len("paths: ["):]
    paths = {p.strip().strip('"') for p in listed[:listed.index("]")].split(",")}
    assert {f"scripts/{f}" for f in run} | {"scripts/build_site.py"} <= paths


def test_the_build_passes_its_warnings_and_writes_spots_json_after():
    """build() hands write_any_point the health's own list, and writes spots.json (whose build.warnings
    the page and the status checks read) only after it."""
    src = (ROOT / "scripts" / "build_site.py").read_text()
    body = src[src.index("\ndef build(refresh"):]
    call = body.index('health["anypoint"] = write_any_point(SITE, credits, health["warnings"])')
    assert call < body.index('(SITE / "data" / "spots.json").write_text(')
