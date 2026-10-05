"""Plain overflow names (markets plan B1/T1): the Python copy (src/dipcast/overflow_names.py) gives the
same name as the page's (plainName in src/dipcast/site/levels.js) for every overflow name in
tests/fixtures/overflow_names.txt, the 14,064 distinct names in swimsignal.co.uk/data/overflows.geojson
on 6 Oct 2026. tests/site_overflow_names.test.cjs checks what the names say."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dipcast.overflow_names import name_case, plain_name

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
