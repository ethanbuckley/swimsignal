"""Printable signs for the listed spots, spot/<id>/sign/, and the QR code each one carries.

A sign gives the spot's name, one line on what SwimSignal forecasts, a QR code and the short address
of the spot's page, the caveat, and where the credits are. It gives no level: printed, a level would
be out of date within hours. The QR codes are SVG made here, at build time, with segno (BSD 3-Clause
licence, https://github.com/heuer/segno), so the page needs no script and the sign prints sharp at
any size. scripts/build_site.py (write_pages) writes a sign and a QR file for every spot with a page.
"""

from __future__ import annotations

import io
import re
from html import escape
from pathlib import Path

import segno

TEMPLATE = Path(__file__).parent / "site" / "sign.html"
SLOT = re.compile(r"\{\{(\w+)\}\}")
# What a sign says about the data behind the forecast it points to. It shows none of that data, so it
# names where the credits are (the terms page) rather than carrying them all; "not run by or connected
# with" is the terms' own wording ("Who runs SwimSignal"), there because a sign at the water could be
# taken for an official notice.
CREDIT = "SwimSignal is independent: not run by or connected with the Environment Agency or any water company. Data credits: {terms}"
# A spot from OpenStreetMap shows OpenStreetMap's data (its name and position), so its sign carries the
# notice ODbL 4.3 asks for, as the spot's page does (build_site.OSM_CREDIT, the terms' "Swim spot locations").
OSM_CREDIT = "Location © OpenStreetMap contributors, ODbL 1.0: openstreetmap.org/copyright."


def page_url(root: str, spot_id: str) -> str:
    """The spot's page, which the QR code opens."""
    return f"{root}spot/{spot_id}/"


def short(url: str) -> str:
    """An address as it is printed: no scheme and no closing slash ("swimsignal.co.uk/spot/x")."""
    return re.sub(r"^https?://", "", url).rstrip("/")


def code(url: str) -> segno.QRCode:
    """The QR code for an address. Error correction Q, so a quarter of the code can be lost and it still
    reads: a sign outdoors gets wet, creased and dirty. segno raises the level further where that costs
    no extra size (boost_error, its default)."""
    return segno.make(url, error="q", micro=False)


def qr_inline(url: str) -> str:
    """The code as an SVG element for the sign: no size of its own (the sheet sizes it), a four-module
    quiet zone round it, and its address as its accessible name."""
    svg = code(url).svg_inline(scale=1, border=4, omitsize=True, svgclass="qr", lineclass=None)
    return svg.replace("<svg ", f'<svg role="img" aria-label="QR code for {escape(short(url))}" ', 1)


def qr_file(url: str) -> str:
    """The code as an SVG file, spot/<id>/qr.svg, on white, for the live sign (embed.js) to show as an image."""
    out = io.BytesIO()
    code(url).save(out, kind="svg", scale=1, border=4, omitsize=True, light="#fff", xmldecl=True)
    return out.getvalue().decode()


def credit(spot: dict, root: str) -> str:
    line = CREDIT.format(terms=short(f"{root}terms.html#data"))   # last, so the address ends the line
    return escape((f"{OSM_CREDIT} " if spot.get("source") == "openstreetmap" else "") + line)


def sign_page(spot: dict, root: str, mark: str, template: str | None = None) -> str:
    """The sign's page for one spot, from sign.html. `mark` is the brand mark's inline SVG (build_site.MARK)."""
    url = page_url(root, spot["id"])
    slots = {
        "name": escape(spot["name"]),
        "mark": mark,
        "qr": qr_inline(url),
        # A line break may fall after "spot/", where a long id would otherwise break mid-word.
        "short": escape(short(url)).replace("/spot/", "/spot/<wbr>", 1),
        "credit": credit(spot, root),
        "live": escape(f"embed.html?spot={spot['id']}&screen"),
        "organisers": escape(f"organisers.html#spot={spot['id']}"),
    }
    html = template if template is not None else TEMPLATE.read_text()
    missing = {m for m in SLOT.findall(html)} - slots.keys()
    if missing:
        raise ValueError(f"sign.html has slots this build does not fill: {sorted(missing)}")
    return SLOT.sub(lambda m: slots[m.group(1)], html)
