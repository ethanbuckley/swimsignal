"""A local copy of the redesign preview in src/dipcast/site/preview/, on the live forecast.

    python3 scripts/preview_redesign.py            # then open http://localhost:8797/preview/
    python3 scripts/preview_redesign.py --data DIR  # keep the forecast files in DIR (default: .preview-data/)
    python3 scripts/preview_redesign.py --offline   # serve only what DIR already holds
    python3 scripts/preview_redesign.py --built site/preview   # the pages as a build wrote them, answers in the HTML

It serves the source files as they are, so an edit shows on reload:

- /preview/, /levels.js, /eatoday.js, /icons/   from src/dipcast/site/
- /fonts/                                       from src/dipcast/pages/fonts/
- /guides/photos/                               from guides/photos/
- /preview/spot/<id>/                           a place's own page: the opening's file with a <base>, as the build
                                                writes it, without the place's own head or built answer
- /preview/map.json                             the map tiles: OpenStreetMap's, as a build with no provider
- /preview/hero-photos.json                     made here from guides/*.toml by the build's own rule for the photo
                                                that opens a place (src/dipcast/hero_photos.py)
- /data/...                                     from DIR; a file DIR lacks is fetched once from swimsignal.co.uk
                                                and kept, so the levels and times are a real issue of the forecast
- anything else (about.html, plan/, ...)        a redirect to the live site, so the preview's links to it work

The build publishes the same files at <site>/preview/ (scripts/build_site.py, write_preview). This script is not
part of the build.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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
sys.path.insert(0, str(ROOT / "src"))
from dipcast.hero_photos import hero  # noqa: E402  (standard library only: the build's own rule for the photo)


def map_tiles() -> dict:
    """The map's tiles as the build writes them without a provider chosen (build_site.preview_map): OpenStreetMap's
    own, with the colour filter index.html carries. The build's file names the live site's provider and its key."""
    found = re.search(r'<filter id="tiles".*?</filter>', (SITE / "index.html").read_text(), re.DOTALL)
    return {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "credit": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            "filter": found.group(0) if found else ""}


def hero_photos() -> dict:
    """Each spot's opening photo, from guides/<id>.toml by the build's rule, for the files that exist."""
    out = {}
    for path in sorted(GUIDES.glob("*.toml")):
        h = hero(tomllib.loads(path.read_text()).get("photo"))
        if h and (GUIDES / "photos" / h["file"]).is_file():
            out[path.stem] = h
    return out


class Handler(SimpleHTTPRequestHandler):
    data: Path
    offline = False
    built: Path | None = None

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
        if rel == "preview/hero-photos.json":
            return self.send_json(hero_photos())
        if rel == "preview/map.json":
            return self.send_json(map_tiles())
        if self.built and re.fullmatch(r"preview/(spot/[A-Za-z0-9_-]+/)?(index\.html)?", rel):
            page = self.built / rel[len("preview/"):] / ("" if rel.endswith(".html") else "index.html")
            if page.is_file():   # the page as the build wrote it, with its head and its answer in the HTML
                return self.send_page(page.read_bytes())
        if re.fullmatch(r"preview/spot/[A-Za-z0-9_-]+/(index\.html)?", rel):
            return self.send_place()
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

    def send_place(self) -> None:
        """A place's own page, preview/spot/<id>/: the opening's file with a <base> back to preview/, as the build
        writes it (build_site.preview_place_page), but without the place's own <head> or its built answer."""
        page = (SITE / "preview" / "index.html").read_text().replace("<title>", '<base href="../../">\n<title>', 1)
        self.send_page(page.encode())

    def send_page(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
    ap.add_argument("--built", type=Path, default=None,
                    help="a preview/ folder the build wrote (build_site.write_preview): its pages are served in place of the source's")
    args = ap.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    Handler.data, Handler.offline = args.data.resolve(), args.offline
    Handler.built = args.built.resolve() if args.built else None
    print(f"Redesign preview: http://localhost:{args.port}/preview/   (forecast files in {args.data})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
