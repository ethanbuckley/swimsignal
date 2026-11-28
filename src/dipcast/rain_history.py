"""What a beach's own past samples read after rain and after dry spells, in England, Wales, Northern Ireland and the
Republic of Ireland, coast and inland (data/research/coastal_rain_history.v1.json, written off CI by
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


def attach_cached(snapshot: dict | None, points: dict | None, cache_dir: Path, now, max_age_h: float = 30.0,
                  min_coverage: float = 0.9) -> int:
    """Each site's `rain_now` from the forecast cells the build already caches near the directories for their water
    temperature (build_site.directory_air; docs/DIRECTORY-RAIN-NOW-2026-11.md): the rain in the 48 hours to midday
    today at the nearest cell, its own 0.1 degree square or one of the eight around it, whose file is at most
    `max_age_h` old and covers `min_coverage` of the window. Only sites with past samples by rain (`rain_history`).
    `points` maps a site id to [lat, lon] where the site has no position of its own. No request."""
    import math

    import numpy as np
    import pandas as pd
    if not snapshot:
        return 0
    now = pd.Timestamp(now).tz_convert("Europe/London")
    noon = now.normalize() + pd.Timedelta(hours=12)
    start, day = noon - pd.Timedelta(hours=48), now.date().isoformat()
    cells: dict = {}

    def cell(a: float, b: float):
        if (a, b) not in cells:
            f = Path(cache_dir) / f"forecast_{a:.3f}_{b:.3f}.parquet"
            cells[(a, b)] = None
            try:
                if f.exists():   # fresh by the file's own fetch time: a restored cache keeps old data under a new mtime
                    d = pd.read_parquet(f, columns=["time", "precip_mm", "issued_at"])
                    issued = pd.Timestamp(d["issued_at"].max())
                    t = pd.to_datetime(d["time"], utc=True).dt.tz_convert("Europe/London")
                    w = d[(t > start) & (t <= noon)]
                    if ((now - issued.tz_convert("Europe/London")) <= pd.Timedelta(hours=max_age_h) and len(w)
                            and w["precip_mm"].notna().sum() >= min_coverage * 48):
                        cells[(a, b)] = (round(float(np.nansum(w["precip_mm"])), 1), pd.Timestamp(d["issued_at"].max()))
            except Exception:  # noqa: BLE001 - a torn or older cache file counts as none
                cells[(a, b)] = None
        return cells[(a, b)]
    n = 0
    for site in snapshot.get("sites") or []:
        if not site.get("rain_history"):
            continue
        p = (points or {}).get(site.get("id"))
        lat, lon = (site.get("lat"), site.get("lon")) if site.get("lat") is not None else (p or (None, None))[:2]
        if lat is None or lon is None:
            continue
        a0, b0 = round(round(float(lat) / 0.1) * 0.1, 1), round(round(float(lon) / 0.1) * 0.1, 1)
        best = None
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                a, b = round(a0 + i / 10, 1) + 0.0, round(b0 + j / 10, 1) + 0.0
                got = cell(a, b)
                if got is None:
                    continue
                km = math.hypot((a - float(lat)) * 111.2, (b - float(lon)) * 111.2 * math.cos(math.radians(float(lat))))
                if best is None or (i, j) == (0, 0) or (best[2] != (0, 0) and km < best[0]):
                    best = (km, got, (i, j))   # the site's own square first, as on English cards; else the nearest
        if best:
            km, (mm, issued), at = best
            site["rain_now"] = {"mm": mm, "date": day, **({} if at == (0, 0) else {"km": max(1, round(km))}),
                                "fetched": issued.tz_convert("Europe/London").strftime("%-d %b %H:%M")}
            n += 1
    return n


def _reading(v) -> str:
    if isinstance(v, str):
        return f'{"under" if v[:1] == "<" else "over"} {float(v[1:]):,.0f}'
    return f"{v:,.0f}" if v >= 10 else f"{v:g}"


def _part(g: dict | None, words: str, line: int = 500) -> str | None:
    if not g or "median" not in g:
        return None
    n = g.get(f"over_{line}")
    over = f"{n} over {line}" if n else f"none over {line}"
    return f'{words}, the middle of {g["samples"]} read {_reading(g["median"])} ({over})'


def line(h: dict, rule: dict | None = None) -> str | None:
    """One plain line: the water's samples after rain in the 2 days before, and after 2 dry days, with how many were
    over its line (500 on the coast, 900 inland: `line` in the file). None when neither group has enough samples."""
    rule = {**RULE, **(rule or {})}
    ln = h.get("line", 500)
    wet = _part(h.get("after_rain"), f'after {rule["after_rain_mm"]:g} mm or more of rain in the 2 days before', ln)
    dry = _part(h.get("dry"), f'after 2 dry days (under {rule["dry_mm"]:g} mm)', ln)
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
    where = f'at a point {r["km"]} km away' if r.get("km") else "here"
    source = f'forecast service, fetched {r["fetched"]}' if r.get("fetched") else "forecast service, this build"
    return f'Rain {where} in the 2 days to midday on {r["date"]}: {mm:g} mm ({source}).{group}'


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
    if r.get("inland"):
        tested += (" At lakes and rivers the lines count results over 900, the inland line, and they were not "
                   "tested: the test was on the coast.")
    place = "water" if r.get("inland") else "beach"
    return (f'<p class="small">The "by rain" lines split each {place}\'s own samples by the rain in the 2 days before '
            f'each one, from ERA5-Land, a reanalysis of past weather, at the {place}\'s grid square.'
            f'{escape(pooled)} {escape(tested)} '
            'These are past samples. They are not a forecast for today, and rain is not the only cause of a bad '
            'result.</p>')


def credit(snapshot: dict) -> str:
    r = snapshot.get("rain_history")
    return f'<p class="small">{escape(r["credit"])}</p>' if r and r.get("credit") else ""
