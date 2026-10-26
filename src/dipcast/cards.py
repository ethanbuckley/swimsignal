"""Pictures of the forecast to post to Instagram and Facebook groups, with a caption to paste.

Two kinds, each drawn at 1080 x 1350 (Instagram's portrait) and 1080 x 1080 (square, Facebook):

- A weekend card for each area in AREAS: a row for each spot, its level on the two days. The days
  are the coming Saturday and Sunday, or today and tomorrow when the forecast was issued on a
  Saturday or a Sunday. Before Wednesday the five days do not reach Sunday, so there is no card.
- A storm card: the spots with monitored overflows upstream discharging now, most first, with when
  right now's risk from spills should be back to low if they stop. With none discharging there is
  no card, never an "all clear" one: an overflow with no current reading is not a quiet one.

The levels are the page's own. They come from alerts.json, which scripts/alerts.js writes by running
src/dipcast/site/levels.js, so a card says what the spot's page says on that day. Nothing here works
a level out. The storm card reads each spot's `now` block from spots.json, as the "Right now" tile
does, and words its clearing time as that tile's sentence does (index.html, clearSentence).

scripts/build_site.py writes them to site/cards/ with an unlisted page, cards/index.html, that shows
them with their captions and download links.

A third kind is not for posting: each spot's share card, cards/spot/<id>.png at 1200 x 630, the picture
a link to the spot's page shows in a messaging app (its og:image). The spot's name, its headline from
alerts.json and when the forecast was issued, since a preview is kept for days (write_spot_cards). scripts/make_cards.py makes them from the live site's
data. Drawn with Pillow in the site's own faces (docs/DESIGN.md): Source Serif 4 for names and
headings, Source Sans 3 for levels and the rest, read from the WOFF2 files the site serves.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
FONTS = HERE / "pages" / "fonts"
SERIF = FONTS / "SourceSerif4-latin.woff2"   # weight 600 only, variable optical size 8-60
SANS = FONTS / "SourceSans3-latin.woff2"     # variable weight 200-900
ICON_PNG = HERE / "site" / "icons" / "icon-512.png"
ICON_SVG = HERE / "site" / "icons" / "icon.svg"
LONDON = ZoneInfo("Europe/London")
BRAND = "SwimSignal"


# ------------------------------------------------------------------------------ the areas
@dataclass(frozen=True)
class Area:
    """A weekend card: its file name, its title, and its spots as (id, the name on the card), in
    the order of the rows. The card's title names the river or the area, so a row's name is the
    place alone. Keep a row's name free of commas: the line about poor ratings lists them."""
    slug: str
    title: str
    spots: tuple[tuple[str, str], ...]


# To add an area, add an Area. Ids are the spots' ids in spots.csv and spots-osm.csv; an id that is
# not in the forecast is left out of the card and named in the build log. Seven rows fit the square
# card with room to spare; a row whose level does not change from day to day (nothing monitored
# upstream) goes in a line under the table instead.
AREAS: tuple[Area, ...] = (
    Area("wharfe", "River Wharfe", (   # downstream order
        ("wharfe-linton-falls", "Linton Falls"),
        ("wharfe-burnsall", "Burnsall"),
        ("wharfe-appletreewick", "Appletreewick"),
        ("wharfe-bolton-abbey", "Bolton Abbey"),
        ("bw-uke4100-08901", "Ilkley (Cromwheel)"),
        ("osm-wharfe-greenholme", "Greenholme"),
        ("bw-uke4200-08904", "Wetherby (Wilderness)"),
    )),
    Area("thames-oxford", "Upper Thames and Oxford", (
        ("thames-lechlade", "Lechlade"),
        ("thames-buscot-weir", "Buscot Weir"),
        ("bw-ukj1402-11946", "Wolvercote Mill Stream"),
        ("thames-port-meadow", "Port Meadow"),
        ("osm-thames-long-bridges", "Long Bridges"),
        ("thames-clifton-hampden", "Clifton Hampden"),
    )),
    Area("lakes", "Lake District", (
        ("bw-ukd1203-45650", "Windermere (Bowness)"),
        ("bw-ukd1230-45750", "Coniston Water"),
        ("bw-ukd1101-45800", "Derwent Water"),
        ("ullswater-glenridding", "Ullswater (Glenridding)"),
        ("grasmere", "Grasmere"),
        ("rydal-water", "Rydal Water"),
        ("buttermere", "Buttermere"),
        ("wastwater", "Wastwater"),
    )),
    Area("cam", "River Cam", (
        ("cam-grantchester", "Grantchester Meadows"),
        ("bw-ukh1201-09801", "Sheep's Green"),
    )),
    Area("dart-teign", "Dart and Teign", (
        ("dart-sharrah-pool", "Sharrah Pool (Dart)"),
        ("dart-spitchwick", "Spitchwick (Dart)"),
        ("osm-dart-dartington", "Dartington (Dart)"),
        ("osm-teign-drogo-weir", "Drogo Weir (Teign)"),
        ("teign-fingle-bridge", "Fingle Bridge (Teign)"),
    )),
)


# ------------------------------------------------------------------------------ the words
LEVELS = ("low", "moderate", "high", "very high")   # levels.js ORDER
CAVEAT = "A forecast, not a water test."
# The overflow companies' data is on the storm card, so their credit is: CC BY 4.0 s.3(a) asks for it
# wherever the data is shown (build_site.data_credits has the full one, the terms page every one).
OVERFLOW_CREDIT = ("Overflow data: water companies via the National Storm Overflow Hub, CC BY 4.0. "
                   "Combined and modelled by SwimSignal.")
MAX_STORM_ROWS = 8


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


# Reviewed official advice (spots.json `official`, src/dipcast/official_advice.py), in the compact form the
# site's rows use: eatoday.js eaTodayBrief, line for line, so a card says what the list says
# (tests/test_cards.py checks the two agree). It never changes a level; a card shows it beside the level.
OFFICIAL_STATES = {"checked", "stale", "unverified", "gone", "changed"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _short_day(iso) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{int(m[3])} {MONTHS[int(m[2]) - 1]}" if m and 1 <= int(m[2]) <= 12 else ""


def official_brief(spot: dict) -> str:
    """'EA advice against bathing · since 19 Jun · checked 26 Oct', or '' without advice."""
    items = [o for o in (spot.get("official") or []) if isinstance(o, dict) and isinstance(o.get("line"), str) and o["line"]
             and isinstance(o.get("publisher"), str) and o["publisher"] and o.get("state") in OFFICIAL_STATES
             and _short_day(o.get("checked"))]
    if not items:
        return ""
    o = items[0]
    said = re.sub(r"^[^:]*:\s*", "", o["line"], count=1)
    said = re.sub(r"\s+since\s.*$", "", re.sub(r"\s*\(.*$", "", said, count=1), count=1)
    who = "EA" if o["publisher"] == "Environment Agency" else o["publisher"]
    since, checked = _short_day(o.get("since")), _short_day(o["checked"])
    parts = [f"{who} {said}", f"since {since}" if since else "",
             f"checked {checked}" if o["state"] == "checked" else f"not re-checked since {checked}",
             f"{len(items) - 1} more" if len(items) > 1 else ""]
    return " · ".join(p for p in parts if p)


def official_words(brief: str) -> str:
    """The advice as a card or caption says it, apart from the level."""
    return f"Official: {brief}. Follow it first; the level is SwimSignal's sewage forecast only."


def and_list(words: list[str]) -> str:
    return words[0] if len(words) < 2 else f"{', '.join(words[:-1])} and {words[-1]}"


def day_date(iso: str, month: bool = True) -> str:
    """'Saturday 17 October', or 'Saturday 17' without the month."""
    d = date.fromisoformat(iso)
    return f"{d:%A} {d.day}" + (f" {d:%B}" if month else "")


def two_days(days: list[str]) -> str:
    """'Saturday 17 and Sunday 18 October'; the month twice when they differ."""
    a, b = (date.fromisoformat(x) for x in days)
    return f"{day_date(days[0], month=a.month != b.month)} and {day_date(days[1])}"


def issued(generated_at: str, short: bool = True) -> str:
    """'Forecast issued Sun 11 Oct, 14:09' (the card) or 'Forecast issued Sunday 11 October at 14:09'."""
    t = datetime.fromisoformat(generated_at).astimezone(LONDON)
    return (f"Forecast issued {t:%a} {t.day} {t:%b}, {t:%H:%M}" if short
            else f"Forecast issued {t:%A} {t.day} {t:%B} at {t:%H:%M}")


# index.html, partOfDay: the part of the day a time falls in, in UK time.
DAY_PARTS = ((6, "overnight"), (12, "morning"), (18, "afternoon"), (24, "evening"))


def part_of_day(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(LONDON)
    part = next(p for end, p in DAY_PARTS if t.hour < end)
    return f"overnight into {t:%A}" if part == "overnight" else f"by about {t:%A} {part}"


# ------------------------------------------------------------------------------ choosing what to show
def weekend_days(dates: list[str]) -> list[str] | None:
    """The two days a weekend card shows, from the forecast's dates (alerts.json `dates`, today
    first): on a Saturday or a Sunday, today and tomorrow; on a weekday, the coming Saturday and
    Sunday. None when the forecast does not reach both (Monday and Tuesday)."""
    if not dates:
        return None
    today = date.fromisoformat(dates[0])
    first = today if today.weekday() >= 5 else today + timedelta(days=5 - today.weekday())
    days = [first.isoformat(), (first + timedelta(days=1)).isoformat()]
    return days if all(d in dates for d in days) else None


def spot_levels(alerts: dict) -> dict[str, dict]:
    """alerts.json as each spot's level and headline on each forecast date: {id: {name, url, level,
    headline, days: {iso: (level, headline) or None} or None}}. `days` is None where the level does
    not change from day to day (levels.js daily() is false), and the spot's own level holds."""
    words, dates = alerts.get("words", []), alerts.get("dates", [])
    out = {}
    for sid, s in alerts.get("spots", {}).items():
        days = None
        if s.get("days") is not None:
            days = {iso: (None if x is None else (x[0], words[x[1]])) for iso, x in zip(dates, s["days"])}
        out[sid] = {"name": s.get("name", sid), "url": s.get("url"), "level": s.get("level"),
                    "headline": s.get("headline", ""), "days": days}
    return out


@dataclass
class Row:
    id: str
    label: str
    cells: list[str | None]   # a level on each day, or None for no forecast that day
    poor: bool = False        # rated poor: at least high on every day, whatever the forecast
    official: str = ""        # official_brief: advice beside the level, never in it


@dataclass
class WeekendCard:
    area: Area
    days: list[str]
    rows: list[Row]
    plain: list[tuple[str, str, list[str]]] = field(default_factory=list)   # (headline, level, names)
    missing: list[str] = field(default_factory=list)                        # ids not in the forecast

    @property
    def ids(self) -> list[str]:
        return [sid for sid, _ in self.area.spots if sid not in self.missing]


def weekend_card(area: Area, levels: dict[str, dict], days: list[str], advice: dict[str, str] | None = None) -> WeekendCard | None:
    """An area's card for two days, or None when none of its spots is in the forecast. A spot whose
    level is one of the four goes in a row; one with a plain level ("No monitored overflow found upstream")
    goes in a line under the table, in the page's words."""
    card = WeekendCard(area, days, [])
    plain: dict[str, tuple[str, list[str]]] = {}
    for sid, label in area.spots:
        s = levels.get(sid)
        if s is None:
            card.missing.append(sid)
            continue
        if s["days"] is None:
            if s["level"] in LEVELS:   # a standing level, a rating's or the algae's: the same both days
                card.rows.append(Row(sid, label, [s["level"]] * len(days), poor="rated poor" in s["headline"]))
            else:
                plain.setdefault(s["headline"], (s["level"], []))[1].append(label)
            continue
        got = [s["days"].get(iso) for iso in days]
        cells = [x[0] if x and x[0] in LEVELS else None for x in got]
        card.rows.append(Row(sid, label, cells, poor=any(x and "rated poor" in x[1] for x in got)))
    card.plain = [(h, lv, names) for h, (lv, names) in plain.items()]
    for r in card.rows:
        r.official = (advice or {}).get(r.id, "")
    if not card.rows and not card.plain:
        return None
    return card


@dataclass
class StormRow:
    id: str
    name: str
    discharging: int
    monitored: int
    clears: str   # when right now's risk from spills should be low if they stop, or ""


def clear_words(now: dict, generated_at: str) -> str:
    """index.html's clearSentence, first part, for a card: only while right now is above low and
    the time is still ahead."""
    at, label = now.get("clears_at"), now.get("label")
    if not at or label not in LEVELS[1:]:
        return ""
    if datetime.fromisoformat(at) <= datetime.fromisoformat(generated_at):
        return ""
    k = now.get("discharging_upstream") or 0
    who = "If it stops now" if k == 1 else "If they stop now" if k else "If no new spill starts"
    return f"{who}, the model expects low risk from spills {part_of_day(at)}."


def storm_rows(spots: list[dict], generated_at: str) -> list[StormRow]:
    """The spots with monitored overflows upstream discharging now, the most first, then the larger
    share of those monitored, then by name. Empty when none is: then there is no storm card."""
    rows = []
    for s in spots:
        n = s.get("now") or {}
        k = n.get("discharging_upstream") or 0
        if s.get("error") or k <= 0:
            continue
        mon = n.get("monitored_upstream")
        if mon is None:
            mon = (s.get("upstream_summary") or {}).get("overflows") or k
        rows.append(StormRow(s["id"], s["name"], min(k, mon), mon, clear_words(n, generated_at)))
    return sorted(rows, key=lambda r: (-r.discharging, -r.discharging / max(r.monitored, 1), r.name))


def storm_count(r: StormRow) -> str:
    return f"of {r.monitored} monitored overflow{'s' if r.monitored != 1 else ''} upstream discharging now"


# ------------------------------------------------------------------------------ captions
def list_url(root: str, name: str, ids: list[str], day: str | None = None) -> str:
    """A shared list's link, as lists.js shareHash makes it: the spots open together on the Saved
    page, read only, on the day if it is still in the forecast."""
    return (f"{root}saved/#list={quote(name, safe='')}{f'&day={day}' if day else ''}"
            f"&spots={','.join(quote(i, safe='') for i in ids)}")


def cell_words(level: str | None) -> str:
    return f"{level} risk" if level else "no forecast"


def weekend_caption(card: WeekendCard, generated_at: str, root: str) -> str:
    d0 = date.fromisoformat(card.days[0])
    when = "this weekend" if d0.weekday() == 5 else "today and tomorrow"
    names = [day_date(x, month=False).split()[0] for x in card.days]
    lines = [f"{card.area.title} {when}: the pollution risk forecast for {two_days(card.days)}.", ""]
    for r in card.rows:
        if len(set(r.cells)) == 1:
            lines.append(f"{r.label}: {cell_words(r.cells[0])} both days.")
        else:
            lines.append(f"{r.label}: " + ", ".join(f"{cell_words(c)} on {n}" for c, n in zip(r.cells, names)) + ".")
        if r.official:
            lines[-1] += " " + official_words(r.official)
    for headline, _, who in card.plain:
        lines.append(f"{and_list(who)}: {headline[:1].lower() + headline[1:]}.")
    poor = [r.label for r in card.rows if r.poor]
    if poor:
        lines += ["", poor_words(poor)]
    lines += ["", f"Each spot's five-day forecast: {root.removeprefix('https://').rstrip('/')}",
              f"These spots together: {list_url(root, card.area.title, card.ids, card.days[0])}",
              "", f"{issued(generated_at, short=False)}. {CAVEAT}"]
    return "\n".join(lines) + "\n"


def poor_words(names: list[str]) -> str:
    """levels.js poorAdvice, out of season, for a list of spots."""
    one = len(names) == 1
    return (f"{and_list(names)} {'is' if one else 'are'} rated poor by the Environment Agency, so "
            f"{'it stays' if one else 'they stay'} at high risk or worse.")


def storm_caption(rows: list[StormRow], generated_at: str, root: str) -> str:
    t = datetime.fromisoformat(generated_at).astimezone(LONDON)
    lines = [(f"Storm overflows discharging upstream of {len(rows)} swim spot{'s' if len(rows) != 1 else ''} "
             f"at {t:%H:%M} on {t:%A} {t.day} {t:%B}:"), ""]
    for r in rows[:20]:
        lines.append(f"{r.name}: {r.discharging} {storm_count(r)}." + (f" {r.clears}" if r.clears else ""))
    if len(rows) > 20:
        lines.append(f"And {len(rows) - 20} more.")
    lines += ["", f"Each spot's forecast: {root.removeprefix('https://').rstrip('/')}",
              "", f"{issued(generated_at, short=False)}. {CAVEAT}", OVERFLOW_CREDIT]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------ drawing
SIZES = {"portrait": (1080, 1350), "square": (1080, 1080)}
PAPER, INK, MUTED, LINE = "#f6f4ee", "#1b2328", "#5a6166", "#e0dbd0"
BAR, ON_FILL, BRAND_TEAL = "#3d5b5d", "#ffffff", "#0f5a61"
BAR_INK = "#e4e8e8"   # --bar-ink, white at 86% over the slate, as one colour
MARKS = {"low": "#3b7d4f", "moderate": "#b7791f", "high": "#c2552a", "very high": "#a32d2d"}
TEXTS = {"low": "#326a43", "moderate": "#855817", "high": "#a04623", "very high": "#992a2a"}
CLEAR_MARK, CLEAR_TEXT = "#4aa39a", "#0f5a61"   # no monitored overflow upstream: --clear, --k-clear
NA_MARK, NA_TEXT = "#98a2aa", "#4f5a62"         # no level: --unknown, --k-na
MIN_PX = 28   # nothing smaller: the card is seen at about a third of its size on a phone
M = 64        # the side margin


class Overflow(Exception):
    """The card's content does not fit."""


@lru_cache(maxsize=64)
def font(kind: str, size: int, weight: int = 400):
    """The site's faces at a size. The serif's optical size follows the size the card is seen at on
    a phone (about 375 of its 1080 pixels), so its strokes hold up small, as make_share_image.py does
    with the text cut."""
    from PIL import ImageFont

    if size < MIN_PX:
        raise ValueError(f"{size} px is under the {MIN_PX} px floor")
    f = ImageFont.truetype(str(SERIF if kind == "serif" else SANS), size)
    f.set_variation_by_axes([max(8, min(60, round(size * 375 / 1080)))] if kind == "serif" else [weight])
    return f


def wrap(draw, text: str, f, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=f) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def lh(f) -> int:
    return round(f.size * 1.25)


def paste_round(img, src, x: int, y: int, size: int, radius: int) -> None:
    """src at (x, y), size square, its corners rounded: the mask drawn four times over and scaled
    down, since Pillow's shapes have no smooth edges."""
    from PIL import Image, ImageDraw

    k = 4
    mask = Image.new("L", (size * k, size * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * k - 1, size * k - 1), radius=radius * k, fill=255)
    img.paste(src.convert("RGB").resize((size, size), Image.LANCZOS), (x, y), mask.resize((size, size), Image.LANCZOS))


def dot(img, cx: float, cy: float, d: int, colour: str) -> None:
    """A round mark, smooth-edged as paste_round's corners."""
    from PIL import Image, ImageColor, ImageDraw

    k = 4
    mask = Image.new("L", (d * k, d * k), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * k - 1, d * k - 1), fill=255)
    x, y = round(cx - d / 2), round(cy - d / 2)
    img.paste(ImageColor.getrgb(colour), (x, y, x + d, y + d), mask.resize((d, d), Image.LANCZOS))


def header(img, draw, w: int, h: int) -> int:
    """The site's header: the slate bar, the mark, the serif wordmark in white, the address on the
    right. Returns its height."""
    from PIL import Image

    mark = 64
    draw.rectangle((0, 0, w, h - 1), fill=BAR)
    paste_round(img, Image.open(ICON_PNG), M, (h - mark) // 2, mark, 14)   # --radius-mark, 6 of 28 px
    draw.text((M + mark + 22, h // 2), BRAND, font=font("serif", 46), fill=ON_FILL, anchor="lm")
    draw.text((w - M, h // 2), "swimsignal.co.uk", font=font("sans", 32, 600), fill=BAR_INK, anchor="rm")
    return h


def text_block(draw, x: int, y: int, text: str, f, fill: str, width: int, gap: int = 0) -> int:
    for line in wrap(draw, text, f, width):
        draw.text((x, y), line, font=f, fill=fill)
        y += lh(f) + gap
    return y


def footer(draw, w: int, h: int, lines: list[str]) -> int:
    """The foot, drawn up from the bottom: a hairline, then each line in the muted grey. Returns its top."""
    f = font("sans", 28, 500)
    wrapped = [ln for t in lines for ln in wrap(draw, t, f, w - 2 * M)]
    top = h - 48 - len(wrapped) * lh(f) - 24
    draw.rectangle((M, top, w - M, top + 1), fill=LINE)
    y = top + 24
    for ln in wrapped:
        draw.text((M, y), ln, font=f, fill=MUTED)
        y += lh(f)
    return top


@dataclass
class Style:
    title: int
    sub: int
    name: int
    cell: int
    pad: int      # above and below a row's text
    gap: int      # between the blocks


STYLES = {"portrait": Style(title=68, sub=32, name=36, cell=32, pad=20, gap=40),
          "square": Style(title=56, sub=30, name=32, cell=30, pad=12, gap=26)}


def draw_weekend(card: WeekendCard, generated_at: str, size: str):
    """The card as a Pillow image. Raises Overflow if the rows and lines do not fit."""
    from PIL import Image, ImageDraw

    w, h = SIZES[size]
    st = STYLES[size]
    img = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(img)
    y = header(img, draw, w, 124 if size == "portrait" else 112) + st.gap
    y = text_block(draw, M, y, card.area.title, font("serif", st.title), INK, w - 2 * M)
    y = text_block(draw, M, y + 4, f"Pollution risk forecast for {two_days(card.days)}", font("sans", st.sub), MUTED, w - 2 * M)
    foot_top = footer(draw, w, h, [f"{issued(generated_at)}. {CAVEAT}"])
    y += st.gap - 8

    # The table: "Pollution risk" over the two day columns, the days under it, then a row a spot.
    head = font("sans", 28, 600)
    day_w = 220
    xs = [w - M - (len(card.days) - i) * day_w for i in range(len(card.days))]
    name_w = xs[0] - M - 24
    draw.text((xs[0], y), "Pollution risk", font=head, fill=MUTED)
    y += lh(head) + 6
    draw.rectangle((xs[0], y, w - M, y), fill=LINE)
    y += 10
    draw.text((M, y), "Spot", font=head, fill=MUTED)
    for x, iso in zip(xs, card.days):
        draw.text((x, y), f"{date.fromisoformat(iso):%A}", font=head, fill=MUTED)
    y += lh(head) + 8
    draw.rectangle((M, y, w - M, y + 1), fill=LINE)

    name_f, cell_f, note_f = font("serif", st.name), font("sans", st.cell, 700), font("sans", 30, 600)
    plain = ("no overflows", "no river connection")   # the two plain levels, one colour as on the site
    notes = [(CLEAR_MARK if lv in plain else NA_MARK, CLEAR_TEXT if lv in plain else NA_TEXT,
              f"{headline} at {and_list(names)}.") for headline, lv, names in card.plain]
    poor = [r.label for r in card.rows if r.poor]
    if poor:
        notes.append((None, MUTED, poor_words(poor)))
    for r in card.rows:   # official advice under the table, in ink: the row's level is the sewage forecast alone
        if r.official:
            notes.append((None, INK, f"{r.label}: {official_words(r.official)}"))
    note_h = sum(len(wrap(draw, t, note_f, w - 2 * M - (40 if m else 0))) * lh(note_f) + 12 for m, _, t in notes)
    text_h = [len(wrap(draw, r.label, name_f, name_w)) * lh(name_f) for r in card.rows]
    room = foot_top - st.gap // 2 - y - (st.gap // 2 + note_h if notes else 0) - sum(text_h)
    pad = min(st.pad, room // (2 * len(card.rows))) if card.rows else st.pad   # closer rows before none
    if pad < 8:
        raise Overflow(f"{card.area.slug}: {len(card.rows)} rows and {len(notes)} notes do not fit the {size} card")
    rows_h = [t + 2 * pad for t in text_h]

    for r, rh in zip(card.rows, rows_h):
        mid = y + rh / 2
        lines = wrap(draw, r.label, name_f, name_w)
        ty = mid - len(lines) * lh(name_f) / 2
        for ln in lines:
            draw.text((M, ty + lh(name_f) / 2), ln, font=name_f, fill=INK, anchor="lm")
            ty += lh(name_f)
        for x, lv in zip(xs, r.cells):
            dot(img, x + 10, mid, 20, MARKS.get(lv, NA_MARK))
            draw.text((x + 34, mid), cap(lv) if lv else "No forecast", font=cell_f, fill=TEXTS.get(lv, NA_TEXT), anchor="lm")
        y += rh
        draw.rectangle((M, y, w - M, y), fill=LINE)
    y += st.gap // 2
    for mark, colour, text in notes:
        if mark:
            dot(img, M + 10, y + lh(note_f) / 2, 20, mark)
        y = text_block(draw, M + (40 if mark else 0), y, text, note_f, colour, w - 2 * M - (40 if mark else 0)) + 12
    return img


def draw_storm(rows: list[StormRow], generated_at: str, size: str):
    """The storm card as a Pillow image, with as many of rows (up to MAX_STORM_ROWS) as fit, and a
    line saying how many more there are."""
    from PIL import Image, ImageDraw

    w, h = SIZES[size]
    st = STYLES[size]
    img = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(img)
    y = header(img, draw, w, 124 if size == "portrait" else 112) + st.gap
    t = datetime.fromisoformat(generated_at).astimezone(LONDON)
    y = text_block(draw, M, y, "Overflows discharging now", font("serif", st.title), INK, w - 2 * M)
    sub = (f"Storm overflows upstream of {len(rows)} swim spot{'s' if len(rows) != 1 else ''} were discharging "
           f"at {t:%H:%M} on {t:%A} {t.day} {t:%B}.")
    y = text_block(draw, M, y + 4, sub, font("sans", st.sub), MUTED, w - 2 * M) + st.gap - 16
    foot_top = footer(draw, w, h, [OVERFLOW_CREDIT, f"{issued(generated_at)}. {CAVEAT}"])
    draw.rectangle((M, y, w - M, y + 1), fill=LINE)

    name_f, count_f, clear_f = font("serif", st.name), font("sans", 30, 700), font("sans", 28, 400)
    more_f = font("sans", 30, 600)
    text_w = w - 2 * M

    def row_lines(r: StormRow):
        return (wrap(draw, r.name, name_f, text_w), wrap(draw, f"{r.discharging} {storm_count(r)}", count_f, text_w),
                wrap(draw, r.clears, clear_f, text_w) if r.clears else [])

    def row_h(r: StormRow) -> int:
        n, c, k = row_lines(r)
        return len(n) * lh(name_f) + 4 + len(c) * lh(count_f) + len(k) * lh(clear_f) + 2 * st.pad

    shown: list[StormRow] = []
    used = 0
    for r in rows[:MAX_STORM_ROWS]:
        more = len(rows) - len(shown) - 1
        need = used + row_h(r) + (lh(more_f) + st.pad if more > 0 else 0)
        if y + need > foot_top - st.gap // 2:
            break
        shown.append(r)
        used += row_h(r)
    if not shown:
        raise Overflow(f"no storm row fits the {size} card")
    for r in shown:
        n, c, k = row_lines(r)
        ty = y + st.pad
        for ln in n:
            draw.text((M, ty), ln, font=name_f, fill=INK)
            ty += lh(name_f)
        ty += 4
        for ln in c:   # an overflow discharging now is the very-high brick (docs/DESIGN.md, Colour)
            draw.text((M, ty), ln, font=count_f, fill=TEXTS["very high"])
            ty += lh(count_f)
        for ln in k:
            draw.text((M, ty), ln, font=clear_f, fill=MUTED)
            ty += lh(clear_f)
        y += row_h(r)
        draw.rectangle((M, y, w - M, y), fill=LINE)
    rest = len(rows) - len(shown)
    if rest > 0:
        draw.text((M, y + st.pad), f"And {rest} more spot{'s' if rest != 1 else ''}: each spot's page on swimsignal.co.uk.",
                  font=more_f, fill=BRAND_TEAL)
    return img


# ------------------------------------------------------------------------------ a spot's share card
# The picture a link to a spot's page shows in a messaging app or a feed (its og:image), at the size those
# expect. It carries the level, which a cached preview keeps for days, so when the forecast was issued
# sits right under it, in ink, not in the grey foot. Remade with each build.
SHARE_SIZE = (1200, 630)
PLAIN = ("no overflows", "no river connection")   # the two plain levels, one colour as on the site


def spot_where(spot: dict) -> str:
    """'Lake · Windermere (N Basin)': the kind, and the water it is on where the trace names it. 'River
    Wharfe' alone, not 'River · River Wharfe'."""
    kind, water = cap(str(spot.get("kind") or "")), (spot.get("location") or {}).get("watercourse")
    return water if water and kind and kind.lower() in water.lower().split() else " · ".join(x for x in [kind, water] if x)


def level_colours(level: str | None) -> tuple[str, str]:
    """A level's mark and text colours, as the site's (docs/DESIGN.md)."""
    if level in PLAIN:
        return CLEAR_MARK, CLEAR_TEXT
    return MARKS.get(level, NA_MARK), TEXTS.get(level, NA_TEXT)


def draw_spot(name: str, where: str, level: str | None, headline: str, generated_at: str, official: str = ""):
    """A spot's share card as a Pillow image: its name, where it is, the headline from levels.js
    (alerts.json) beside the level's mark, any official advice (official_brief) on its own line under it,
    when it was issued, and the caveat. The name steps down a
    size before it takes a third line; raises Overflow if it still does not fit."""
    from PIL import Image, ImageDraw

    w, h = SHARE_SIZE
    width = w - 2 * M
    img = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(img)
    top = header(img, draw, w, 104) + 32
    foot_top = footer(draw, w, h, [f"{CAVEAT} The latest is on the spot's page."])
    head_f, when_f, where_f = font("sans", 44, 700), font("sans", 32, 500), font("sans", 30, 400)
    mark, text = level_colours(level)
    head = wrap(draw, headline, head_f, width - 44)
    said, said_f = f"Official: {official}." if official else "", font("sans", 30, 600)   # one line: the alt text has the rest
    said_h = len(wrap(draw, said, said_f, width - 44)) * lh(said_f) + 10 if said else 0
    # With the advice line, a name that still does not fit at the smallest size loses where it is (the page
    # says it), rather than the card being left out: the advice must not cost the card.
    for size, show_where in [(s, True) for s in (60, 52, 44)] + ([(44, False)] if said else []):
        name_f = font("serif", size)
        lines = wrap(draw, name, name_f, width)
        need = len(lines) * lh(name_f) + (8 + lh(where_f) if show_where else 0) + 24 + len(head) * lh(head_f) + said_h + 8 + lh(when_f)
        if len(lines) <= 2 and top + need <= foot_top - 24:
            break
    else:
        raise Overflow(f"{name}: the name and headline do not fit the share card")
    y = text_block(draw, M, top + (foot_top - 24 - top - need) // 2, name, name_f, INK, width)   # in the middle of the room
    y = (text_block(draw, M, y + 8, where, where_f, MUTED, width) if show_where else y) + 24
    dot(img, M + 12, y + lh(head_f) * 0.56, 24, mark)   # on the words' middle, a little under the line's
    y = text_block(draw, M + 44, y, headline, head_f, text, width - 44) + 8
    if said:   # in ink, never the level's colour: it is not part of the level
        y = text_block(draw, M + 44, y + 2, said, said_f, INK, width - 44) + 8
    draw.text((M + 44, y), issued(generated_at), font=when_f, fill=INK)
    return img


def write_spot_cards(out: Path, spots: list[dict], alerts: dict | None, generated_at: str) -> dict[str, str]:
    """out/<id>.png for each spot with a page and a level in alerts.json (the page's own words). Earlier
    ones go first, so a spot dropped from the lists loses its card. Returns {id: the card's alt text};
    a spot whose card failed is left out and logged, and its page keeps the shared picture."""
    import shutil

    shutil.rmtree(out, ignore_errors=True)
    if not alerts or alerts.get("generated_at") != generated_at:
        return {}
    out.mkdir(parents=True)
    made = {}
    for s in spots:
        a = (alerts.get("spots") or {}).get(s["id"])
        if not a or not re.fullmatch(r"[A-Za-z0-9_-]+", str(s["id"])):
            continue
        try:
            o = official_brief(s)
            draw_spot(s["name"], spot_where(s), a.get("level"), a.get("headline") or "", generated_at, o).save(
                out / f"{s['id']}.png", "PNG", optimize=True)
            made[s["id"]] = f"{s['name']}: {a.get('headline')}.{' ' + official_words(o) if o else ''} {issued(generated_at)}."
        except Exception as e:  # noqa: BLE001 - one card must not stop the others, or the site
            log.warning("share card for %s not made: %s", s["id"], e)
    return made


# ------------------------------------------------------------------------------ the files and the page
def save_both(out: Path, stem: str, draw) -> list[tuple[str, str]]:
    """A card at both sizes, saved only once both have been drawn: [(label, file name)], portrait first."""
    imgs = {size: draw(size) for size in SIZES}
    files = []
    for size, (w, h) in SIZES.items():
        name = f"{stem}-{w}x{h}.png"
        imgs[size].save(out / name, "PNG", optimize=True)
        files.append((f"{size.capitalize()}, {w} × {h}", name))
    return files


def mark_svg() -> str:
    """The icon, inline, as every header carries it."""
    s = ICON_SVG.read_text()
    s = re.sub(r"<title>.*?</title>|<!--.*?-->", "", s, flags=re.DOTALL)
    s = re.sub(r'\s(?:width|height)="\d+"', "", s, count=2).replace("<svg ", '<svg aria-hidden="true" ', 1)
    return re.sub(r">\s+<", "><", s).strip()


def page(root: str, generated_at: str, made: list[dict], notes: list[str]) -> str:
    """cards/index.html: each card with its two sizes to download and its caption to copy. Unlisted:
    noindex, in no sitemap and linked from no page."""
    r = escape(root)
    rows = lambda t: sum(max(1, -(-len(ln) // 48)) for ln in t.splitlines()) + 1
    parts = []
    for i, c in enumerate(made):
        files = " · ".join(f'<a href="{escape(f)}" download>{escape(label)}</a>' for label, f in c["files"])
        alt = escape(c["caption"].splitlines()[0])
        # The caption in a field, read only: on a phone, a tap and "Select all" copies it whole.
        parts.append(f'<h2>{escape(c["title"])}</h2>\n<p>{files}</p>\n'
                     f'<p><img src="{escape(c["files"][0][1])}" width="1080" height="1350" alt="{alt}" '
                     f'style="width:100%;height:auto;display:block"></p>\n'
                     f'<label for="caption-{i}">Caption</label>\n'
                     f'<textarea id="caption-{i}" readonly rows="{rows(c["caption"])}">{escape(c["caption"])}</textarea>\n'
                     f'<p class="hint">Also as a text file: '
                     f'<a href="{escape(c["caption_file"])}">{escape(c["caption_file"])}</a></p>')
    note_html = "".join(f"<p>{escape(n)}</p>\n" for n in notes)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>Cards to share · {BRAND}</title><meta name="robots" content="noindex">\n'
        '<meta name="theme-color" content="#3d5b5d">\n'
        f'<link rel="icon" href="{r}icons/icon.svg" type="image/svg+xml">\n'
        f'<link rel="stylesheet" href="{r}page.css">\n'
        f'</head><body>\n<header class="top"><a class="brand" href="{r}">{mark_svg()}{BRAND}</a></header>\n'
        '<main class="doc"><h1>Cards to share</h1>\n'
        f'<p class="lead">Pictures of the forecast for Instagram and Facebook, remade with each update. {escape(issued(generated_at, short=False))}.</p>\n'
        '<p>Each card comes in two sizes: portrait for Instagram, square for Facebook. Tap a size to save it, '
        'then copy the caption under it. This page is not linked from the site.</p>\n'
        f'{note_html}' + "\n".join(parts) + '</main>\n</body></html>\n')


def write_cards(out: Path, spots: list[dict], alerts: dict | None, generated_at: str, root: str,
                areas: tuple[Area, ...] = AREAS) -> dict:
    """Every card, its caption and the page, into out. The cards and captions of an earlier run there
    go first (its PNG and text files and index.html, nothing else), so a past weekend's card does not
    linger. A card that fails is left out and named in the summary's warnings; nothing here raises
    for one card."""
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("*.png"), *out.glob("*.txt"), out / "index.html"]:
        old.unlink(missing_ok=True)
    made, notes, warnings = [], [], []
    weekend = []
    levels = spot_levels(alerts) if alerts else None
    days = weekend_days(alerts.get("dates", [])) if alerts else None
    if levels is None:
        notes.append("No weekend cards in this update: the levels file (data/alerts.json) was not written.")
    elif days is None:
        notes.append("No weekend cards today: the five-day forecast does not reach Sunday until Wednesday.")
    else:
        for area in areas:
            try:
                card = weekend_card(area, levels, days, {s["id"]: official_brief(s) for s in spots})
                if card is None:
                    warnings.append(f"card {area.slug}: none of its spots is in the forecast")
                    continue
                if card.missing:
                    warnings.append(f"card {area.slug}: not in the forecast, left out: {', '.join(card.missing)}")
                stem = f"{area.slug}-{days[0]}"
                files = save_both(out, stem, lambda size, c=card: draw_weekend(c, generated_at, size))
                caption = weekend_caption(card, generated_at, root)
                (out / f"{stem}.txt").write_text(caption)
                made.append({"title": f"{area.title}, {two_days(days)}", "files": files, "caption": caption,
                             "caption_file": f"{stem}.txt"})
                weekend.append(area.slug)
            except Exception as e:  # noqa: BLE001 - one card must not stop the others, or the site
                warnings.append(f"card {area.slug} not made: {e}")
    storm = storm_rows(spots, generated_at)
    if not storm:
        notes.append("No storm card: no monitored overflow upstream of any spot was discharging when this "
                     "update was made.")
    else:
        try:
            t = datetime.fromisoformat(generated_at).astimezone(LONDON)
            stem = f"storm-{t:%Y-%m-%d-%H%M}"
            files = save_both(out, stem, lambda size: draw_storm(storm, generated_at, size))
            caption = storm_caption(storm, generated_at, root)
            (out / f"{stem}.txt").write_text(caption)
            made.append({"title": "Overflows discharging now", "files": files, "caption": caption,
                         "caption_file": f"{stem}.txt"})
        except Exception as e:  # noqa: BLE001
            warnings.append(f"storm card not made: {e}")
    (out / "index.html").write_text(page(root, generated_at, made, notes))
    for w_ in warnings:
        log.warning("%s", w_)
    return {"weekend": weekend, "storm_spots": len(storm), "cards": len(made), "warnings": warnings}
