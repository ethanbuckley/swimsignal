"""Make a photo ready for a spot's practical guide (guides/README.md):

    uv run --with pillow python scripts/guide_photo.py ~/Downloads/IMG_1234.HEIC.jpg cromwheel-shingle.jpg

It turns the picture the right way up, shrinks it to 1600 px on its long side, and saves it as a
JPEG in guides/photos/ with nothing else in the file: no location, camera, owner or time stamps, so a
swimmer's photo does not publish where they live or what phone they carry. Then it prints the
[[photo]] lines to paste into the guide, with the width and height filled in.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "guides" / "photos"
LONG_SIDE = 1600
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,78}\.jpe?g")   # as src/dipcast/guides.py accepts


def prepare(src: Path, dst: Path, long_side: int = LONG_SIDE) -> tuple[int, int]:
    """Upright, at most long_side pixels on the long side, re-encoded with no metadata. Returns (w, h)."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
        # A new image from the pixels alone: nothing of the original's EXIF, XMP or ICC comes with it.
        clean = Image.new("RGB", im.size)
        clean.paste(im)
        dst.parent.mkdir(parents=True, exist_ok=True)
        clean.save(dst, "JPEG", quality=82, optimize=True, progressive=True)
        return clean.size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", type=Path, help="the photo as it came off the camera or phone")
    ap.add_argument("name", help="the file name in guides/photos/: lower case, hyphens, ending .jpg")
    a = ap.parse_args(argv)
    if not NAME.fullmatch(a.name):
        print(f"{a.name!r}: use lower case letters, digits and hyphens, ending .jpg", file=sys.stderr)
        return 2
    w, h = prepare(a.source, PHOTOS / a.name)
    print(f"Saved guides/photos/{a.name}, {w} x {h}. Paste into the guide and fill in the rest:\n")
    print(f'[[photo]]\nfile = "{a.name}"\nwidth = {w}\nheight = {h}\ncaption = ""\ncredit = ""\ntaken = YYYY-MM-DD\n'
          'status = "confirmed"   # with seen = YYYY-MM-DD; or "suggested" with from and on\n'
          '# [[photo.label]]\n# x = 50   # per cent across, from the left\n# y = 50   # per cent down, from the top\n# text = ""')
    return 0


if __name__ == "__main__":
    sys.exit(main())
