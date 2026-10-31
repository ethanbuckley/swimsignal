"""One storm overflow's public record, overflow/<id>/: what open public sources say about it, for a swimmer to read,
keep and send on. The build writes one for every monitored overflow upstream of a spot with a page
(scripts/build_site.py, write_overflow_pages), from each spot's data/upstream/<id>.json joined to:

- the Environment Agency's EDM annual returns (data/processed/annual_returns.parquet): spills, hours, monitor uptime,
  the name in the company's return, its type and receiving water. OGL v3.
- the same layer's permit reference and improvement and investigation activity (data/processed/overflow_record.parquet,
  scripts/make_overflow_record.py). OGL v3.
- the PR24 WINEP's storm overflow improvement deadlines (data/processed/winep_overflow_actions.parquet). OGL.
- the spill durations export (data/research/spill_durations.v1.json), from the EA's start/stop records. OGL v3.
- the live feeds via the National Storm Overflow Hub, as the spot's upstream file carries them. CC BY 4.0.
- the upgrade notes (a company's own words, quoted with a link) and the dry-weather counts (SwimSignal's count, with
  its method linked), which the build reads and passes in, as the spot's page shows them.

What it may say: each source's figures as published, credited, and what SwimSignal worked out labelled as its own.
What it must not: that a spill, a dry-weather spill or a count is a breach, illegal or a permit failure (nothing here
can tell), that the water is safe or unsafe, or anything from a source with no licence to publish it (the EA's
consents register, the companies' own event files and plan layers, Water UK's plan): those say "not published here"
and why. A prose page with no script, like the spot's overflow history (profile.py). The "Send this record" link opens
the reader's own email app with a draft; SwimSignal sends nothing.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from dipcast import config
from dipcast.overflow_names import overflow_names
from dipcast.profile import OVERFLOW_PAGE as OVERFLOW_ID   # the annual returns' current ids: the page's folder name
from dipcast.profile import _table, company_name, fmt, hours_said, share_tags, zero_said

YEARS = [2021, 2022, 2023, 2024, 2025]
RECORD = config.PROCESSED / "overflow_record.parquet"
WINEP = config.PROCESSED / "winep_overflow_actions.parquet"
TEMPLATE = Path(__file__).parent / "site" / "overflow.html"
SLOT = re.compile(r"\{\{(\w+)\}\}")
NO_ACTION = re.compile(r"^No (improvement action|investigation activity) in reporting period$")

# Each company's own contact page, opened on 31 Oct 2026 (the address after any redirect). The draft has no "To":
# the reader takes the address from here, so the page never guesses an email address. Keys: the annual returns' names.
CONTACT = {
    "Anglian Water": "https://www.anglianwater.co.uk/contact-and-support",
    "Dwr Cymru Welsh Water": "https://contact.dwrcymru.com/en/",
    "Northumbrian Water": "https://www.nwl.co.uk/contact/",
    "Severn Trent Water": "https://www.stwater.co.uk/help-and-contact/contact-us/",
    "South West Water": "https://www.southwestwater.co.uk/contact-us",
    "Southern Water": "https://www.southernwater.co.uk/contact-us/",
    "Thames Water": "https://www.thameswater.co.uk/contact-us",
    "United Utilities": "https://www.unitedutilities.com/help-and-support/contact-us/",
    "Wessex Water": "https://www.wessexwater.co.uk/contact-us",
    "Yorkshire Water": "https://www.yorkshirewater.com/get-in-touch/",
}
FIND_MP = "https://members.parliament.uk/FindYourMP"   # UK Parliament's own finder, opened 31 Oct 2026
EA_RETURNS = "https://www.arcgis.com/home/item.html?id=66fef44a4aab438991d7ce08fbc1de64"   # the layer config.EDM_ANNUAL_RETURNS reads
EA_EVENTS = "https://environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7"
WINEP_PAGE = "https://www.data.gov.uk/dataset/cf9b80c2-cae9-4ed1-88ce-890940be379a/pr24-water-industry-national-environment-programme"
HUB = "https://www.streamwaterdata.co.uk/pages/storm-overflows-data"
# Companies whose own event files go back further than the EA's, with no licence on them
# (docs/OVERFLOW-DATA-SOURCES-2026-10.md, 2.3), and whose plan layers have none (2.6).
UNLICENSED_EVENTS = {"Southern Water": "2017", "Yorkshire Water": "2021"}
UNLICENSED_PLANS = {"Southern Water": "its Clean Rivers and Seas Plan layer", "Wessex Water": "its overflow plan layers"}

CAVEAT = ("This page collects what public records say about one storm overflow: its permit, how often it spilled, and "
          "the improvements recorded for it. It is not a water test and does not say whether the water is fit to swim in. "
          "A spill count is not a finding that the overflow broke its permit: overflows may spill in heavy rain under their "
          "permits, and nothing here can tell whether a spill was allowed.")
CREDITS = ("Storm overflow annual returns, including permit references and improvement and investigation activity: "
           "© Environment Agency copyright and/or database right, Open Government Licence v3.0; the figures are the water "
           "companies' own returns. PR24 Water Industry National Environment Programme: © Environment Agency copyright "
           "and/or database right 2025. All rights reserved. Published under the Open Government Licence. Spill lengths: "
           "Environment Agency storm overflow EDM start/stop data 2024 and 2025, Open Government Licence v3.0. Live status: "
           "the water companies via the National Storm Overflow Hub, CC BY 4.0. Spots, distances and model weights: "
           "SwimSignal, traced on OS Open Rivers (contains OS data © Crown copyright and database right 2026).")
METHOD_12_24 = ("Spills are counted by the Environment Agency's 12/24 method: any discharge in the first 12 hours counts as one "
                "spill, then one more for each 24 hours with any discharge.")


# ------------------------------------------------------------------ the data a page needs
def gather(upstream: dict[str, list[dict]], spots: dict[str, str]) -> dict[str, dict]:
    """{overflow id: {"row": its row from the first spot's upstream file, "spots": [{id, name, km, weight, travel_h,
    in_lake}, ...] nearest first}} for every overflow whose id can be a folder name. upstream: {spot id: rows};
    spots: {spot id: name}, the spots with a page."""
    out: dict[str, dict] = {}
    for sid, rows in upstream.items():
        if sid not in spots:
            continue
        for r in rows or []:
            oid = str(r.get("site_id") or "")
            if not OVERFLOW_ID.fullmatch(oid):
                continue
            river, lake = float(r.get("distance_km") or 0), float(r.get("lake_distance_km") or 0)
            o = out.setdefault(oid, {"row": r, "spots": []})
            o["spots"].append({"id": sid, "name": spots[sid], "km": river + lake, "in_lake": lake > 0 and river < 0.05,
                               "weight": r.get("weight"), "travel_h": r.get("travel_h")})
    for o in out.values():
        o["spots"].sort(key=lambda s: (s["km"], s["name"]))
    return out


def load_returns(path: Path, ids) -> dict[str, pd.DataFrame]:
    """Each overflow's annual-return rows, by year, with the fields the page shows."""
    cols = ["site_id", "year", "company", "site_name", "asset_type", "spills", "spill_hours", "edm_operational_pct",
            "receiving_water", "wfd_waterbody_name", "bathing_water"]
    ar = pd.read_parquet(path, columns=cols)
    ar = ar[ar["site_id"].isin(set(ids))].sort_values(["site_id", "year"])
    return {k: g.drop_duplicates("year", keep="last").set_index("year") for k, g in ar.groupby("site_id")}


def load_record(path: Path = RECORD) -> dict[str, pd.DataFrame]:
    r = pd.read_parquet(path)
    return {k: g.set_index("year") for k, g in r.groupby("site_id")}


def _key(p) -> str:
    return re.sub(r"\s+", "", str(p or "")).upper()


def is_permit(p) -> bool:
    """A permit reference, not a placeholder such as "Unpermitted" or "Permit applied for": it has a digit."""
    return bool(p) and not pd.isna(p) and bool(re.search(r"\d", str(p)))


WINEP_ID = re.compile(r"^(\S.*?)\s+/?\s*([A-Za-z]?\d+)$")   # "2482 1", "27/19/0045 /1", "EPR/SB3499RQ A1"


def winep_actions(winep: pd.DataFrame, record: dict[str, pd.DataFrame]) -> dict[str, list[dict]]:
    """The WINEP's actions on each overflow's permit (latest return), {overflow id: [action, ...]}. The WINEP names a
    permit, sometimes with the activity number on it ("2482 1"): with a number, an action goes to the overflow with that
    activity alone; without, to every overflow on the permit, and each says how many share it (`shared`)."""
    by_permit: dict[str, list[tuple[str, str]]] = {}
    for oid, g in record.items():
        last = g.iloc[-1]
        if is_permit(last.get("permit")):
            by_permit.setdefault(_key(last["permit"]), []).append((oid, re.sub(r"\D", "", str(last.get("activity_ref") or ""))))
    out: dict[str, list[dict]] = {}
    for w in winep.to_dict("records"):
        m = WINEP_ID.match(str(w["permit"]).strip())
        if m and _key(m[1]) in by_permit:   # a permit and the activity number on it
            hit = [oid for oid, a in by_permit[_key(m[1])] if a == re.sub(r"\D", "", m[2])]
        else:                               # the permit alone ("301740", "AECNF11009")
            hit = [oid for oid, _ in by_permit.get(_key(w["permit"]), [])]
        for oid in hit:
            out.setdefault(oid, []).append({**w, "shared": len(hit)})
    for v in out.values():
        v.sort(key=lambda a: (a["completion_date"], a["action_id"] or ""))
    return out


def spill_lengths(path: Path) -> dict:
    """The spill durations export by overflow id: {"rows": {id: row}, "claim", "attribution", "period", "method"}, or {}."""
    import json
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    if doc.get("schema") != "swimsignal.spill-durations" or str(doc.get("version", "")).split(".")[0] != "1":
        return {}
    cols, companies = doc.get("overflows") or {}, doc.get("companies") or []
    keys = ("spills_2024", "spills_2025", "median_h", "p90_h", "longest_h", "few")
    rows = {}
    for i, oid in enumerate(cols.get("site_id") or []):
        c = (cols.get("company") or [None])[i] if i < len(cols.get("company") or []) else None
        rows[oid] = {k: (cols.get(k) or [None] * (i + 1))[i] for k in keys} | {
            "company": companies[c] if isinstance(c, int) and 0 <= c < len(companies) else None}
    return {"rows": rows, "claim": doc.get("claim") or {}, "attribution": doc.get("attribution") or [],
            "period": doc.get("period") or {}, "method": doc.get("method") or {}}


# ------------------------------------------------------------------ the words
def pct(v) -> str:
    return "–" if v is None or pd.isna(v) else figure(v) + "%"


def figure(v, digits: int = 2) -> str:
    """A return's figure as published: whole numbers whole, others to at most `digits` places, no trailing zeros."""
    if v is None or pd.isna(v):
        return "–"
    s = f"{float(v):,.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def day_said(iso) -> str:
    try:
        return pd.Timestamp(iso).tz_convert("Europe/London").strftime("%-d %B %Y") if pd.Timestamp(iso).tzinfo else pd.Timestamp(iso).strftime("%-d %B %Y")
    except (TypeError, ValueError):
        return str(iso)


def live_said(row: dict, as_of: str) -> str:
    """The live feed's status when the page was written, and the end of its last spill, in a sentence or two."""
    st, state = row.get("status"), row.get("data_state")
    if not row.get("has_live") or state == "no_feed":
        return "This overflow is not in its company's live feed, so there is no recent spill information for it here."
    if state == "live" and st in (0, 1):
        now = f"When this page was updated ({as_of}), its company's live feed showed it {'discharging' if st == 1 else 'not discharging'}."
    elif state == "offline":
        now = f"When this page was updated ({as_of}), its company's live feed listed its monitor as offline."
    else:   # stale: the feed's last reading for it was not current (ingest.live.data_states)
        now = f"When this page was updated ({as_of}), the live feed's last reading for it was not current."
    end = row.get("latest_event_end")
    return now + (f" The last spill the feed reported ended on {day_said(end)}." if end else "")


def mail_parts(name: str, oid: str, company: str, permit: str | None, spots: list[dict], returns: pd.DataFrame | None,
               record: pd.DataFrame | None, actions: list[dict], url: str) -> tuple[str, str]:
    """The draft's subject and body: who it is to, which overflow, the latest two years' counts as published, the
    improvement the returns record and the WINEP deadline, one question, and the page's address. Neutral: no claim
    beyond the figures, no demand. The reader adds the address and their name."""
    lines = [f"Dear {company_name(company)},", "",
             f"I am writing about your storm overflow {name} (Environment Agency id {oid}"
             + (f", permit {permit}" if permit else "") + "). It is upstream of "
             + "; ".join(s["name"] for s in spots[:3]) + (f"; and {len(spots) - 3} other places" if len(spots) > 3 else "")
             + ", where people swim.", ""]
    if returns is not None:
        said = [f"{y}: {figure(returns.loc[y, 'spills'])} spills, {figure(returns.loc[y, 'spill_hours'])} hours"
                for y in (2024, 2025) if y in returns.index and not pd.isna(returns.loc[y, "spills"])]
        if said:
            lines += ["Your annual returns to the Environment Agency record " + "; ".join(said) + ".", ""]
    if record is not None and len(record):
        imp = record.iloc[-1].get("improvement")
        if isinstance(imp, str) and imp:
            lines += [f"Your {int(record.index[-1])} return lists its improvement activity as: \"{imp}\".", ""]
    if actions:
        a = actions[0]
        lines += [f"The Environment Agency's PR24 WINEP sets {day_said(a['completion_date'])} as the date for the action "
                  f"\"{a['action_name']}\" ({a['action_id']}).", ""]
    lines += ["Could you tell me what is planned for this overflow, and when the work is expected to be finished?", "",
              f"The public record I am referring to is here: {url}", "", "Thank you."]
    return f"Storm overflow {name} ({oid})", "\n".join(lines)


def mailto(subject: str, body: str) -> str:
    return f"mailto:?subject={quote(subject)}&body={quote(body)}"


def _row(label: str, value: str) -> tuple[str, str]:
    return label, value


def facts_table(rows: list[tuple[str, str]]) -> str:
    """Label and value a row, values already escaped: overflow.html stacks them on a phone."""
    return ('<div class="tw"><table class="facts"><tbody>'
            + "".join(f'<tr><th scope="row">{k}</th><td>{v}</td></tr>' for k, v in rows) + "</tbody></table></div>")


def body(oid: str, o: dict, returns: pd.DataFrame | None, record: pd.DataFrame | None, actions: list[dict] | None,
         upgrade: dict | None, dry: dict | None, lengths: dict, url: str, as_of: str) -> str:
    """The page's main content. o: gather()'s entry; returns and record: the overflow's rows by year, or None;
    actions: its WINEP actions, or None when the build has no WINEP file; upgrade: its upgrade note's row; dry: its dry-weather row if the note's rule
    holds; lengths: spill_lengths()."""
    from dipcast.dry_weather import noted
    row, spots = o["row"], o["spots"]
    company = (str(returns["company"].dropna().iloc[-1]) if returns is not None and returns["company"].notna().any()
               else str(row.get("company") or ""))
    own_name = (str(returns["site_name"].dropna().iloc[-1]) if returns is not None and returns["site_name"].notna().any()
                else row.get("site_name"))
    plain, own = overflow_names(own_name, oid)
    if plain == oid:   # no name in the returns or the feed: say whose it is, as levels.js's overflowSaid does
        plain = f"{company_name(company)} overflow {oid}"
    last = record.iloc[-1] if record is not None and len(record) else None
    permit = last.get("permit") if last is not None else None
    permit_ok = is_permit(permit)
    out = [f"<h1>{escape(plain)}</h1>",
           f'<p class="dateline">{escape(company_name(company))} · {escape(own) + " · " if own else ""}{escape(oid)}</p>',
           f"<p>{escape(CAVEAT)}</p>"]

    # The record: who, what and where, as the returns give them.
    latest = returns.iloc[-1] if returns is not None and len(returns) else None
    facts = [_row("Company", escape(company_name(company))),
             _row("Environment Agency id", escape(oid)),
             _row("Name in the company's return" if returns is not None else "Name in the company's live feed", escape(own_name or "–"))]
    if last is not None:
        yr = int(record.index[-1])
        if permit_ok:
            act = last.get("activity_ref")
            facts.append(_row("Permit reference", escape(str(permit)) + (f", activity {escape(str(act))}" if isinstance(act, str) and act else "")
                              + f' <span class="muted">({yr} return)</span>'))
        elif isinstance(permit, str) and permit:
            facts.append(_row("Permit reference", f'None given. The {yr} return\'s permit field reads "{escape(permit)}".'))
    else:
        facts.append(_row("Permit reference", "Not in the 2024 or 2025 returns this build holds."))
    if latest is not None:
        if isinstance(latest.get("asset_type"), str):
            facts.append(_row("Type", escape(latest["asset_type"])))
        water = [x for x in (row.get("receiving_watercourse"), latest.get("wfd_waterbody_name")) if isinstance(x, str) and x]
        if water:
            facts.append(_row("Discharges to", escape(water[0]) + (f' <span class="muted">(water body: {escape(water[1])})</span>'
                                                                   if len(water) > 1 and water[1] != water[0] else "")))
        if isinstance(latest.get("bathing_water"), str) and latest["bathing_water"].strip().lower() not in ("", "no", "n/a", "none", "not applicable"):
            facts.append(_row("Bathing water named in the return", escape(latest["bathing_water"])))
    out.append('<h2 id="record">The record</h2>')
    out.append(facts_table(facts))
    out.append('<p class="small muted">The permit reference is as the Environment Agency\'s annual returns give it. The EA\'s '
               "consents register holds the permit itself, but its licence allows internal use only, so its conditions are "
               "not published here.</p>")

    # Downstream: the spots, each linked both ways.
    n = len(spots)
    out.append(f'<h2 id="spots">Swim spots downstream</h2><p>SwimSignal counts this overflow at {n} swim spot{"" if n == 1 else "s"}. '
               "km is along the river network, through any lake on the way. The model weight is SwimSignal's estimate of how much "
               'this overflow\'s spills count at that spot, not a measurement (<a href="methods.html#weight">how it is worked out</a>).</p>')
    out.append('<ul class="spots">' + "".join(
        f'<li><a href="spot/{escape(s["id"])}/">{escape(s["name"])}</a> · {fmt(s["km"], 1)}&nbsp;km '
        f'{"away, across the lake" if s["in_lake"] else "upstream"} · model weight {escape(_weight(s["weight"]))} · '
        f'<a href="spot/{escape(s["id"])}/profile/">every overflow there</a></li>' for s in spots) + "</ul>")

    # Each year, as the returns give it.
    out.append('<h2 id="years">Spills each year</h2>')
    if returns is None or not len(returns):
        out.append("<p>No annual return in this build is filed under this id, so there are no yearly figures to show. "
                   "The overflow may be in the returns under another id.</p>")
    else:
        rows = [[str(y), figure(returns.loc[y, "spills"], 0) if y in returns.index else "–",
                 figure(returns.loc[y, "spill_hours"]) if y in returns.index else "–",
                 pct(returns.loc[y, "edm_operational_pct"]) if y in returns.index else "–"] for y in YEARS]
        out.append(_table([("Year", False), ("Spills", True), ("Spill hours", True), ("Monitor uptime", True)], rows, "spills each year"))
        out.append(f'<p class="small muted">From the water company\'s annual return to the Environment Agency, as published: the '
                   "spill count as the company returned it, and the hours as the Environment Agency works them out from the return's "
                   f"total duration, to two decimal places. {METHOD_12_24} A dash: no return for that year. Monitor uptime is the share "
                   "of the year the monitor worked; a year with low uptime may undercount.</p>")

    # Recent spills.
    out.append('<h2 id="recent">Recent spills</h2>')
    out.append(f"<p>{escape(live_said(row, as_of))}</p>")
    if lengths.get("rows", {}).get(oid):
        d = lengths["rows"][oid]
        p = lengths.get("period") or {}
        y0, y1 = str(p.get("from") or "2024")[:4], str(p.get("to") or "2025")[:4]
        out.append(f"<p><b>How long its spills lasted, {y0} and {y1}.</b> {escape((lengths.get('claim') or {}).get('public_wording') or '')}</p>")
        out.append(facts_table([("Typical spill", hours_said(d.get("median_h")) + (", few spills" if d.get("few") else "")),
                                ("Long end", hours_said(d.get("p90_h"))), ("Longest", hours_said(d.get("longest_h"))),
                                (f"Spills {y0}", f"{d.get('spills_2024') or 0:,}"), (f"Spills {y1}", f"{d.get('spills_2025') or 0:,}")]))
        out.append('<p class="small muted">Typical: half its spills were shorter, half longer. Long end: one in ten lasted longer. '
                   "A spill here is the monitor's events joined when they overlap or start less than an hour apart, so these counts "
                   "differ from the annual returns' above." + escape(zero_said([d], lengths.get("method") or {}))
                   + ' <a href="durations.html">More on spill lengths</a>.</p>')
    held = UNLICENSED_EVENTS.get(company)
    # The lengths above come from those files, so "not part of this site's build" contradicted them (31 Oct 2026): what is
    # left out is the list of each spill's times, not the files.
    out.append("<p><b>Each spill's start and stop times: not listed here.</b> The Environment Agency publishes them for 2024 on, under "
               f'the Open Government Licence (<a href="{EA_EVENTS}">its start/stop files</a>)' + ('; this page gives only the summary above.' if lengths.get("rows", {}).get(oid) else '.')
               + (f" {escape(company)} publishes its own files from {held}; they carry no licence, so SwimSignal does not use them." if held else "")
               + "</p>")

    # Improvements.
    out.append('<h2 id="improvements">Improvements recorded</h2>')
    if record is not None and len(record):
        rows = [[str(int(y)), escape(_flag(r.get("improvement"))), escape(_flag(r.get("investigation")))] for y, r in record.iterrows()]
        out.append(_table([("Return year", False), ("Improvement activity", False), ("Investigation activity", False)], rows, "improvements"))
        out.append('<p class="small muted">Word for word from the annual returns. The 2023 return left these columns empty. A year\'s '
                   "entry covers that year only; work under way may not show until a later return.</p>")
    else:
        out.append("<p>No improvement or investigation entry for this overflow is in this build's 2024 and 2025 returns.</p>")
    if actions:
        items = "".join(
            f"<li>{escape(a['action_name'] or '')} ({escape(a['action_id'] or '')}, {escape(a['driver'] or '')}): "
            f"due {escape(day_said(a['completion_date']))}."
            + (f" The programme names the permit, which {a['shared']} overflows share, so this action may concern another of them."
               if a["shared"] > 1 else "") + "</li>" for a in actions)
        out.append(f"<p>The Environment Agency's PR24 Water Industry National Environment Programme (WINEP) lists "
                   f"{'this action' if len(actions) == 1 else f'{len(actions)} actions'} on this overflow's permit. The date is the "
                   "date the action should be delivered, a deadline, not a record that it was:</p>"
                   f'<ul class="actions">{items}</ul>')
    elif actions is None:
        out.append("<p>The PR24 WINEP's deadlines are not in this build, so none is shown here.</p>")
    elif permit_ok:
        out.append("<p>The PR24 WINEP lists no storm overflow improvement action on this overflow's permit.</p>")
    if upgrade:
        did = "has upgraded" if upgrade.get("stage") == "upgraded" else "is upgrading"
        what = (f"its {escape(upgrade.get('source_name') or '')}, a name that could also mean another overflow nearby"
                if upgrade.get("match") == "shared name" else "this overflow")
        done = f", finished {day_said(upgrade['completed'])}" if upgrade.get("stage") == "upgraded" and upgrade.get("completed") else ""
        out.append(f'<p>{escape(company_name(upgrade["company"]))} says it {did} {what}{done} '
                   f'(<a href="{escape(upgrade["source_url"])}">its page</a>, read {escape(day_said(upgrade["checked"]))}).</p>')
    plans = UNLICENSED_PLANS.get(company)
    out.append("<p class=\"small muted\">Not published here: "
               + (f"{escape(company)}'s planned dates ({plans}), which carry no licence; " if plans else "")
               + "Water UK's National Storm Overflows Plan, whose terms forbid reuse without written permission.</p>")

    # Dry weather: SwimSignal's count, labelled as such.
    if dry and noted(dry["days"], dry["dry_days"]):
        out.append('<h2 id="dry-weather">Spills in dry weather</h2>'
                   f"<p>By SwimSignal's count from the EA's start/stop records, this overflow spilled on {dry['days']} of "
                   f"{dry['dry_days']} dry days in {dry['year']}. A dry day here is one with under 0.25&nbsp;mm of rain that day and "
                   'on each of the two before, from ERA5-Land rain estimates (<a href="methods.html#dry-weather">the method</a>). '
                   "This is SwimSignal's inference, not an Environment Agency finding. It names no cause: a blockage, a failed pump "
                   "and groundwater in the sewer look alike in these records. It is not a finding that any permit was broken.</p>")

    # Send it on.
    subject, text = mail_parts(plain, oid, company, str(permit) if permit_ok else None, spots, returns, record, actions or [], url)
    contact = CONTACT.get(company)
    out.append('<h2 id="send">Send this record</h2>'
               f"<p>The button opens your own email app with a short, factual draft about this overflow and a link to this page. "
               f"Read it, change it as you wish, and add the address yourself: SwimSignal sends nothing and keeps no copy.</p>"
               f'<p class="send"><a class="btn primary" href="{escape(mailto(subject, text))}">Send this record</a></p>'
               f"<p>{escape(company_name(company))}'s own contact details are "
               + (f'on <a href="{contact}">its contact page</a>' if contact else "on its website")
               + f'. To send the same record to your MP, <a href="{FIND_MP}">find your MP</a> on the UK Parliament website.</p>')
    out.append(f'<details class="fold"><summary>The draft</summary><pre class="draft">{escape(subject)}\n\n{escape(text)}</pre></details>')

    out.append('<h2 id="sources">Sources and credits</h2>'
               f'<p>{escape(CREDITS)} Sources: <a href="{EA_RETURNS}">annual returns</a>, <a href="{WINEP_PAGE}">PR24 WINEP</a>, '
               f'<a href="{EA_EVENTS}">start/stop data</a>, <a href="{HUB}">National Storm Overflow Hub</a>. '
               '<a href="terms.html#data">All credits and licences</a>.</p>')
    return "\n".join(out)


def _weight(w) -> str:
    return "–" if w is None or pd.isna(w) else "under 1%" if 0 < w < 0.005 else f"{100 * w:.0f}%"


def _flag(v) -> str:
    return "–" if v is None or pd.isna(v) or not str(v).strip() else str(v)


def description(plain: str, company: str, n: int) -> str:
    return (f"{plain}, a {company_name(company)} storm overflow upstream of {n} swim spot{'' if n == 1 else 's'}: its permit, "
            "spills each year from the Environment Agency's annual returns, and the improvements recorded for it.")


def site_page(oid: str, o: dict, mark: str, returns: pd.DataFrame | None = None, record: pd.DataFrame | None = None,
              actions: list[dict] | None = None, upgrade: dict | None = None, dry: dict | None = None, lengths: dict | None = None,
              root: str = "", as_of: str = "", template: str | None = None) -> str:
    """overflow/<id>/index.html for one overflow."""
    url = f"{root}overflow/{oid}/"
    company = str(returns["company"].dropna().iloc[-1]) if returns is not None and returns["company"].notna().any() else str(o["row"].get("company") or "")
    plain, _ = overflow_names(o["row"].get("site_name") if returns is None or not returns["site_name"].notna().any()
                              else returns["site_name"].dropna().iloc[-1], oid)
    desc = description(plain if plain != oid else f"Overflow {oid}", company, len(o["spots"]))
    title = f"{plain} ({oid})" if plain != oid else f"{company_name(company)} overflow {oid}"
    slots = {"title": escape(title), "mark": mark, "description": escape(desc),
             "body": body(oid, o, returns, record, actions, upgrade, dry, lengths or {}, url, as_of),
             "canonical": f'<link rel="canonical" href="{escape(url)}">' if root else "",
             "share": share_tags(f"{title} · SwimSignal", desc, url, root) if root else ""}
    html = template if template is not None else TEMPLATE.read_text()
    missing = set(SLOT.findall(html)) - slots.keys()
    if missing:
        raise ValueError(f"overflow.html has slots this build does not fill: {sorted(missing)}")
    return SLOT.sub(lambda m: slots[m.group(1)], html)
