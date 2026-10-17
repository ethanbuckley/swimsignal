"""Plain overflow names (markets plan B1/T1): the Python copy (src/dipcast/overflow_names.py) gives the
same name as the page's (plainName in src/dipcast/site/levels.js) for every overflow name in
tests/fixtures/overflow_names.txt, the 14,064 distinct names in swimsignal.co.uk/data/overflows.geojson
on 6 Oct 2026. tests/site_overflow_names.test.cjs checks what the names say."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dipcast.overflow_names import name_case, plain_name, water_name

ROOT = Path(__file__).resolve().parents[1]
NAMES = (ROOT / "tests" / "fixtures" / "overflow_names.txt").read_text(encoding="utf-8").splitlines()
LEVELS = ROOT / "src" / "dipcast" / "site" / "levels.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_python_and_the_page_agree_on_every_name():
    js = ("const L = require(process.argv[1]); const names = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
          "process.stdout.write(JSON.stringify(names.map(n => [L.plainName(n), L.nameCase(n)])));")
    names = NAMES + ["", "  ", "Kettlewell/STW", "o/s 12 High St/CSO"]
    r = subprocess.run(["node", "-e", js, str(LEVELS)], input=json.dumps(names), capture_output=True, text=True,
                       timeout=120, check=True)
    page = json.loads(r.stdout)
    differ = [(n, p, plain_name(n)) for n, (p, _) in zip(names, page) if p != plain_name(n)]
    assert not differ, f"{len(differ)} names differ, the first: {differ[:5]}"
    assert [c for _, c in page] == [name_case(n) for n in names]


def test_the_examples():
    assert plain_name("Addingham/NO 1 SPS/Preliminary Treatment-STW/6Xdwf Overflow") == "Addingham sewage works overflow"
    assert plain_name("RIVADALE VIEW/CSO") == "Rivadale View storm overflow"
    assert plain_name("Bridge Lane/CSO") == "Bridge Lane storm overflow"
    assert plain_name(None) == "" and plain_name("WAREHAM NORTH BRIDGE") == name_case("WAREHAM NORTH BRIDGE")
    # 11 Oct 2026: a phrase in capitals before the codes, and three capitals in a name all in capitals.
    assert plain_name("BUXTON STW INLET STORM OVERFLOW (CSO)") == "Buxton sewage works overflow"
    assert name_case("BEN RHYDDING/STW") == "Ben Rhydding/STW" and name_case("BUXTON STW (SSTO)") == "Buxton STW (SSTO)"


# 16 Oct 2026 (docs/REVIEW-2026-10-16.md, 8.3): the placeholders the feeds give for a receiving water, in
# the spellings overflows.geojson held, read as no name, so the map's pop-up and the spot's list say the
# water is not named in its feed rather than print "#N/A".
@pytest.mark.parametrize("raw", ["#N/A", "N/A", "None", "0", "-", "", "  ", " #n/a ", "n/a", "NONE", None, float("nan")])
def test_a_placeholder_is_no_water_name(raw):
    assert water_name(raw) is None


def test_a_water_name_is_kept_as_the_feed_gives_it():
    assert water_name("River Wharfe") == "River Wharfe"
    assert water_name("  Clifton Hampton Ditch ") == "Clifton Hampton Ditch"
    # Names that only contain a placeholder's characters are names.
    assert water_name("R STOUR") == "R STOUR" and water_name("Nonesuch Brook") == "Nonesuch Brook"
    assert water_name("10") == "10" and water_name("UCK") == "UCK"


def test_the_forecast_writes_no_placeholder_water(monkeypatch):
    import pandas as pd

    from dipcast.model import forecast
    rows = pd.DataFrame({"site_id": list("abcdef"), "receiving_watercourse": ["#N/A", "N/A", "None", "0", "River Eden", None]})
    monkeypatch.setattr(forecast, "load_overflows", lambda net: rows.copy())
    monkeypatch.setattr(forecast, "_net", lambda: None)
    forecast._overflows_uncached.cache_clear()
    try:
        written = [forecast._clean(v) for v in forecast._overflows()["receiving_watercourse"]]   # as spots.json gets them
        assert written == [None, None, None, None, "River Eden", None]
    finally:
        forecast._overflows_uncached.cache_clear()
