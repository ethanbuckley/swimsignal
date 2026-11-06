"""The README's spot counts match the spot files, so they cannot go stale again (they said 105 and 16 on
6 Nov 2026 against 111 and 18). The site's own counts come from the build (build_site.home_lead, about.html's
n-spots); the README is the one place a count is typed by hand."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rows(name: str) -> int:
    with (ROOT / name).open(newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_the_readme_counts_the_spot_files():
    readme = (ROOT / "README.md").read_text()
    england = _rows("spots.csv") + _rows("spots-osm.csv")
    scotland = _rows("spots-scotland.csv")
    osm = _rows("spots-osm.csv")
    m = re.search(r"It covers (\d+) named spots in England, (\d+) more\s+in Scotland", readme)
    assert m, "the README's opening no longer states the counts"
    assert (int(m.group(1)), int(m.group(2))) == (england, scotland)
    m = re.search(r"\| OpenStreetMap \(Overpass API\) \| (\d+) river and lake swim spots chosen one by one", readme)
    assert m and int(m.group(1)) == osm
