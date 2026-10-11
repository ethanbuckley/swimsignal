"""Make the social-media cards (src/dipcast/cards.py) from the live site's data, without a build:

    uv run python scripts/make_cards.py --out cards-out

It downloads data/spots-lite.json and data/alerts.json from the site (or reads them from a folder
with --data), then writes each card at both sizes, its caption and an index.html into --out. The
site build makes the same files at site/cards/ on every update, so this is for a local look or a
card between updates. No forecast is run and nothing else is asked for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from dipcast import cards

SITE = "https://swimsignal.co.uk/"


def load(src: str, name: str) -> dict:
    if src.startswith(("http://", "https://")):
        r = httpx.get(src.rstrip("/") + "/" + name, timeout=60, follow_redirects=True)
        r.raise_for_status()
        return r.json()
    return json.loads((Path(src) / name).read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path, help="folder to write into; its PNG and text files and index.html are replaced")
    ap.add_argument("--data", default=SITE + "data/", help="the site's data/ address, or a folder holding the two files")
    ap.add_argument("--root", default=SITE, help="the site's address for links in the captions, ending in /")
    a = ap.parse_args()
    if not a.root.endswith("/"):
        ap.error("--root must end in /")
    lite = load(a.data, "spots-lite.json")
    alerts = load(a.data, "alerts.json")
    summary = cards.write_cards(a.out, lite["spots"], alerts, lite["generated_at"], a.root)
    for f in sorted(a.out.iterdir()):
        print(f)
    print(summary)
    return 1 if summary["warnings"] and not summary["cards"] else 0


if __name__ == "__main__":
    sys.exit(main())
