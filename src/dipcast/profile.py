"""The storm overflows upstream of a place and how often each spilled in 2021-2025, from the
Environment Agency's annual returns (event duration monitoring, OGL v3; data/processed/annual_returns.parquet).

Shared by scripts/site_profile.py, which traces any point for a bathing-water applicant
(docs/MARKETS-2026-10.md, T8), and the site's profile pages, spot/<id>/profile/ (T6), which the build
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
REACH_NOTE = ("Reach is the share of a spill's bacteria SwimSignal's model expects to arrive here, after die-off "
              "on the way and dilution by the river. Weighting by it counts an hour of spilling just upstream for "
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


def in_short(t: pd.DataFrame) -> dict:
    """How many overflows upstream, how many within NEAR_KM, how many live, and the nearest's km."""
    km = t["km"] if "km" in t else km_upstream(t)
    return {"n": len(t), "near": int((km <= NEAR_KM).sum()), "live": int(t["has_live"].fillna(False).astype(bool).sum()),
            "nearest_km": float(km.min()) if len(t) else None}


def hours_away(h) -> str:
    return "under 1" if h is not None and not pd.isna(h) and h < 1 else fmt(h, 0)


def reach(w) -> str:
    return "–" if w is None or pd.isna(w) else "<1%" if 0 < w < 0.005 else f"{100 * w:.0f}%"


def uptime(v) -> str:
    return "–" if v is None or pd.isna(v) else f"{v:.0f}%"


# ------------------------------------------------------------------ the site's page, spot/<id>/profile/
TEMPLATE = Path(__file__).parent / "site" / "profile.html"
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
    ovt = label == "overflows"
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


def body(spot: dict, t: pd.DataFrame | None) -> str:
    """The page's main content. t is with_returns() of the spot's overflows, or None when the build has no
    list for it (no file in data/upstream/)."""
    sid, name = escape(str(spot["id"])), escape(str(spot["name"]))
    total = (spot.get("upstream_summary") or {}).get("overflows") or 0
    km = (spot.get("assumptions") or {}).get("max_upstream_km") or config.MAX_UPSTREAM_KM
    links = (f'<p class="dateline"><a href="spot/{sid}/">The spot\'s forecast</a> · '
             f'<a href="organisers.html#spot={sid}">For event organisers</a></p>')
    out = [f"<h1>Overflow history upstream of {name}</h1>", links, f"<p>{escape(SITE_CAVEAT)}</p>"]
    err = str(spot.get("error") or "")
    if err.startswith("An isolated lake"):
        out.append("<p>No river flows into this lake in the river network, so no storm overflow can reach it by water. "
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
                   f"<li>{s['live']} of them report live to the water companies' public feeds.</li>"
                   f"<li>The nearest is {fmt(s['nearest_km'], 1)}&nbsp;km upstream.</li></ul></aside>")
        out.append("<h2>Each year, all overflows upstream</h2>")
        out.append(_table([("Year", False), ("Overflows with a return", True), ("Spills", True), ("Spill hours", True),
                           ("Spill hours, weighted by reach", True)],
                          [[str(r["year"]), str(r["with_return"]), f"{r['spills']:,}", fmt(r["hours"]), fmt(r["reach_hours"])]
                           for r in years], "yearly totals"))
        out.append(f'<p class="small muted">{escape(REACH_NOTE)} <a href="methods.html#how">How reach is worked out</a>.</p>')
        out.append(f"<h2>The overflows, by reach</h2><p>All {s['n']}, the one whose spills matter most here first. "
                   "Hours away is how long sewage takes to arrive at the model's river speed.</p>")
        named = lambda r: name_case(r["site_name"] if pd.notna(r.get("site_name")) else r["site_id"])
        rows = [[f'{escape(named(r))}<br><span class="muted">{escape(str(r["site_id"]))}</span>',
                 escape(str(r.get("company") or "")), fmt(r["km"], 1), hours_away(r.get("travel_h")), escape(reach(r.get("weight"))),
                 fmt(r.get("spills_2023")), fmt(r.get("spills_2024")), fmt(r.get("spills_2025")),
                 fmt(r.get("spill_hours_2025")), uptime(r.get("edm_operational_pct_2025"))] for _, r in t.iterrows()]
        out.append(_table([("Overflow and id", False), ("Company", False), ("km upstream", True), ("Hours away", True),
                           ("Reach", True), ("Spills 2023", True), ("Spills 2024", True), ("Spills 2025", True),
                           ("Spill hours 2025", True), ("Monitor uptime 2025", True)], rows, "overflows"))
        out.append('<p class="small muted">A dash: no annual return for that overflow in that year.</p>')
    out.append(f'<h2>Sources and credits</h2><p>{escape(CREDITS)} <a href="terms.html#data">All credits and licences</a>.</p>')
    return "\n".join(out)


def site_page(spot: dict, t: pd.DataFrame | None, mark: str, template: str | None = None) -> str:
    """spot/<id>/profile/index.html for one spot. `mark` is the brand mark's inline SVG (build_site.MARK)."""
    name = escape(str(spot["name"]))
    slots = {"name": name, "mark": mark, "body": body(spot, t),
             "description": escape(f"The monitored storm overflows upstream of {spot['name']} and how often each "
                                   "spilled in each year from 2021 to 2025, from the Environment Agency's annual returns.")}
    html = template if template is not None else TEMPLATE.read_text()
    missing = set(SLOT.findall(html)) - slots.keys()
    if missing:
        raise ValueError(f"profile.html has slots this build does not fill: {sorted(missing)}")
    return SLOT.sub(lambda m: slots[m.group(1)], html)
