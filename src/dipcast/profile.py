"""The storm overflows upstream of a place and how often each spilled in 2021-2025, from the
Environment Agency's annual returns (event duration monitoring, OGL v3; data/processed/annual_returns.parquet).

Shared by scripts/site_profile.py, which traces any point for a bathing-water applicant
(docs/MARKETS-2026-10.md), and the site's profile pages, spot/<id>/profile/, which the build
writes from each spot's data/upstream/<id>.json (scripts/build_site.py, write_profiles). Both take the
overflows as rows with site_id, site_name, company, weight (reach), travel_h, has_live and a distance:
distance_km and lake_distance_km as the site's files have them, or the trace's distance_m and
lake_distance_m.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

import pandas as pd

from dipcast import config
from dipcast.overflow_names import overflow_names

YEARS = [2021, 2022, 2023, 2024, 2025]
NEAR_KM = 10
RETURNS = config.PROCESSED / "annual_returns.parquet"
RETURN_FIELDS = ["site_id", "year", "spills", "spill_hours", "edm_operational_pct"]
CAVEAT = ("This profile lists the monitored storm overflows upstream of the point and how often each "
          "spilled in each year. It is not a water test, and it does not say whether the water is fit to "
          "swim in. It does not include farm runoff, misconnected drains, treated sewage effluent, "
          "wildlife or overflows without a monitor. A year's count depends on how long the monitor "
          "worked (shown as monitor uptime).")
CREDITS = ("Storm overflow annual returns: © Environment Agency copyright and/or database right 2025, "
           "Open Government Licence v3.0. Overflow positions: the water companies via the National Storm "
           "Overflow Hub, CC BY 4.0. River network: contains OS data © Crown copyright and database right "
           "2026 (OS Open Rivers). Traced and weighted by SwimSignal (swimsignal.co.uk), whose method is at "
           "swimsignal.co.uk/methods.html.")
# The weight in words, as the app says it (levels.js, WEIGHT_SAID): until 30 Oct 2026 this note called it reach,
# "the share of a spill's bacteria SwimSignal's model expects to arrive here". The name REACH_NOTE is kept.
REACH_NOTE = ("Weight is SwimSignal's modelled relative contribution weight for each overflow here, from its assumptions on "
              "travel time and die-off on the way and dilution by the river: neither a measured bacterial concentration nor a "
              "calibrated chance of contamination. Weighting by it counts an hour of spilling just upstream for "
              "far more than one 40 km away. Spills are counted by the Environment Agency's 12/24 method: any "
              "discharge in the first 12 hours counts as one spill, then one more for each 24 hours with any discharge.")


def name_case(s: str) -> str:
    """Overflow names that arrive in capitals ("GRASSINGTON/STW") in normal case, as the site shows them."""
    return re.sub(r"[A-Za-z']+", lambda m: m[0][0] + m[0][1:].lower() if re.fullmatch(r"[A-Z']{4,}", m[0]) else m[0],
                  str(s or ""))


def fmt(v, digits: int = 0) -> str:
    if v is None or pd.isna(v):
        return "–"
    return f"{v:,.{digits}f}"


def km_upstream(t: pd.DataFrame) -> pd.Series:
    """Distance along the water, river and lake together, in km, as the site's pages give it."""
    if "distance_km" in t:
        return t["distance_km"].fillna(0) + t.get("lake_distance_km", pd.Series(0.0, index=t.index)).fillna(0)
    return (t["distance_m"].fillna(0) + t.get("lake_distance_m", pd.Series(0.0, index=t.index)).fillna(0)) / 1000


def load_returns(path: Path = RETURNS) -> pd.DataFrame:
    return pd.read_parquet(path, columns=RETURN_FIELDS)


def yearly(returns: pd.DataFrame, ids=None) -> pd.DataFrame:
    """One row an overflow id, with spills_<year>, spill_hours_<year> and edm_operational_pct_<year>."""
    ar = returns if ids is None else returns[returns["site_id"].isin(set(ids))]
    if ar.empty:
        return pd.DataFrame(index=pd.Index([], name="site_id"))
    wide = ar.pivot_table(index="site_id", columns="year", values=["spills", "spill_hours", "edm_operational_pct"],
                          aggfunc="max")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    return wide


def with_returns(up: pd.DataFrame, returns: pd.DataFrame | None = None, wide: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each overflow's spills, spill hours and monitor uptime for each year, by its id, and its km upstream.
    Pass `wide` (yearly()) to join many places to one pivot."""
    wide = yearly(returns, up["site_id"]) if wide is None else wide
    t = up.merge(wide, left_on="site_id", right_index=True, how="left")
    t["km"] = km_upstream(t)
    return t.sort_values("weight", ascending=False, kind="stable").reset_index(drop=True)


def summary(t: pd.DataFrame) -> list[dict]:
    """Per year: overflows with a return, spills and hours in all, and hours weighted by reach."""
    rows = []
    for y in YEARS:
        s, h = t.get(f"spills_{y}"), t.get(f"spill_hours_{y}")
        if s is None:
            rows.append({"year": y, "with_return": 0, "spills": 0, "hours": 0.0, "reach_hours": 0.0})
            continue
        rows.append({"year": y, "with_return": int(s.notna().sum()), "spills": int(s.fillna(0).sum()),
                     "hours": float(h.fillna(0).sum()), "reach_hours": float((h.fillna(0) * t["weight"]).sum())})
    return rows


def in_lake(t: pd.DataFrame) -> pd.Series:
    """Overflows in the spot's own lake: some lake on the way and no river. They are across the
    lake, not upstream: Glebe Road PS in Bowness read "2.6 km upstream" of Millerground, though Windermere
    drains south. The site's pages say it the same way (levels.js, overflowWhere)."""
    if "distance_km" in t:
        river, lake = t["distance_km"].fillna(0), t.get("lake_distance_km", pd.Series(0.0, index=t.index)).fillna(0)
    else:
        river, lake = t["distance_m"].fillna(0) / 1000, t.get("lake_distance_m", pd.Series(0.0, index=t.index)).fillna(0) / 1000
    return (lake > 0) & (river < 0.05)


def in_short(t: pd.DataFrame) -> dict:
    """How many overflows upstream, how many within NEAR_KM, how many live, the nearest's km, and whether it
    is in the same lake."""
    km = t["km"] if "km" in t else km_upstream(t)
    return {"n": len(t), "near": int((km <= NEAR_KM).sum()), "live": int(t["has_live"].fillna(False).astype(bool).sum()),
            "nearest_km": float(km.min()) if len(t) else None,
            "nearest_in_lake": bool(in_lake(t).loc[km.idxmin()]) if len(t) else False}


def company_name(name) -> str:
    """A company's name as the pages write it: the EA's returns spell Dŵr Cymru without its circumflex
    (levels.js, companyName)."""
    return re.sub(r"\bDwr Cymru\b", "Dŵr Cymru", str(name or ""))


def hours_away(h) -> str:
    return "under 1" if h is not None and not pd.isna(h) and h < 1 else fmt(h, 0)


def reach(w) -> str:
    return "–" if w is None or pd.isna(w) else "<1%" if 0 < w < 0.005 else f"{100 * w:.0f}%"


def uptime(v) -> str:
    return "–" if v is None or pd.isna(v) else f"{v:.0f}%"


# ------------------------------------------------------------------ the site's page, spot/<id>/profile/
TEMPLATE = Path(__file__).parent / "site" / "profile.html"
OVERFLOW_PAGE = re.compile(r"[A-Z]{3}\d{5}")   # an id with a page of its own, overflow/<id>/ (overflow_record.py)
SLOT = re.compile(r"\{\{(\w+)\}\}")
SITE_CAVEAT = ("This page lists the monitored storm overflows upstream of this spot and how often each spilled in "
               "each year. It is not a water test, and it does not say whether the water is fit to swim in. It does "
               "not include farm runoff, misconnected drains, treated sewage effluent, wildlife or overflows without a "
               "monitor. A year's count depends on how long the monitor worked, shown as monitor uptime.")
OTHER_RISKS = "Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water."   # levels.js OTHER_RISKS


def _table(head: list[tuple[str, bool]], rows: list[list[str]], label: str) -> str:
    """A table as the Accuracy page draws them, numbers right, in a box that scrolls sideways if it must. The
    overflows' table (class ovt, as on the organisers' page) has each overflow's name as its row's header,
    and each cell carries its column's name (data-l) for the phone layout in profile.html: a block an overflow."""
    ovt = label in ("overflows", "spill lengths")   # the spill lengths (durations_section) take the same phone layout
    num = ' class="num"'

    def cell(i: int, c: str) -> str:
        if i == 0 and ovt:
            return f'<th scope="row" class="ov">{c}</th>'
        lab = f' data-l="{head[i][0]}"' if ovt else ""
        return f"<td{num if head[i][1] else ''}{lab}>{c}</td>"
    th = "".join(f'<th scope="col"{num if n else ""}>{h}</th>' for h, n in head)
    body = "".join("<tr>" + "".join(cell(i, c) for i, c in enumerate(r)) + "</tr>" for r in rows)
    cls = ' class="ovt"' if ovt else ""
    return (f'<div class="tw" tabindex="0" role="region" aria-label="{escape(label.capitalize())}, scrolls sideways">'
            f"<table{cls}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>")


def _named(site_name, site_id) -> str:
    """The plain name, then the company's own and the id, as the site's other pages give them."""
    plain, own = overflow_names(None if site_name is None or pd.isna(site_name) else site_name, site_id)
    name = (f'<a href="overflow/{escape(str(site_id))}/">{escape(plain)}</a>' if OVERFLOW_PAGE.fullmatch(str(site_id))
            else escape(plain))   # its public record (overflow_record.py), which the build writes for every overflow listed here
    return f'{name}<br><span class="muted">{escape(own) + " · " if own else ""}{escape(str(site_id))}</span>'


# ------------------------------------------------------------------ spill lengths, 2024-25 (history)
# From the research export (docs/SPILL-DURATIONS-CONTRACT-v1.md), split per spot by build_site.write_spill_durations.
# What it may say is the contract's: how long each overflow's spills lasted in 2024 and 2025. Never when a running
# spill will end (it is not a forecast), how much was discharged, that a short spill was harmless, or that companies
# record events alike. The export's own sentence (claim.public_wording) stands beside the figures, and every figure
# names its years. An overflow with no row is not said to have had no spills: the annual returns above give its count.
# durations.js (durationsHours) says a length the same way; the tests hold both to the same cases.
def hours_said(h) -> str:
    """A spill's length in words: minutes under an hour, hours to two days, days beyond, the number and its unit joined
    by a no-break space so a narrow cell does not split them."""
    if h is None or pd.isna(h):
        return "–"
    if h < 1:
        m = round(h * 60)
        return "under\u00a01\u00a0min" if m < 1 else f"{m}\u00a0min"
    if h < 10:
        return f"{h:.1f}".removesuffix(".0") + "\u00a0h"
    if h < 48:
        return f"{round(h)}\u00a0h"
    d = h / 24
    return (f"{d:.1f}".removesuffix(".0") if d < 10 else f"{round(d)}") + "\u00a0days"


def zero_said(rows: list[dict], method: dict) -> str:
    """When a typical length shows as under a minute (the export's 0.0 hours), what that means, from the export's
    method.zero_length_note and events_same_start_stop (1.1); durations.js (durationsZero) says the same. Else ''."""
    if not method.get("zero_length_note") or not any(
            isinstance(r.get("median_h"), (int, float)) and r["median_h"] * 60 < 0.5 for r in rows):
        return ""
    n = method.get("events_same_start_stop")
    events = f" ({n:,} such events in these records, mostly at Wessex Water and South West Water)" if isinstance(n, int) else ""
    return (" A typical spill shown as under 1\u00a0min means most of that overflow's spills lasted under a minute as recorded, "
            f"or were recorded with the same start and stop time{events}. It does not mean nothing was discharged.")


def durations_section(d: dict) -> str:
    """The spot's overflows' spill lengths in 2024 and 2025: a heading and the years first, the export's own sentence,
    then the figures in a fold, after the annual returns. d: build_site.spill_durations_for."""
    rows, absent = d.get("overflows") or [], d.get("absent") or []
    period = d.get("period") or {}
    y0, y1 = str(period.get("from") or "2024")[:4], str(period.get("to") or "2025")[:4]
    wording = (d.get("claim") or {}).get("public_wording") or ""
    # The export's sentence goes beside figures; with none to show, the years alone.
    out = [f'<h2 id="spill-lengths">How long their spills lasted, {y0} and {y1}</h2>',
           f"<p><b>History: {y0} and {y1}.</b>{' ' + escape(wording) if rows else ''}</p>"]
    if rows:
        n = len(rows)
        table = _table([("Overflow and id", False), (f"Typical spill, {y0}-{y1[2:]}", True), ("Long end", True),
                        ("Longest", True), (f"Spills {y0}", True), (f"Spills {y1}", True)],   # counted as the note below says, not as the annual returns count
                       [[f'{escape(r.get("name") or str(r["site_id"]))}<br><span class="muted">'
                         f'{escape(r["own"]) + " · " if r.get("own") else ""}{escape(str(r["site_id"]))}</span>',
                         hours_said(r.get("median_h")) + (", few spills" if r.get("few") else ""), hours_said(r.get("p90_h")),
                         hours_said(r.get("longest_h")), f"{r.get('spills_2024') or 0:,}", f"{r.get('spills_2025') or 0:,}"] for r in rows],
                       "spill lengths")
        out.append(f'<details class="fold"><summary>Spill lengths at {n} of the {n + len(absent)} overflows, {y0}-{y1[2:]}</summary>{table}'
                   f"<p class=\"small muted\">Typical: half of the overflow's spills in {y0} and {y1} were shorter, half longer. Long end: "
                   "one spill in ten lasted longer. Longest: its longest in the two years. A spill here is the monitor's events joined "
                   "when they overlap or start less than an hour apart, so these counts differ from the annual returns' counts above. "
                   "Few spills: fewer than 5 in the two years, so its typical length rests on little. Companies do not record spills "
                   "the same way, so compare overflows of different companies with care."
                   + zero_said(rows, d.get("method") or {}) + "</p></details>")
    if absent:
        welsh = any("cymru" in str(a.get("company") or "").lower() for a in absent)
        k = len(absent)
        lead = (f"{k} of the overflows upstream {'has' if k == 1 else 'have'} no spill" if rows
                else f"None of the {k} overflows upstream has a spill")   # as durations.js says it
        out.append(f"<p>{lead} in these {y0}-{y1[2:]} records: none was "
                   "recorded, or there is no record" + (" (Dŵr Cymru Welsh Water's overflows are not in them)" if welsh else "")
                   + ". That is not the same as no spills: the annual returns above give each year's count.</p>")
    credit = " ".join(escape(a) for a in d.get("attribution") or [])
    out.append(f'<p class="small muted">{credit + ". " if credit else ""}How to read these, and how long spills already '
               'running went on, company by company: <a href="durations.html">Spill durations</a>.</p>')
    return "\n".join(out)


def body(spot: dict, t: pd.DataFrame | None, durations: dict | None = None) -> str:
    """The page's main content. t is with_returns() of the spot's overflows, or None when the build has no
    list for it (no file in data/upstream/). durations: build_site.spill_durations_for, or None for no spill
    lengths section."""
    sid, name = escape(str(spot["id"])), escape(str(spot["name"]))
    total = (spot.get("upstream_summary") or {}).get("overflows") or 0
    km = (spot.get("assumptions") or {}).get("max_upstream_km") or config.MAX_UPSTREAM_KM
    links = (f'<p class="dateline"><a href="spot/{sid}/">The spot\'s forecast</a> · '
             f'<a href="organisers.html#spot={sid}">For event organisers</a></p>')
    out = [f"<h1>Overflow history upstream of {name}</h1>", links, f"<p>{escape(SITE_CAVEAT)}</p>"]
    err = str(spot.get("error") or "")
    if err.startswith("An isolated lake"):
        out.append("<p>The river network links no monitored storm overflow to this lake. "
                   f"There is no overflow history to show. {OTHER_RISKS}</p>")
    elif t is None or not len(t):
        out.append("<p>This spot has no forecast in this update, so its overflows are not listed here. Try again later.</p>" if err
                   else "<p>The list of overflows upstream is not in this update. Try again later.</p>" if total
                   else f"<p>No monitored storm overflow was found within {km:g} km upstream of this spot, so there is no "
                        f"overflow history to show. {OTHER_RISKS}</p>")
    else:
        s, years = in_short(t), summary(t)
        out.append('<aside class="summary" aria-labelledby="short-h"><h2 id="short-h">In short</h2><ul>'
                   f"<li><b>{s['n']}</b> monitored storm overflow{'' if s['n'] == 1 else 's'} drain{'s' if s['n'] == 1 else ''} into "
                   f"the water within {km:g}&nbsp;km upstream; <b>{s['near']}</b> of them within {NEAR_KM}&nbsp;km.</li>"
                   # "Report live" here read as a count of what reports now, which the spot's page gives
                   # and which can be lower: Ilkley's history said 15 where its page said 14 (12 Oct 2026).
                   f"<li>{s['live']} of them are in the water companies' live feeds. "
                   f"<a href=\"spot/{sid}/\">The spot's page</a> says how many report right now.</li>"
                   f"<li>The nearest is {fmt(s['nearest_km'], 1)}&nbsp;km "
                   f"{'away, across the lake' if s['nearest_in_lake'] else 'upstream'}.</li></ul></aside>")
        out.append("<h2>Each year, all overflows upstream</h2>")
        out.append(_table([("Year", False), ("Overflows with a return", True), ("Spills", True), ("Spill hours", True),
                           ("Spill hours, weighted by model weight", True)],
                          [[str(r["year"]), str(r["with_return"]), f"{r['spills']:,}", fmt(r["hours"]), fmt(r["reach_hours"])]
                           for r in years], "yearly totals"))
        out.append(f'<p class="small muted">{escape(REACH_NOTE)} <a href="methods.html#weight">How the weight is worked out</a>.</p>')
        out.append(f"<h2>The overflows, by model weight</h2><p>All {s['n']}, the one whose spills matter most here first. "
                   "km away is along the river network, through any lake on the way, or across the lake for one that drains "
                   "into the same lake. Hours away is how long sewage takes to arrive, at the model's river speed, and "
                   "across a lake at its slower lake speed.</p>")
        lake = in_lake(t)
        rows = [[_named(r.get("site_name"), r["site_id"]),
                 escape(company_name(r.get("company"))), fmt(r["km"], 1) + (" across the lake" if on_lake else ""),
                 hours_away(r.get("travel_h")), escape(reach(r.get("weight"))),
                 fmt(r.get("spills_2023")), fmt(r.get("spills_2024")), fmt(r.get("spills_2025")),
                 fmt(r.get("spill_hours_2025")), uptime(r.get("edm_operational_pct_2025"))] for (_, r), on_lake in zip(t.iterrows(), lake.to_numpy())]
        out.append(_table([("Overflow and id", False), ("Company", False), ("km away", True), ("Hours away", True),
                           ("Weight", True), ("Spills 2023", True), ("Spills 2024", True), ("Spills 2025", True),
                           ("Spill hours 2025", True), ("Monitor uptime 2025", True)], rows, "overflows"))
        out.append('<p class="small muted">A dash: no annual return for that overflow in that year.</p>')
        if durations:
            out.append(durations_section(durations))
    out.append(f'<h2>Sources and credits</h2><p>{escape(CREDITS)} <a href="terms.html#data">All credits and licences</a>.</p>')
    return "\n".join(out)


def share_tags(title: str, description: str, url: str, root: str) -> str:
    """A link preview for the page, the tags build_site.page_meta gives every other page: its own title
    and description, its address, and the site's shared picture (icons/og.png). Not the spot's own card
    (cards/spot/<id>.png), which shows today's level: a preview is kept for days, and this page is about
    past years. Values escaped here."""
    return "\n".join([
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="SwimSignal">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(url)}">',
        f'<meta property="og:image" content="{escape(root + "icons/og.png")}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="SwimSignal: pollution risk forecasts for river and lake swim spots">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def site_page(spot: dict, t: pd.DataFrame | None, mark: str, template: str | None = None, url: str | None = None,
              root: str | None = None, durations: dict | None = None) -> str:
    """spot/<id>/profile/index.html for one spot. `mark` is the brand mark's inline SVG (build_site.MARK);
    `url` the page's own published address, for its canonical link, and with `root` (the site's published
    address) its link preview (none without them)."""
    name = escape(str(spot["name"]))
    description = (f"The monitored storm overflows upstream of {spot['name']} and how often each "
                   "spilled in each year from 2021 to 2025, from the Environment Agency's annual returns.")
    slots = {"name": name, "mark": mark, "body": body(spot, t, durations),
             "canonical": f'<link rel="canonical" href="{escape(url)}">' if url else "",
             "share": share_tags(f"Overflow history: {spot['name']} · SwimSignal", description, url, root) if url and root else "",
             "description": escape(description)}
    html = template if template is not None else TEMPLATE.read_text()
    missing = set(SLOT.findall(html)) - slots.keys()
    if missing:
        raise ValueError(f"profile.html has slots this build does not fill: {sorted(missing)}")
    return SLOT.sub(lambda m: slots[m.group(1)], html)
