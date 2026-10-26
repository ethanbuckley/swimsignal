"""The data-quality page, quality.html: the overflow records SwimSignal has had to
pick between or guess at, listed for the water companies and the Environment Agency to correct.

Four lists. The position conflicts checked on 13 October 2026 (docs/OVERFLOW-POSITIONS-2026-10.md),
from its cases file, each with both positions: the live feed's (the state's live_latest.parquet) and
the latest annual return's outlet (data/processed/annual_returns.parquet). Then, from this build's
overflow table, the overflows with no name or no receiving water in either record, and the records
that have stopped updating in a feed that has not (ingest.live.frozen_records, `record_stale`). Last,
the monitors reporting one spill far longer than any the overflow has on record (monitor_anomalies.long_runs,
against data/processed/longest_events.parquet), with those that have no spill on record in a group of their own
(long_run_section): a display only, which changes no status, count, risk or level, and which says it could not be
checked, never "None", when its inputs are missing or older than the build allows. Each overflow links to the feedback form with its id filled in. scripts/build_site.py
(write_quality_page) writes the page; src/dipcast/site/quality.html is its template.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from dipcast import config
from dipcast import monitor_anomalies as ma
from dipcast.ingest.live import FEED_CURRENT_H, with_data_states
from dipcast.overflow_names import water_name

CASES = config.ROOT / "docs" / "OVERFLOW-POSITIONS-2026-10-cases.csv"
CASES_DOC = "https://github.com/ethanbuckley/swimsignal/blob/main/docs/OVERFLOW-POSITIONS-2026-10.md"
LONG_RUN_DOC = "https://github.com/ethanbuckley/swimsignal/blob/main/docs/MONITOR-ANOMALIES-2026-10.md"
LONG_RUN_COLS = {"site_id", "company", "status", "status_start", "latest_event_start", "fetched_at"}
LONG_RUN_ASK = "Is this monitor still reporting correctly?"   # the link on each row: a question, never a verdict
RETURNS = config.PROCESSED / "annual_returns.parquet"
TEMPLATE = Path(__file__).resolve().parent / "site" / "quality.html"
SLOT = re.compile(r"\{\{(\w+)\}\}")
CREDITS = ("Live positions, names and record times: the water companies via the National Storm Overflow Hub, "
           "CC BY 4.0. Outlets, names and receiving waters: the Environment Agency's storm overflow annual returns, "
           "© Environment Agency copyright and/or database right 2025, Open Government Licence v3.0. Longest spills: the "
           "Environment Agency's storm overflow start and stop records for 2024 and 2025, © Environment Agency copyright "
           "and/or database right, Open Government Licence v3.0.")
# The cases file's reasons in plain words. The evidence is the receiving water's name, the WFD water
# body's name and the place in the site name, each looked for within 3 km of each position.
REASONS = {
    "under 1 km apart": "the two are under 1 km apart, too close for the names nearby to tell them apart",
    "no evidence": "no water, water body or place name near either position points to one of them",
    "evidence points to the outlet only": "the names near the outlet match the overflow's records; those near the live position do not",
    "evidence points to the live position only": "the names near the live position match the overflow's records; those near the outlet do not",
    "evidence conflicts": "names near both positions match the overflow's records",
    "every receiving-water name says ground; off the network either way": "every record says it discharges to ground",
}
# East Worthing CSO: the names pointed to the outlet; the EA's features did not (KEEP_LIVE in overflows.py).
KEPT_LIVE = ("Settled: the live position. The names point to the outlet, but the Environment Agency's bathing-water "
             "features put a storm overflow at the live position.")
DIFFERENT = re.compile(r"different waters: live '(.*)', return '(.*)'")
WHERE = {"live": "the live position", "annual return": "the outlet", "join": "a point set by hand on the river"}


def load_cases(path: Path = CASES) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def latest_outlets(returns: pd.DataFrame) -> pd.DataFrame:
    """Per overflow id, the latest annual return's outlet and its receiving water."""
    a = returns.dropna(subset=["site_id", "lat", "lon"]).sort_values("year").groupby("site_id").last()
    return a[["lat", "lon"]]


def reason_words(outcome: str, reason: str) -> str:
    """The rule applied to one case, as a sentence: what was decided, and why."""
    if outcome == "kept live: K3 contradicts":
        return KEPT_LIVE
    m = DIFFERENT.fullmatch(reason)
    why = (f"the two records name different waters: “{m[1]}” in the feed, “{m[2]}” in the return"
           if m else REASONS.get(reason, reason))
    head = {"settled: outlet": "Settled: the outlet", "settled: live": "Settled: the live position",
            "settled: ground": "Settled: off the river network"}.get(outcome, "Open")
    return f"{head}. {why[0].upper()}{why[1:]}."


def tell_us(site_id: str, name: str = "", text: str = "Tell us") -> str:
    q = urlencode({"type": "problem", "spot": f"Overflow {site_id}" + (f" ({name})" if name else "")})
    return f'<a href="feedback.html?{escape(q)}">{escape(text)}</a>'


def place(lat, lon) -> str:
    """A position as text that links to it on OpenStreetMap's map."""
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return '<span class="muted">not in the latest records</span>'
    la, lo = f"{float(lat):.5f}", f"{float(lon):.5f}"
    return f'<a href="https://www.openstreetmap.org/?mlat={la}&amp;mlon={lo}#map=16/{la}/{lo}">{la}, {lo.replace("-", "−")}</a>'


def _water(raw) -> str:
    w = water_name(raw)
    return escape(w) if w else '<span class="muted">not named</span>'


def _gap(m: str) -> str:
    v = float(m)
    return f"{v / 1000:.1f}&nbsp;km" if v >= 1000 else f"{v:.0f}&nbsp;m"


def _fold(summary: str, inner: str) -> str:
    return f'<details class="fold"><summary>{summary}</summary>{inner}</details>'


def positions_section(cases: pd.DataFrame, live: pd.DataFrame, outlets: pd.DataFrame, used: pd.Series | None) -> str:
    """The 166 position conflicts, one fold per company, each overflow with both positions and the rule.
    Names are given as the records give them, capitals and all: this page is about the records."""
    n_open = int((cases["outcome"] == "open").sum())
    n_kept = int(cases["outcome"].str.startswith("kept").sum())
    h = ('<section id="positions" aria-labelledby="positions-h"><h2 id="positions-h">Two positions for one overflow</h2>'
         f'<p>On 13 October 2026, {len(cases)} overflows had a position in their company\'s live feed and an outlet in the '
         "Environment Agency's latest annual return more than 300 m apart, and neither position had a river of the "
         "receiving water's name within 750 m. A rule written down before it was applied settled "
         f"{len(cases) - n_open - n_kept} of them"
         + (f", kept {n_kept} at the live position because a check contradicted the move," if n_kept else "")
         + f" and left {n_open} open. "
         f'<a href="{CASES_DOC}">The rule, and every case with its evidence</a>. Each position links to a map.</p>')
    for company, g in cases.sort_values(["company", "site_name", "site_id"]).groupby("company", sort=True):
        rows = []
        for r in g.itertuples():
            name = escape(r.site_name) if r.site_name else escape(r.site_id)
            lv = live.loc[r.site_id] if r.site_id in live.index else None
            ar = outlets.loc[r.site_id] if r.site_id in outlets.index else None
            now = used.get(r.site_id) if used is not None else None
            rule = reason_words(r.outcome, r.reason)
            if now in WHERE:
                rule += f' <span class="muted">Today\'s forecast uses {WHERE[now]}.</span>'
            rows.append(
                f'<tr><th class="ov" scope="row">{name}<span class="id">{escape(r.site_id)} · {tell_us(r.site_id, r.site_name)}</span></th>'
                f'<td data-l="Live feed">{place(*(lv[["lat", "lon"]] if lv is not None else (None, None)))}'
                f'<span class="w">{_water(r.rw_live)}</span></td>'
                f'<td data-l="Annual return">{place(*(ar[["lat", "lon"]] if ar is not None else (None, None)))}'
                f'<span class="w">{_water(r.rw_ar)}</span></td>'
                f'<td class="num" data-l="Apart">{_gap(r.gap_m)}</td>'
                f'<td data-l="Rule" class="rule">{rule}</td></tr>')
        table = ('<div class="tw"><table class="qt"><thead><tr><th>Overflow</th><th>Live feed, and its water</th>'
                 '<th>Annual return outlet, and its water</th><th class="num">Apart</th><th>Rule applied</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>')
        o = int((g["outcome"] == "open").sum())
        h += _fold(f"{escape(company)}: {len(g)} overflow{'s' if len(g) != 1 else ''}, {o} open", table)
    return h + "</section>"


def unnamed(ov: pd.DataFrame) -> pd.DataFrame:
    """The overflows with no name, or no receiving water, in either record."""
    no_name = ov["site_name"].isna() | ov["site_name"].astype(str).str.strip().eq("")
    no_water = ov["receiving_watercourse"].map(water_name).isna()
    return ov.assign(no_name=no_name, no_water=no_water)[no_name | no_water]


def names_section(ov: pd.DataFrame | None) -> str:
    h = '<section id="names" aria-labelledby="names-h"><h2 id="names-h">Overflows without a name or a receiving water</h2>'
    if ov is None:
        return h + "<p>This build had no overflow table, so this list is empty.</p></section>"
    u = unnamed(ov)
    nn, nw = int(u["no_name"].sum()), int(u["no_water"].sum())
    h += (f"<p>{nn:,} overflow{' has' if nn == 1 else 's have'} no name: the live feeds give none, and no annual return "
          f"lists one. {nw:,} {'has' if nw == 1 else 'have'} no receiving water in either record, or only a placeholder "
          "such as #N/A. The site then shows the overflow by its id, or says its water is not named in its feed.</p>")
    for company, g in u.sort_values(["company", "site_id"]).groupby("company", sort=True):
        rows = "".join(
            f'<tr><th class="ov" scope="row">{escape(r.site_id)}<span class="id">{tell_us(r.site_id)}</span></th>'
            f'<td data-l="Name">{escape(r.site_name) if not r.no_name else "<span class=muted>none</span>"}</td>'
            f'<td data-l="Receiving water">{_water(r.receiving_watercourse)}</td></tr>' for r in g.itertuples())
        table = ('<div class="tw"><table class="qt"><thead><tr><th>Overflow</th><th>Name</th><th>Receiving water</th></tr></thead>'
                 f"<tbody>{rows}</tbody></table></div>")
        h += _fold(f"{escape(company)}: {len(g)}", table)
    return h + "</section>"


def frozen_section(ov: pd.DataFrame | None) -> str:
    h = '<section id="frozen" aria-labelledby="frozen-h"><h2 id="frozen-h">Records without a current time</h2>'
    if ov is None:
        return h + "<p>This build had no overflow table, so this list is empty.</p></section>"
    f = ov[ov.get("record_stale", pd.Series(False, index=ov.index)).fillna(False).astype(bool)]
    h += (f"<p>Most companies stamp every record in their feed each time it updates. In those feeds, these records carry no "
          f"time, or one more than {FEED_CURRENT_H:g} hours older than the poll, while the rest of the feed is current. Their "
          "last reading may not be current, so the site does not count them as reporting live.</p>")
    if f.empty:
        return h + "<p>None in this build.</p></section>"
    f = f.assign(when_=pd.to_datetime(f.get("feed_updated_at"), utc=True).dt.tz_convert("Europe/London"))
    for company, g in f.sort_values(["company", "site_id"]).groupby("company", sort=True):
        rows = "".join(
            f'<tr><th class="ov" scope="row">{escape(_name(r.site_name, r.site_id))}'
            f'<span class="id">{escape(r.site_id)} · {tell_us(r.site_id, _name(r.site_name, ""))}</span></th>'
            f'<td data-l="Record last updated">{r.when_.strftime("%-d %b %Y, %H:%M") if pd.notna(r.when_) else "no time in its record"}</td></tr>'
            for r in g.itertuples())
        h += _fold(f"{escape(company)}: {len(g)}", '<div class="tw"><table class="qt"><thead><tr><th>Overflow</th>'
                   f'<th>Record last updated</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return h + "</section>"


def _name(site_name, fallback: str) -> str:
    return site_name.strip() if isinstance(site_name, str) and site_name.strip() else fallback


def _span(h: float) -> str:
    """A length of time in words: minutes under an hour, hours under two days, days after."""
    if h < 1:
        return f"{h * 60:.0f}&nbsp;minutes"
    if h < 48:
        return f"{h:.1f}&nbsp;hours"
    d = h / 24
    return f"{d:.0f}&nbsp;days" if d >= 10 else f"{d:.1f}&nbsp;days"


def _long_run_rows(flags: pd.DataFrame, info: pd.DataFrame, with_ref: bool) -> str:
    """The table of one group of long_run flags: by company, then the longest run first."""
    rows = []
    for f in flags.itertuples():
        e = json.loads(f.evidence)
        r = info.loc[f.site_id] if f.site_id in info.index else None
        name = _name(r.get("site_name") if r is not None else None, "")
        water = r.get("receiving_watercourse") if r is not None else None
        since = pd.Timestamp(e["status_start"]).tz_convert("Europe/London")
        ref = e.get("longest_on_record_h")
        cells = (f'<tr><th class="ov" scope="row">{escape(name or str(f.site_id))}'
                 f'<span class="id">{escape(str(f.site_id))} · {tell_us(f.site_id, name, LONG_RUN_ASK)}</span></th>'
                 f'<td data-l="Company">{escape(str(f.company)) if f.company else "<span class=muted>not known</span>"}</td>'
                 f'<td data-l="Receiving water">{_water(water)}</td>'
                 f'<td data-l="Reported discharging">{_span(float(e["run_h"]))}<span class="w">since {since.strftime("%-d %b %Y, %H:%M")}</span></td>')
        if with_ref:
            cells += f'<td data-l="Longest on record">{_span(float(ref))}</td>'
        rows.append((str(f.company or ""), -float(e["run_h"]), cells + "</tr>"))
    rows.sort(key=lambda x: (x[0], x[1]))
    head = ("<th>Overflow</th><th>Company</th><th>Receiving water</th><th>Reported discharging</th>"
            + ("<th>Longest on record</th>" if with_ref else ""))
    return (f'<div class="tw"><table class="qt"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(r[2] for r in rows)}</tbody></table></div>')


def _not_checked(h: str, why: str) -> str:
    return h + f"<p>{why} This is not a finding that every monitor is reporting as usual.</p></section>"


def long_run_section(ov: pd.DataFrame | None, longest: pd.Series | None, as_of: pd.Timestamp | None = None) -> str:
    """The monitors reporting one spill far longer than any on record (monitor_anomalies.long_runs on this build's
    overflow table, against `longest`, each overflow's longest spill in the EA's records). Display only: it reads
    the table and changes nothing.

    Two groups, kept apart (PR #382 review, 26 Oct 2026). The list proper compares: only an overflow with a
    longest spill on record is in it, and only when its spill is over the seven-day floor and over twice that
    longest. An overflow with no spill on record has the floor alone, so it goes in a second group under its own
    heading, which says there is nothing to compare with and claims nothing more.

    A list that could not be checked says so, never "None in this build": without the table, its live columns or
    the record of longest spills; when the live readings are more than FEED_CURRENT_H older than the build
    (`as_of`, the build's time; None skips this test); and a monitor whose own reading is not current
    (data_state not "live", ingest.live.data_states) is left out of both groups and counted instead."""
    h = ('<section id="long-runs" aria-labelledby="long-runs-h">'
         '<h2 id="long-runs-h">Monitors reporting a spill far longer than any on record</h2>')
    if ov is None:
        return _not_checked(h, "This build had no overflow table, so this list could not be checked.")
    if longest is None:
        return _not_checked(h, "The comparison with past spills could not be made in this build, because the record "
                               "of past spill lengths was not available.")
    if not LONG_RUN_COLS <= set(ov.columns):
        return _not_checked(h, "This build's overflow table had no live statuses, so this list could not be checked.")
    ov = with_data_states(ov)
    polled = ov[pd.to_numeric(ov["status"], errors="coerce").isin([0, 1, -1])]
    poll = pd.to_datetime(polled["fetched_at"], utc=True).max() if len(polled) else pd.NaT
    if as_of is not None and len(polled) and (pd.isna(poll) or (pd.Timestamp(as_of).tz_convert("UTC") - poll)
                                              > pd.Timedelta(hours=FEED_CURRENT_H)):
        return _not_checked(h, f"The live readings in this build are more than {FEED_CURRENT_H:g} hours older than "
                               "the build, so this list could not be checked.")
    flags = ma.long_runs(ov, longest)
    times = "twice" if ma.LONG_RUN_FACTOR == 2 else f"{ma.LONG_RUN_FACTOR:g} times"
    days = f"{ma.LONG_RUN_MIN_H / 24:g}"
    h += (f"<p>Each of these monitors has reported one spill for more than {days} days, and for more than {times} as "
          "long as the overflow's longest spill in the Environment Agency's records for 2024 and 2025. A spill that "
          "long can be real, in a wet spell or after a change at the overflow. The question for each is whether its "
          "monitor is still reporting correctly, and the company that runs it can answer that. The forecast counts each "
          "spill as its company reports it: this list changes nothing on the site. "
          f'<a href="{LONG_RUN_DOC}">How the list is made</a>.</p>')
    current = flags["site_id"].map(ov.drop_duplicates("site_id", keep="last").set_index("site_id")["data_state"]).eq("live")
    not_current = int((~current).sum())
    flags = flags[current.to_numpy()]
    known = flags["evidence"].map(lambda e: json.loads(e).get("longest_on_record_h") is not None).astype(bool)
    compared, unmatched = flags[known.to_numpy()], flags[~known.to_numpy()]
    info = ov.drop_duplicates("site_id", keep="last").set_index("site_id")
    if len(compared):
        h += _long_run_rows(compared, info, with_ref=True)
    else:
        h += "<p>None in this build.</p>" if not not_current else "<p>None among the monitors with a current reading.</p>"
    if not_current:
        h += (f"<p>{not_current} more monitor{' has' if not_current == 1 else 's have'} reported a spill this long, but "
              f"{'its reading was' if not_current == 1 else 'their readings were'} not current in this build, so "
              f"{'it was' if not_current == 1 else 'they were'} not checked.</p>")
    if len(unmatched):
        h += ('<h3 id="long-runs-no-record">Monitors reporting one spill for more than '
              f"{days} days, with no Environment Agency record to compare against</h3>"
              "<p>The Environment Agency's records for 2024 and 2025 have no spill at these overflows, so there is "
              "nothing to compare these spills with. That is often because the monitor, or its id, is new. A spill of "
              f"more than {days} days is listed here only so that someone can ask whether the monitor is still reporting "
              "correctly; nothing here says the spill is unusual for the overflow.</p>"
              + _long_run_rows(unmatched, info, with_ref=False))
    return h + "</section>"


def body(cases: pd.DataFrame, live: pd.DataFrame, outlets: pd.DataFrame, ov: pd.DataFrame | None, generated: str,
         longest: pd.Series | None = None, as_of: pd.Timestamp | None = None) -> str:
    used = ov.set_index("site_id")["position_source"] if ov is not None and "position_source" in ov else None
    return ('<h1>Overflow records to check</h1>'
            "<p class=\"lead\">Where the water companies' live feeds and the Environment Agency's annual returns disagree "
            "about a storm overflow, or leave something out, SwimSignal has to pick one or do without. These are those "
            "overflows, so the company or the Agency can put the record right.</p>"
            "<p>Each overflow has a link to the feedback form, with its id filled in. A correction from the company "
            "that runs it, from the Agency, or from someone who knows where it discharges, settles a case.</p>"
            + positions_section(cases, live, outlets, used) + names_section(ov) + frozen_section(ov)
            + long_run_section(ov, longest, as_of)
            + f'<p class="small muted note">The first list is as checked on 13 October 2026; the others are from the '
              f"build of {escape(generated)}. {escape(CREDITS)}</p>")


def site_page(cases: pd.DataFrame, live: pd.DataFrame, outlets: pd.DataFrame, ov: pd.DataFrame | None,
              generated: str, mark: str, template: str | None = None, longest: pd.Series | None = None,
              as_of: pd.Timestamp | None = None) -> str:
    slots = {"mark": mark, "body": body(cases, live, outlets, ov, generated, longest, as_of)}
    html = template if template is not None else TEMPLATE.read_text()
    missing = set(SLOT.findall(html)) - slots.keys()
    if missing:
        raise ValueError(f"quality.html has slots this build does not fill: {sorted(missing)}")
    return SLOT.sub(lambda m: slots[m.group(1)], html)
