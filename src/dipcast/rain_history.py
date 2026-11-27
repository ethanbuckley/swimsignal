"""What a beach's own past samples read after rain and after dry spells, in England, Wales, Northern Ireland and the
Republic of Ireland (data/research/coastal_rain_history.v1.json, written off CI by
scripts/coastal_c1/export_rain_history.py), and the rain at an English beach's square today. Past samples, never a
forecast. Two lines on each beach's card on the coverage page, and one note above the list that says
what was tested (C1's frozen-model backtest, docs/COASTAL-C1-PROTOCOL-2026-11.md).
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "research" / "coastal_rain_history.v1.json"
SCHEMA, MAJOR = "swimsignal.coastal-rain-history", "1"
RULE = {"hours": 48, "after_rain_mm": 10, "dry_mm": 1}


NATION_WORDS = {"england": "English", "wales": "Welsh", "northern_ireland": "Northern Irish", "ireland": "Irish"}


def attach(snapshot: dict | None, nation: str = "england", path: Path | None = None) -> int:
    """Each coastal site's `rain_history`, and the snapshot's `rain_history` (the rule, credit, and the nation's
    period, pooled figures and what was tested). A missing file, one of another schema or major version, or a nation
    the file does not hold adds nothing."""
    try:
        doc = json.loads(Path(path or PATH).read_text())
    except (OSError, ValueError):
        return 0
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != MAJOR or not snapshot:
        return 0
    info = (doc.get("nations") or {}).get(nation)
    if not info:
        return 0
    n = 0
    for site in snapshot.get("sites") or []:
        h = (doc.get("sites") or {}).get(site.get("id"))
        if h and h.get("nation", nation) == nation:
            site["rain_history"] = h
            n += 1
    snapshot["rain_history"] = {"nation": nation, "rule": doc.get("rule"), "credit": doc.get("credit"), **info}
    return n


def _cell(lat: float, lon: float) -> str:
    return f"{round(round(lat / 0.1) * 0.1, 1) + 0.0:.1f},{round(round(lon / 0.1) * 0.1, 1) + 0.0:.1f}"


def attach_live(snapshot: dict | None, overflow_days: dict | None, points: dict | None = None) -> int:
    """Each site's `rain_now`: the rain in the 48 hours to midday today at its 0.1 degree square, from the
    click-anywhere file this build already wrote (overflow_days.json, `rain_48h`, index 0 is today). `points` maps a
    site id to [lat, lon] (data/raw/bathing_water_points.json). A square that file does not hold gets nothing. No request."""
    if not snapshot or not overflow_days:
        return 0
    squares = overflow_days.get("rain_48h") or {}
    days = overflow_days.get("days") or []
    today = overflow_days.get("today", 0)
    day = days[today] if isinstance(today, int) and 0 <= today < len(days) else None
    n = 0
    for site in snapshot.get("sites") or []:
        p = (points or {}).get(site.get("id"))
        lat, lon = (p[0], p[1]) if isinstance(p, list | tuple) and len(p) >= 2 else (site.get("lat"), site.get("lon"))
        if lat is None or lon is None or not day:
            continue
        v = (squares.get(_cell(float(lat), float(lon))) or [None])[0]
        if isinstance(v, int | float):
            site["rain_now"] = {"mm": float(v), "date": day}
            n += 1
    return n


def _reading(v) -> str:
    if isinstance(v, str):
        return f'{"under" if v[:1] == "<" else "over"} {float(v[1:]):,.0f}'
    return f"{v:,.0f}" if v >= 10 else f"{v:g}"


def _part(g: dict | None, words: str) -> str | None:
    if not g or "median" not in g:
        return None
    over = f'{g["over_500"]} over 500' if g["over_500"] else "none over 500"
    return f'{words}, the middle of {g["samples"]} read {_reading(g["median"])} ({over})'


def line(h: dict, rule: dict | None = None) -> str | None:
    """One plain line: the beach's samples after rain in the 2 days before, and after 2 dry days. None when neither
    group has enough samples."""
    rule = {**RULE, **(rule or {})}
    wet = _part(h.get("after_rain"), f'after {rule["after_rain_mm"]:g} mm or more of rain in the 2 days before')
    dry = _part(h.get("dry"), f'after 2 dry days (under {rule["dry_mm"]:g} mm)')
    if not wet and not dry:
        return None
    years = str(h["first_year"]) if h["first_year"] == h["last_year"] else f'{h["first_year"]}–{h["last_year"]}'
    parts = "; ".join(p for p in (wet, dry) if p)
    return f"Past samples here by rain, {years}: {parts}. E. coli per 100 ml. Not a forecast"


def now_line(site: dict, rule: dict | None = None) -> str | None:
    """Today's rain at the beach's square and which of the two groups it falls in, or neither."""
    r = site.get("rain_now")
    if not r:
        return None
    rule = {**RULE, **(rule or {})}
    mm = r["mm"]
    group = (" That is as wet as the after-rain samples above." if mm >= rule["after_rain_mm"]
             else " That is as dry as the dry-day samples above." if mm < rule["dry_mm"] else "")
    return f'Rain here in the 2 days to midday on {r["date"]}: {mm:g} mm (forecast service, this build).{group}'


def card_lines(site: dict, snapshot: dict) -> list[str]:
    """The escaped lines a card adds: the past samples by rain, then today's rain when the first is there."""
    rule = (snapshot.get("rain_history") or {}).get("rule")
    by_rain = line(site["rain_history"], rule) if site.get("rain_history") else None
    if not by_rain:
        return []
    now = now_line(site, rule)
    return [escape(by_rain)] + ([escape(now)] if now else [])


def note(snapshot: dict) -> str:
    """Once, above the list: what the rain lines are and what was tested."""
    r = snapshot.get("rain_history")
    if not r:
        return ""
    wet, dry = r.get("after_rain") or {}, r.get("dry") or {}
    rule = {**RULE, **(r.get("rule") or {})}
    pooled = ""
    if wet.get("share_over_500") is not None and dry.get("share_over_500") is not None:
        pooled = (f' Across {NATION_WORDS.get(r.get("nation"), "these")} beaches ({r.get("period", "")}), '
                  f'{wet["share_over_500"] * 100:.1f}% of samples taken after {rule["after_rain_mm"]:g} mm or more of '
                  f'rain in 2 days were over 500, against {dry["share_over_500"] * 100:.1f}% after 2 dry days.')
    tested = r.get("tested") or ""
    return ('<p class="small">The "by rain" lines split each beach\'s own samples by the rain in the 2 days before '
            'each one, from ERA5-Land, a reanalysis of past weather, at the beach\'s grid square.'
            f'{escape(pooled)} {escape(tested)} '
            'These are past samples. They are not a forecast for today, and rain is not the only cause of a bad '
            'result.</p>')


def credit(snapshot: dict) -> str:
    r = snapshot.get("rain_history")
    return f'<p class="small">{escape(r["credit"])}</p>' if r and r.get("credit") else ""
