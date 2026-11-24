"""A local preview of the redesign in src/dipcast/site/preview/, on the live forecast.

    python3 scripts/preview_redesign.py            # then open http://localhost:8797/preview/
    python3 scripts/preview_redesign.py --data DIR  # keep the forecast files in DIR (default: .preview-data/)
    python3 scripts/preview_redesign.py --offline   # serve only what DIR already holds

It serves the source files as they are, so an edit shows on reload:

- /preview/, /levels.js, /eatoday.js, /icons/   from src/dipcast/site/
- /fonts/                                       from src/dipcast/pages/fonts/
- /guides/photos/                               from guides/photos/
- /data/hero-photos.json                        made here from guides/*.toml, by the live page's own rule for the
                                                photo that opens a spot (guide.js, guideHero)
- /data/...                                     from DIR; a file DIR lacks is fetched once from swimsignal.co.uk
                                                and kept, so the levels and times are a real issue of the forecast
- anything else (about.html, plan/, ...)        a redirect to the live site, so the preview's links to it work

Nothing here is part of the build, and nothing is published by it.
"""

from __future__ import annotations

import argparse
import json
import tomllib
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "src" / "dipcast" / "site"
FONTS = ROOT / "src" / "dipcast" / "pages" / "fonts"
GUIDES = ROOT / "guides"
LIVE = "https://swimsignal.co.uk"
LICENCES = {"https://creativecommons.org/licenses/by-sa/2.0/": "CC BY-SA 2.0"}


def hero_photos() -> dict:
    """Each spot's opening photo: an overview, historical, unlabelled, credited and dated (guideHero's rule)."""
    out = {}
    for path in sorted(GUIDES.glob("*.toml")):
        guide = tomllib.loads(path.read_text())
        for p in guide.get("photo", []):
            if (p.get("topic") == "overview" and p.get("status") == "historical" and not p.get("labels")
                    and p.get("credit") and p.get("taken") and (GUIDES / "photos" / str(p.get("file"))).is_file()):
                out[path.stem] = {"file": p["file"], "w": p.get("width", 640), "h": p.get("height", 480), "credit": p["credit"],
                                  "taken": str(p["taken"]), "caption": p.get("caption", ""), "title": p.get("title", ""),
                                  "source": p.get("source", ""), "licence": p.get("licence", ""),
                                  "licence_name": LICENCES.get(p.get("licence", ""), "")}
                break
    return out


class Handler(SimpleHTTPRequestHandler):
    data: Path
    offline = False

    def log_message(self, fmt, *args):   # one quiet line per miss, nothing per hit
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        rel = unquote(urlsplit(path).path).lstrip("/")
        if ".." in Path(rel).parts:
            return str(SITE / "__missing__")
        if rel.startswith("fonts/"):
            return str(FONTS / rel[len("fonts/"):])
        if rel.startswith("guides/photos/"):
            return str(GUIDES / "photos" / rel[len("guides/photos/"):])
        if rel.startswith("data/"):
            return str(self.data / rel[len("data/"):])
        if rel.endswith("/") or rel == "":
            rel += "index.html"
        return str(SITE / rel)

    def do_GET(self):
        rel = unquote(urlsplit(self.path).path).lstrip("/")
        if rel == "":
            return self.redirect("/preview/")
        if rel == "data/hero-photos.json":
            return self.send_json(hero_photos())
        target = Path(self.translate_path(self.path))
        if rel.startswith("data/") and not target.is_file() and not self.offline:
            self.fetch_live(rel, target)
        if not target.is_file() and not rel.startswith(("preview/", "data/", "fonts/", "guides/", "icons/")) \
                and rel not in ("levels.js", "eatoday.js"):
            return self.redirect(f"{LIVE}/{rel}")
        return super().do_GET()

    def fetch_live(self, rel: str, target: Path) -> None:
        try:
            req = urllib.request.Request(f"{LIVE}/{rel}", headers={"User-Agent": "swimsignal-local-preview"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        except Exception:   # a spot with no overflow upstream has no upstream file: the page says what it has
            pass

    def redirect(self, to: str) -> None:
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()

    def send_json(self, value) -> None:
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--data", type=Path, default=ROOT / ".preview-data")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    Handler.data, Handler.offline = args.data.resolve(), args.offline
    print(f"Redesign preview: http://localhost:{args.port}/preview/   (forecast files in {args.data})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
