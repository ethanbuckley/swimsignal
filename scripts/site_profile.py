"""A profile of the storm overflows upstream of one point, for a group applying for bathing-water
status (docs/MARKETS-2026-10.md, task T8; Defra's deadline for 2026 applications is 15 Oct 2026).

    uv run python scripts/site_profile.py 53.93189 -1.81618 --name "Wharfe at Cromwheel, Ilkley" --river "River Wharfe"

Writes <out>/<slug>.md and <out>/<slug>.html. Everything comes from files already on disk: the river
network, the overflow table and the Environment Agency's annual returns (event duration monitoring,
2021-2025, OGL v3). Nothing is downloaded, so it is safe to run while the site builds elsewhere.

The trace is the site's own: locate_pin and upstream_overflows with the site's settings, so the list
of overflows matches a spot's page. "Reach" is the transport weight (die-off times dilution): the
share of a spill's bacteria the model expects to arrive here, before any rain or spill forecast.
"""
from __future__ import annotations

import argparse
import html
import logging
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dipcast import config

log = logging.getLogger("site_profile")
YEARS = [2021, 2022, 2023, 2024, 2025]
TOP = 25   # rows in the table; the CSV-like Markdown keeps them all
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


def name_case(s: str) -> str:
    """Overflow names that arrive in capitals ("GRASSINGTON/STW") in normal case, as the site shows them."""
    return re.sub(r"[A-Za-z']+", lambda m: m[0][0] + m[0][1:].lower() if re.fullmatch(r"[A-Z']{4,}", m[0]) else m[0],
                  str(s or ""))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "profile"


def trace(lat: float, lon: float, kind: str | None, river: str | None) -> tuple[pd.DataFrame, dict]:
    """The overflows upstream of the point, as a spot's forecast finds them."""
    from dipcast.model.forecast import _net, _overflows
    from dipcast.model.transport import locate_pin, upstream_overflows
    net, ov = _net(), _overflows()
    pin = locate_pin(net, lon, lat, kind_hint=kind, river_hint=river)
    where = {"mode": pin.mode, "watercourse": pin.watercourse,
             "snap_m": None if pin.snap is None else round(pin.snap.dist_m)}
    if pin.mode in ("none", "isolated"):
        return pd.DataFrame(), where
    up = upstream_overflows(net, pin, ov, velocity_ms=config.RIVER_VELOCITY_MS, max_km=config.MAX_UPSTREAM_KM)
    return up, where


def with_returns(up: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Each overflow's spills, spill hours and monitor uptime for each year, by its id."""
    ar = returns[returns["site_id"].isin(up["site_id"])]
    wide = ar.pivot_table(index="site_id", columns="year", values=["spills", "spill_hours", "edm_operational_pct"],
                          aggfunc="max")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    return up.merge(wide, left_on="site_id", right_index=True, how="left")


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


def fmt(v, digits: int = 0) -> str:
    if v is None or pd.isna(v):
        return "–"
    return f"{v:,.{digits}f}"


def render(name: str, lat: float, lon: float, where: dict, t: pd.DataFrame, rows: list[dict]) -> tuple[str, str]:
    today = pd.Timestamp.now(tz="Europe/London").date().isoformat()
    n, live = len(t), int(t["has_live"].fillna(False).sum()) if len(t) else 0
    near = t[t["distance_m"] <= 10_000] if len(t) else t
    head = [f"# Storm overflows upstream of {name}", "",
            f"Point {lat:.5f}, {lon:.5f} · traced along {where.get('watercourse') or 'the river network'} · made {today}", "",
            f"> {CAVEAT}", ""]
    if not n:
        msg = ("No monitored storm overflow was found within 60 km upstream of this point."
               if where["mode"] not in ("none", "isolated") else
               "This point is not on the river network, or is a lake with no river flowing into it, so no overflow can reach it by water.")
        md = "\n".join(head + [msg, "", CREDITS, ""])
        return md, to_html(name, md)
    lines = head + [
        "## In short", "",
        f"- **{n}** monitored storm overflows drain into the water upstream, within 60 km; **{len(near)}** of them within 10 km.",
        f"- {live} of them report live to the water companies' public feeds.",
        f"- The nearest is {fmt(t['distance_m'].min() / 1000, 1)} km upstream.",
        "", "## Each year, all overflows upstream", "",
        "| Year | Overflows with a return | Spills | Spill hours | Spill hours, weighted by reach |",
        "|---|---|---|---|---|"]
    lines += [f"| {r['year']} | {r['with_return']} | {r['spills']:,} | {fmt(r['hours'])} | {fmt(r['reach_hours'])} |" for r in rows]
    lines += ["", ("Reach is the share of a spill's bacteria SwimSignal's model expects to arrive here, after die-off "
              "on the way and dilution by the river (swimsignal.co.uk/methods.html). Weighting by it counts an "
              "hour of spilling just upstream for far more than one 40 km away. Spills are counted by the EA's "
              "12/24 method: any discharge in the first 12 hours counts as one spill, then one more for each "
              "24 hours with any discharge."), "",
              f"## The overflows, by reach (top {min(TOP, n)} of {n})", "",
              "| Overflow (id) | Company | km upstream | Hours away | Reach | Spills 2023 | 2024 | 2025 | Hours 2025 | Monitor uptime 2025 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in t.head(TOP).iterrows():
        hours = "under 1" if pd.notna(r["travel_h"]) and r["travel_h"] < 1 else fmt(r["travel_h"], 0)
        lines.append(f"| {name_case(r['site_name'])} ({r['site_id']}) | {r['company']} | {fmt(r['distance_m'] / 1000, 1)} | "
                     f"{hours} | {fmt(100 * r['weight'], 0)}% | {fmt(r.get('spills_2023'))} | "
                     f"{fmt(r.get('spills_2024'))} | {fmt(r.get('spills_2025'))} | {fmt(r.get('spill_hours_2025'))} | "
                     f"{fmt(r.get('edm_operational_pct_2025'), 0)}{'%' if pd.notna(r.get('edm_operational_pct_2025')) else ''} |")
    lines += ["", "## Sources", "", CREDITS, ""]
    md = "\n".join(lines)
    return md, to_html(name, md)


def to_html(name: str, md: str) -> str:
    """A plain printable page from the Markdown above: headings, lists, one table, a quote, bold."""
    out, table = [], []

    def inline(s: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(s))

    def flush():
        if table:
            rows = [c for c in table if not set(c.replace("|", "").strip()) <= {"-"}]
            cells = [[x.strip() for x in r.strip("|").split("|")] for r in rows]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                       + "</tbody></table>")
            table.clear()
    in_list = False
    for ln in md.splitlines():
        if ln.startswith("|"):
            table.append(ln)
            continue
        flush()
        if ln.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(ln[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("> "):
            out.append(f"<p class='caveat'>{inline(ln[2:])}</p>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
    flush()
    if in_list:
        out.append("</ul>")
    style = ("body{font:15px/1.5 Georgia,serif;color:#14212b;max-width:960px;margin:24px auto;padding:0 16px}"
             "h1{font-size:24px}h2{font-size:18px;margin-top:28px}"
             ".caveat{border-left:3px solid #3d5b5d;padding-left:12px}"
             "table{border-collapse:collapse;width:100%;font:13px/1.35 Helvetica,Arial,sans-serif}"
             "th,td{border-bottom:1px solid #dde5e7;padding:5px 6px;text-align:left;vertical-align:top}"
             "@media print{body{margin:0}h2{break-after:avoid}}")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Overflows upstream of "
            f"{html.escape(name)} · SwimSignal</title><style>{style}</style></head><body>{''.join(out)}</body></html>\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("--name", required=True, help="the site's name, as the application calls it")
    ap.add_argument("--river", help="the river the site is on, so the point snaps to it (as spots.csv's river)")
    ap.add_argument("--lake", action="store_true", help="the site is a lake")
    ap.add_argument("--out", type=Path, default=Path("profiles"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    up, where = trace(a.lat, a.lon, "lake" if a.lake else None, a.river)
    returns = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    t = with_returns(up, returns) if len(up) else up
    md, page = render(a.name, a.lat, a.lon, where, t, summary(t) if len(t) else [])
    a.out.mkdir(parents=True, exist_ok=True)
    base = a.out / slug(a.name)
    base.with_suffix(".md").write_text(md)
    base.with_suffix(".html").write_text(page)
    print(f"{len(t)} overflows upstream ({where['mode']}, {where.get('watercourse')}); wrote {base}.md and .html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
