"""Past-sample histories outside England (docs/SAMPLE-HISTORY-CONTRACT-v1.md): every published lab sample at a bathing
water, with its date, from the official body that took it. Observations only: no forecast, no model, no estimate.

- The Republic of Ireland: the EPA's Bathing Water Open Data API (CC BY 4.0). Every in-season result from 22 May 2014
  and every voluntary out-of-season one, at each of the EPA's waters.
- Wales: Natural Resources Wales (Open Government Licence v3) at two river bathing waters, The Warren at Hay-on-Wye and
  Llandeilo Swing Bridge. The Water Quality Archive's lab results at their bathing-water stations, joined to NRW's
  bathing-water service's in-season samples, which run further into 2026 than the archive copy.

scripts/export_sample_histories.py fetches the raw answers off CI and calls export_ireland / export_wales, which read
those answers only. The build splits each file into an index and one file a water (build_site.write_sample_histories)
for samples.html.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA, MAJOR, VERSION = "swimsignal.sample-history", "1", "1.0.0"
RESEARCH = Path(__file__).resolve().parents[2] / "data" / "research"
FILES = {n: RESEARCH / f"sample_history_{n}.v1.json" for n in ("ireland", "wales")}

EPA = "https://data.epa.ie/bw/api/v1/"
EPA_LOCATIONS, EPA_IN_SEASON, EPA_OUT_SEASON = EPA + "locations", EPA + "measurements/in-season", EPA + "measurements/out-season"

# The two Welsh river bathing waters (data/raw/wales_bathing_waters.json) and the Water Quality Archive station at
# each, by the station's own name ("WYE @ THE WARREN BW", "Tywi Swing Bridge BW", station type "FRESHWATER - BATHING
# WATER"). Where both hold a sample, their E. coli and enterococci matched the service's exactly on 13 Nov 2026.
WALES_WATERS = (
    {"bw_id": "ukl2400-38620", "station": "S5520068", "name": "The Warren, Hay-on-Wye", "river": "Wye"},
    {"bw_id": "ukl1401-37650", "station": "S6020030", "name": "Llandeilo Swing Bridge", "river": "Tywi"},
)
NRW_PROFILE = "https://environment.data.gov.uk/wales/bathing-waters/profiles/profile.html?site={}"
WQA_RECORD = "https://datamap.gov.wales/layers/geonode:nrw_water_quality_archive_stations/metadata_detail"
NRW_SERVICE = "https://environment.data.gov.uk/wales/bathing-waters/"
WQA_ECOLI, WQA_IE = "2348", "3723"   # "Escherichia coli : Confirmed : MF"; "Enterococci: Intestinal: Confirmed: MF"
WQA_REASONS = {"ENVIRONMENTAL MONITORING STATUTORY (EU DIRECTIVES)": "statutory",
               "PLANNED INVESTIGATION (NATIONAL AGENCY POLICY)": "investigation"}
STATUS = {"Excellent": "E", "Good": "G", "Sufficient": "S", "Poor": "P"}   # the EPA's word for each sample, one letter
COUNT = re.compile(r"([<>]?)(\d+(?:\.\d+)?)\Z")

# The credits, as each body asks on the day (13 Nov 2026, docs/SAMPLE-HISTORY-CONTRACT-v1.md). NRW's attribution
# statement is copied from the Water Quality Archive's record word for word, with its capitals; the Ordnance Survey
# line that follows it there is for the station map, which this file does not use.
CREDITS = {
    "ireland": ("Contains bathing water data from the Environmental Protection Agency (Ireland), Bathing Water Open Data "
                "API, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). SwimSignal reorders the "
                "EPA's samples by water and date and draws them; the values are the EPA's, unchanged."),
    "wales": ("Contains Natural Resources Wales information © Natural Resources Wales and Database Right. All rights "
              "Reserved. Open Government Licence v3.0."),
}
SOURCES = {
    "ireland": {"name": "EPA Bathing Water Open Data API", "publisher": "Environmental Protection Agency (Ireland)",
                "url": "https://data.epa.ie/api-list/bathing-water-open-data/", "licence": "CC BY 4.0",
                "licence_url": "https://creativecommons.org/licenses/by/4.0/", "checked": "2026-11-13",
                "licence_wording": "The data provided in the API is licensed under a Creative Commons Attribution 4.0 "
                                   "International License."},
    "wales": {"name": "NRW Water Quality Archive, and NRW bathing water quality (in-season samples)",
              "publisher": "Natural Resources Wales", "url": WQA_RECORD, "service": NRW_SERVICE,
              "licence": "Open Government Licence v3.0",
              "licence_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
              "checked": "2026-11-13",
              "licence_wording": "Data may be re-used under the terms of the Open Government Licence providing it is "
                                 "done so, acknowledging both the source and NRW's copyright."},
}
# What may be said beside the samples, and what may not (the contract's lists).
CLAIM = {
    "public_wording": "Lab samples taken by the official body, each on the date shown. A sample describes the water at that "
                      "place and time only. SwimSignal makes no forecast here and adds no estimate.",
    "not_claimed": ["that the water was safe or unsafe on any day other than a sample's, or at any other time that day",
                    "anything about today's water",
                    "a rating: the official rating uses four seasons of scheduled samples by a set method",
                    "where any bacteria came from"],
}
QUALIFIERS = {
    "<": "Below the lab's lower limit: fewer than that number were found, possibly none. It is not a count of that number.",
    ">": "Above the lab's upper limit: more than that number, how many more is not known.",
}
METHODS = {
    "ireland": ["The EPA's data does not name a lab method for each sample.",
                "Lower limits differ from lab to lab: most give '<10', some '<1', and a few '<5', '<20' or '<50'. A plain "
                "count of 1 to 9 can only come from a lab whose limit is lower than 10.",
                "Upper limits also differ: '>2419' and '>24196' are the top of a most-probable-number tray, read neat or "
                "diluted ten times (inferred from the values; the EPA does not say), and '>2000', '>2005' or '>2010' come "
                "from other labs.",
                "A count of 0 is given as the EPA lists it.",
                "Each sample also has the EPA's own word for it, Excellent, Good, Sufficient or Poor, which the EPA "
                "assesses against the standards in the Bathing Water Quality Regulations 2008.",
                "In-season samples run from 22 May to 15 September. Samples outside those dates are voluntary, reported by "
                "some councils since 2016, and do not count towards a rating.",
                "Before its December report each year, the EPA keeps only the scheduled in-season samples of that season "
                "and drops the investigative ones, so a past season can lose samples between downloads (25,978 results on "
                "31 October 2026, 25,895 on 13 November 2026)."],
    "wales": ["E. coli: 'Escherichia coli : Confirmed : MF', counted by membrane filtration (the water is passed through a "
              "filter and the colonies that grow are counted) and confirmed by a further test, per 100 ml.",
              "Intestinal enterococci: 'Enterococci: Intestinal: Confirmed: MF', the same way, reported per 0.1 litre, which "
              "is 100 ml. The archive also holds a presumptive count before confirmation; this file keeps the confirmed "
              "one, which is the one NRW's bathing-water service gives.",
              "'<10' is below the lab's lower limit of 10 per 100 ml.",
              "The archive marks each result 'Low' or 'Low Additional' in its method_name column. NRW's record does not "
              "say what that means, so the file keeps it as given and the page does not use it.",
              "Every sample here is a spot sample from the river. None is flagged 'deviating', NRW's mark for a sample "
              "that failed the lab's acceptance checks.",
              "'Statutory' samples were taken for the bathing-water rules; 'investigation' samples were planned surveys, "
              "including those of 2023 before either water had a bathing season."],
}


def count(text) -> tuple[float, str | None] | None:
    """('<10' -> (10.0, '<'), '630' -> (630.0, None)) from a count as a source gives it, or None."""
    if isinstance(text, bool) or text is None:
        return None
    m = COUNT.fullmatch(str(text).strip())
    return (float(m[2]), m[1] or None) if m else None


def _num(v: float):
    return int(v) if float(v).is_integer() else v


def over(v: float, q: str | None, line: int | None) -> bool | None:
    """Over the line, None without one. A '<' limit is never over it; a '>' limit is when the limit is at or above it."""
    if line is None:
        return None
    return False if q == "<" else (v >= line if q == ">" else v > line)


def summary(samples: list[dict], line: int | None) -> dict:
    """Counts for one water: samples, first and last dates, over the line, given as below or above a limit, and the
    EPA's Poor and out-of-season counts where the samples carry them."""
    ts = sorted(s["t"] for s in samples)
    out = {"samples": len(samples), "first": ts[0][:10] if ts else None, "last": ts[-1][:10] if ts else None,
           "over_line": sum(bool(s.get("over")) for s in samples) if line else None,
           "below_limit": sum(s["q"] == "<" for s in samples), "above_limit": sum(s["q"] == ">" for s in samples),
           "seasons": len({t[:4] for t in ts})}
    if any("status" in s for s in samples):
        out["poor"] = sum(s.get("status") == "Poor" for s in samples)
    if any("season" in s for s in samples):
        out["out_of_season"] = sum(s.get("season") == "out" for s in samples)
    return out


def _ledger(raw: Path) -> list[dict]:
    rows = [json.loads(x) for x in (raw / "ledger.jsonl").read_text().splitlines() if x.strip()]
    if not rows or any(r["status"] != 200 for r in rows):
        raise ValueError(f"{raw}: the ledger is empty or records a refusal; fetch again into a new directory")
    for r in rows:   # every page read is the page the ledger recorded
        if hashlib.sha256((raw / r["file"]).read_bytes()).hexdigest() != r["sha256"]:
            raise ValueError(f"{r['file']} differs from the ledger")
    return rows


def _doc(nation: str, rows: list[dict], sites: list[dict], extra: dict) -> dict:
    n = sum(s["summary"]["samples"] for s in sites)
    firsts, lasts = [s["summary"]["first"] for s in sites if s["summary"]["first"]], [s["summary"]["last"] for s in sites if s["summary"]["last"]]
    return {"schema": SCHEMA, "version": VERSION, "nation": nation,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "fetched_at": min(r["at"] for r in rows), "period": {"first": min(firsts), "last": max(lasts)},
            "source": SOURCES[nation], "credit": CREDITS[nation], "claim": CLAIM, "qualifiers": QUALIFIERS,
            "methods": METHODS[nation], "lines": {"coast": 500, "estuary": 500, "lake": 900, "river": 900},
            "requests": [{k: r[k] for k in ("at", "url", "status", "bytes", "sha256")} for r in rows],
            **extra, "coverage": {"waters": len(sites), "with_samples": sum(bool(s["summary"]["samples"]) for s in sites),
                                  "samples": n}, "sites": sites}


# ------------------------------------------------------------------ the Republic of Ireland
def ireland_samples(items: list[dict], season: str) -> tuple[dict[str, list[dict]], Counter]:
    """{beach id: samples} from the EPA's measurement rows, each {"t", "ecoli", "q", "ie", "ie_q", "status", "season",
    "id"}, and a count of rows left out by reason. A row without a readable id, date or E. coli count is left out."""
    from dipcast.ireland import ID
    out, dropped = {}, Counter()
    for m in items:
        key, day, ec = m.get("beach_id"), str(m.get("result_date") or ""), count(m.get("e_coli_result"))
        if not isinstance(key, str) or not ID.fullmatch(key):
            dropped["id"] += 1
        elif not re.fullmatch(r"\d{4}-\d\d-\d\d", day):
            dropped["date"] += 1
        elif ec is None:
            dropped["e_coli"] += 1
        else:
            ie = count(m.get("intestinal_enterococci_result"))
            word = m.get("sample_water_quality_status")
            out.setdefault(key, []).append({"t": day, "ecoli": _num(ec[0]), "q": ec[1], "ie": _num(ie[0]) if ie else None,
                                            "ie_q": ie[1] if ie else None, "status": word if word in STATUS else None,
                                            "season": season, "id": m.get("monitoring_result_id")})
    return out, dropped


def export_ireland(raw: Path) -> dict:
    """The EPA's every sample by water, from a fetch's raw pages (scripts/export_sample_histories.py)."""
    from dipcast import ireland as ie
    rows = _ledger(raw)
    pages = lambda k: [m for p in sorted(raw.glob(f"{k}_p*.json"), key=lambda x: int(x.stem.split("_p")[1]))
                       for m in json.loads(p.read_text())["list"]]
    counts = {k: json.loads((raw / f"{k}_p1.json").read_text())["count"] for k in ("in", "out")}
    ins, outs = pages("in"), pages("out")
    if (len(ins), len(outs)) != (counts["in"], counts["out"]):
        raise ValueError(f"pages hold {len(ins)} and {len(outs)} rows, the EPA counts {counts}")
    if len({m["monitoring_result_id"] for m in ins + outs}) != len(ins) + len(outs):
        raise ValueError("a result id appears twice")
    by_in, d1 = ireland_samples(ins, "in")
    by_out, d2 = ireland_samples(outs, "out")
    listed = {s["id"]: s for s in ie.parse_locations(json.loads((raw / "locations.json").read_text())["list"])}
    names = {m["beach_id"]: (ie._clean(m.get("beach_name")), ie._clean(m.get("county_name"))) for m in ins + outs}
    sites = []
    for key in sorted(set(listed) | set(by_in) | set(by_out), key=lambda k: (ie.fold((listed.get(k) or {}).get("name") or names[k][0]), k)):
        loc = listed.get(key)
        name, county = (loc["name"], loc["county"]) if loc else names[key]
        kind, kind_from = (loc["kind"], loc["kind_from"]) if loc else ie.water_kind(key, name)
        line = {"coast": 500, "estuary": 500, "lake": 900, "river": 900}.get(kind)
        samples = sorted(by_in.get(key, []) + by_out.get(key, []), key=lambda s: (s["t"], s["id"] or 0))
        for s in samples:
            s["over"] = over(s["ecoli"], s["q"], line)
        sites.append({"id": key, "name": name, "county": county, "listed": bool(loc),
                      "designated": loc["designated"] if loc else None, "kind": kind, "kind_from": kind_from, "line": line,
                      "rating": loc["rating"] if loc else None, "unrated_year": loc.get("unrated_year") if loc else None,
                      "page": loc["page"] if loc else ie.PAGE_URL.format(key),
                      "summary": summary(samples, line),
                      # Compact: [date, E. coli, enterococci, the EPA's word], E. coli and enterococci as the EPA gave them.
                      "in": [[s["t"], _raw(s["ecoli"], s["q"]), _raw(s["ie"], s["ie_q"]), STATUS.get(s["status"], "")]
                             for s in samples if s["season"] == "in"],
                      "out": [[s["t"], _raw(s["ecoli"], s["q"]), _raw(s["ie"], s["ie_q"]), STATUS.get(s["status"], "")]
                              for s in samples if s["season"] == "out"]})
    return _doc("ireland", rows, sites, {
        "columns": ["date", "e_coli", "intestinal_enterococci", "status"], "status_letters": {v: k for k, v in STATUS.items()},
        "epa_counts": counts, "dropped": dict(d1 + d2),
        "kinds_note": "A water's kind is ireland.water_kind's: the EPA's code for designated waters, a check for ten in "
                      "County Monaghan, else its name. A Lough or Loch with no check has kind 'unknown' and no line."})


def _raw(v, q) -> str | None:
    return None if v is None else f"{q or ''}{v:g}" if isinstance(v, float) else f"{q or ''}{v}"


def ireland_site_samples(site: dict) -> list[dict]:
    """A water's samples from the compact file as the viewer reads them: {"t", "ecoli", "q", "ie", "ie_q", "status",
    "season", "over"}, in date order."""
    letters = {v: k for k, v in STATUS.items()}
    out = []
    for season in ("in", "out"):
        for day, ec, ie_, st in site.get(season) or []:
            e, i = count(ec), count(ie_)
            out.append({"t": day, "ecoli": _num(e[0]), "q": e[1], "ie": _num(i[0]) if i else None, "ie_q": i[1] if i else None,
                        "status": letters.get(st), "season": season, "over": over(e[0], e[1], site.get("line"))})
    return sorted(out, key=lambda s: s["t"])


# ------------------------------------------------------------------ Wales
def wqa_samples(text: str, station: str) -> dict[str, dict]:
    """{"YYYY-MM-DDTHH:MM": sample} at one Water Quality Archive station, from its CSV rows: confirmed E. coli and
    intestinal enterococci with their signs ('<', '>' or '---'), the sampling reason, the method name and any
    deviating flag."""
    out: dict[str, dict] = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["station_number"] != station or r["parameter_shortname"] not in (WQA_ECOLI, WQA_IE):
            continue
        t = r["sampling_datetime"][:16].replace(" ", "T")
        s = out.setdefault(t, {"t": t, "reason": WQA_REASONS.get(r["sampling_reason"], "other"),
                               "reason_text": r["sampling_reason"], "mechanism": r["sampling_mechanism"],
                               "method_name": r["method_name"], "deviating": False})
        v = float(r["sample_value"])
        q = r["sign"] if r["sign"] in ("<", ">") else None
        if r["parameter_shortname"] == WQA_ECOLI:
            s["ecoli"], s["q"] = _num(v), q
        else:
            s["ie"], s["ie_q"] = _num(v), q
        s["deviating"] = s["deviating"] or (r.get("deviating_result") or "").strip().lower() == "yes"
    return {t: s for t, s in out.items() if "ecoli" in s}


def bwq_samples(items: list[dict]) -> dict[str, dict]:
    """{"YYYY-MM-DDTHH:MM": sample} from NRW's bathing-water service's in-season samples for one water."""
    from dipcast.wales import _count
    out = {}
    for it in items:
        t = str(((it.get("sampleDateTime") or {}).get("inXSDDateTime") or {}).get("_value") or "")[:16]
        ec = _count(it.get("escherichiaColiCount"), it.get("escherichiaColiQualifier"))
        ie_ = _count(it.get("intestinalEnterococciCount"), it.get("intestinalEnterococciQualifier"))
        if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", t) and ec:
            q = lambda c: None if c["qualifier"] == "=" else c["qualifier"]   # noqa: E731
            out[t] = {"t": t, "ecoli": _num(ec["value"]), "q": q(ec), "ie": _num(ie_["value"]) if ie_ else None,
                      "ie_q": q(ie_) if ie_ else None}
    return out


def merge_wales(archive: dict[str, dict], service: dict[str, dict], line: int = 900) -> list[dict]:
    """One list from both: a sample in both must hold the same counts (else ValueError); each says where it came from
    ("archive", "service" or both). A service-only sample has no sampling reason in the archive: it is "statutory",
    since the service lists only bathing-water samples."""
    out = []
    for t in sorted(set(archive) | set(service)):
        a, s = archive.get(t), service.get(t)
        if a and s and any(a.get(k) != s.get(k) for k in ("ecoli", "q", "ie", "ie_q")):
            raise ValueError(f"{t}: the archive and the service disagree: {a} {s}")
        x = {**(s or {}), **(a or {})}
        x.setdefault("reason", "statutory")
        x["src"] = [n for n, v in (("archive", a), ("service", s)) if v]
        x["over"] = over(x["ecoli"], x["q"], line)
        out.append(x)
    return out


def export_wales(raw: Path) -> dict:
    """Hay-on-Wye and Llandeilo from a fetch's raw directory (data/raw/nrw_sample_history)."""
    rows = _ledger(raw)
    text = (raw / "wqa_rows.csv").read_text()
    zips = json.loads((raw / "wqa_zips.json").read_text())
    snap = json.loads((Path(__file__).resolve().parents[2] / "data" / "raw" / "wales_bathing_waters.json").read_text())
    from dipcast import wales as w
    rated = {s["id"]: s for s in w.parse_sites(snap["site_items"])}
    sites = []
    for x in WALES_WATERS:
        items = json.loads((raw / f"bwq_{x['bw_id']}.json").read_text())["result"]["items"]
        samples = merge_wales(wqa_samples(text, x["station"]), bwq_samples(items))
        r = rated.get(x["bw_id"]) or {}
        sites.append({"id": x["bw_id"], "name": x["name"], "river": x["river"], "kind": "river", "line": 900,
                      "station": x["station"], "rating": r.get("rating"), "page": NRW_PROFILE.format(x["bw_id"]),
                      "summary": {**summary(samples, 900), "archive": sum("archive" in s["src"] for s in samples),
                                  "service": sum("service" in s["src"] for s in samples),
                                  "investigation": sum(s["reason"] == "investigation" for s in samples)},
                      "samples": samples})
    return _doc("wales", rows, sites, {
        "rating_snapshot": snap.get("fetched_at"),
        "archive": {"zips": zips, "read": "The zips as downloaded from NRW's DataMapWales folder on 4 Oct 2026 (their CSVs "
                    "dated 4 Oct 2026), copied read-only; data/raw/nrw_sample_history/wqa_rows.csv holds their rows at "
                    "the two stations."},
        "times": "Sample times as NRW gives them, with no offset; read as local time in Wales (inferred: the archive and "
                 "the service agree to the minute and the times fall in the working day)."})


# ------------------------------------------------------------------ the site
def read(nation: str, path: Path | None = None) -> tuple[dict | None, str | None]:
    """The committed file and None, or None and why it is not published (missing, another schema or major version)."""
    p = Path(path or FILES[nation])
    if not p.is_file():
        return None, "no export in this build"
    doc = json.loads(p.read_text())
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != MAJOR or doc.get("nation") != nation:
        return None, f"export is {doc.get('schema')} {doc.get('version')} for {doc.get('nation')}, not {SCHEMA} {MAJOR}.x"
    return doc, None


def site_samples(nation: str, site: dict) -> list[dict]:
    return ireland_site_samples(site) if nation == "ireland" else site.get("samples") or []


def attach(snapshot: dict | None, nation: str, path: Path | None = None) -> int:
    """Each directory site with a history its `history` (samples, first and last dates), for the link on its card on
    the coverage page. Returns how many sites got one."""
    doc, why = read(nation, path)
    if why or not snapshot:
        return 0
    by = {s["id"]: s["summary"] for s in doc["sites"] if s["summary"]["samples"]}
    n = 0
    for site in snapshot.get("sites") or []:
        sm = by.get(site.get("id"))
        if sm:
            site["history"] = {k: sm[k] for k in ("samples", "first", "last")}
            n += 1
    return n


def history_line(h: dict) -> str:
    """The card's link text: "Every sample, 2014 to 2026 (162)". Plain text."""
    a, b = h["first"][:4], h["last"][:4]
    years = a if a == b else f"{a} to {b}"
    return f"Every lab sample, {years} ({h['samples']:,})"
