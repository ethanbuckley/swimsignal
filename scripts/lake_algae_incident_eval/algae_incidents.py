"""docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md: the stated rules as functions of JSON, frames and arrays. No network.

The incident parser reads the EA's pollution-incident list (one bathing water's history, the JSON shape of
`pollution-incident.json?bathingWater.eubwidNotation=<id>`). Field names and the incident-type table are from the
EA's API reference (environment.data.gov.uk/bwq/doc/api-reference.html, read 26 October 2026), not from data.

The satellite reading and its pairing reuse docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md's harness
(scripts/lake_algae_sat_eval/protocol.py), loaded by path under its own module name so it cannot clash with another
`protocol` module.

Choices fixed here, before any incident history was fetched, and listed in the statement ("Harness choices"):
* The day of a time is its date as written. The reference gives xsd:dateTime with no zone.
* Days are 1 May to 30 September, 2020 to 2026, at the 14 sites past #377's size rule.
* A stratum is one bathing water in one season. A day without a reading is left out.
* S, the statistic, is the share of (incident day, control day) pairs in the same stratum where the incident day's
  reading is higher, ties counting a half: the Mann-Whitney U summed over strata, over the pairs summed over strata.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_SAT_DIR = Path(__file__).resolve().parents[1] / "lake_algae_sat_eval"
_spec = importlib.util.spec_from_file_location("lake_algae_sat_protocol", _SAT_DIR / "protocol.py")
sat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sat)

StopRule = sat.StopRule
sha256 = sat.sha256
check_hash = sat.check_hash

# --- fixed numbers -----------------------------------------------------------------------------------------
FEATURES_SHA256 = "41f234d3a953df246306aa7785978e7c3d76f82ed1765e5518923633c50b5d0e"   # #377, commit 4ec237b
SEASON_MONTHS = (5, 6, 7, 8, 9)
YEARS = tuple(range(2020, 2027))
PAIR_DAYS = 3
DESCRIPTION_PAIR_DAYS = (0, 7)
GATE_INCIDENT_DAYS, GATE_INCIDENTS, GATE_WATER_BODIES, GATE_STRATA = 30, 5, 4, 6
N_BOOT, N_PLACEBO, SEED = 2000, 200, 20261026
LO, HI = 2.5, 97.5                # one comparison judged: 95% intervals
B, H = 0.15, 0.05                 # on d = S - 0.5: S of 0.65 (the bar of both earlier lake tests), H a third of B
ANOMALY_MIN_SCENES = 5            # scenes in the reference half-month, other seasons, same bathing water
ANOMALY_S_MIN = 0.60
LOLO_S_MIN = 0.50

# The API reference's "Pollution Incident Types" table (code: description). Deprecated: 001 to 005.
INCIDENT_TYPES = {
    "001": "Bacterial contamination", "002": "Potential contamination from sewage",
    "003": "Non-bacterial contamination", "004": "Localised Flooding", "005": "Contamination from sewage",
    "010": "sewage", "011": "agricultural waste", "012": "animal waste", "013": "decaying marine life on beach",
    "014": "harmful algae", "015": "oil or fuel", "016": "chemicals", "017": "dredging or construction work",
    "018": "landslip", "019": "drain or road runoff", "020": "other",
}
ALGAE_CODE = "014"
ALGAE_WORDS = "harmful algae"
ALGA = re.compile(r"alga", re.I)   # any type label naming algae must be code 014, or the run stops
TYPE_URI = re.compile(r"https?://environment\.data\.gov\.uk/def/incident-type/(\d{3})\Z")

HISTORY_URL = ("https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident.json"
               "?bathingWater.eubwidNotation={}&_pageSize={}")
PAGE_SIZE = 200
EA_ID = re.compile(r"uk[a-z0-9]+-\d{5}\Z")


# --- parsing ------------------------------------------------------------------------------------------------
def _v(x):
    """A linked-data value: {"_value": ...} or a plain value; the first of a list."""
    if isinstance(x, list):
        x = x[0] if x else None
    return x.get("_value") if isinstance(x, dict) else x


def _words(x) -> str | None:
    if not isinstance(x, dict):
        return None
    v = _v(x.get("name")) or _v(x.get("label"))
    return " ".join(v.split()).lower() if isinstance(v, str) else None


def _day(stamp) -> date | None:
    """The date part of an xsd:dateTime or xsd:date as written ("2026-06-19T14:28:00" -> 19 June 2026)."""
    if not isinstance(stamp, str) or len(stamp) < 10:
        return None
    try:
        return date.fromisoformat(stamp[:10])
    except ValueError:
        return None


def incident_kind(type_obj) -> tuple[str, str | None, str | None]:
    """("algae" | "other" | "untyped", code, words) from a record's incidentType.

    Algae: notation "014" with the words "harmful algae". A code of 014 with other words, or words naming algae with
    another code, stops the run: the reference's table would no longer describe the data."""
    if not isinstance(type_obj, dict):
        return "untyped", None, None
    code = _v(type_obj.get("notation"))
    if not isinstance(code, str):
        m = TYPE_URI.match(type_obj.get("_about") or "")
        code = m[1] if m else None
    words = _words(type_obj)
    if code == ALGAE_CODE or (words and ALGA.search(words)):
        if code != ALGAE_CODE or words != ALGAE_WORDS:
            raise StopRule(f"incident type {code!r} {words!r}: code and words disagree with the API reference "
                           f"({ALGAE_CODE} = {ALGAE_WORDS!r})")
        return "algae", code, words
    if code is None and words is None:
        return "untyped", None, None
    return "other", code, words


def check_page(body, eubwid: str) -> list[dict]:
    """The items of one water's history page, after the completeness stop rules: the page holds fewer items than the
    page size asked for and has no next page, and every item lists the water asked for."""
    res = body.get("result") if isinstance(body, dict) else None
    items = res.get("items") if isinstance(res, dict) else None
    if not isinstance(items, list):
        raise StopRule(f"{eubwid}: no items list")
    per_page = res.get("itemsPerPage")
    if per_page != PAGE_SIZE or len(items) >= PAGE_SIZE or "next" in res:
        raise StopRule(f"{eubwid}: page may be incomplete (itemsPerPage {per_page}, {len(items)} items, "
                       f"next {'next' in res})")
    for i, it in enumerate(items):
        if eubwid not in _waters(it):
            raise StopRule(f"{eubwid}: item {i} does not list the water asked for")
    return items


def _waters(it) -> list[str]:
    w = it.get("bathingWater") if isinstance(it, dict) else None
    w = w if isinstance(w, list) else [w]
    return [x.get("eubwidNotation") for x in w if isinstance(x, dict) and isinstance(x.get("eubwidNotation"), str)
            and EA_ID.fullmatch(x["eubwidNotation"])]


def parse_items(items: list[dict]) -> list[dict]:
    """One record per item: incident id, the waters it lists, kind, code, words, start and end days, record time.
    An item with no incidentNotation stops the run (it cannot be grouped)."""
    out = []
    for i, it in enumerate(items):
        inc = it.get("incidentNotation")
        if not isinstance(inc, str) or not inc:
            raise StopRule(f"item {i}: no incidentNotation")
        kind, code, words = incident_kind(it.get("incidentType"))
        out.append({"incident": inc, "waters": _waters(it), "kind": kind, "code": code, "words": words,
                    "start_raw": _v(it.get("startOfIncident")), "end_raw": _v(it.get("endOfIncident")),
                    "start": _day(_v(it.get("startOfIncident"))), "end": _day(_v(it.get("endOfIncident"))),
                    "record_time": _v(it.get("som_recordDateTime")) or _v(it.get("recordDateTime")) or ""})
    return out


def latest_records(records: list[dict]) -> list[dict]:
    """One record per incident: the latest record time. The list endpoint already gives the most recent record per
    incident; an incident fetched under two waters appears twice. Two records with the same latest time that differ
    stop the run."""
    best: dict[str, dict] = {}
    for r in records:
        b = best.get(r["incident"])
        if b is None or r["record_time"] > b["record_time"]:
            best[r["incident"]] = r
        elif r["record_time"] == b["record_time"] and _key(r) != _key(b):
            raise StopRule(f"{r['incident']}: two different records at {r['record_time']}")
    return sorted(best.values(), key=lambda r: r["incident"])


def _key(r: dict):
    return (sorted(r["waters"]), r["kind"], r["code"], r["start"], r["end"])


def incidents_at_sites(records: list[dict], sites: set[str], fetch_day: date) -> pd.DataFrame:
    """One row per incident and test site it lists: bw_id, incident, kind, start, end (the fetch day when there is no
    end), open_ended. An algae incident at a test site with no readable start, or an end before its start, stops the
    run. A non-algae one with either is kept as its start day only (or the fetch day if it has no start), and
    counted."""
    rows = []
    for r in latest_records(records):
        for w in sorted(set(r["waters"]) & sites):
            start, end = r["start"], r["end"]
            bad = start is None or (end is not None and end < start)
            if bad and r["kind"] == "algae":
                raise StopRule(f"{r['incident']} at {w}: algae incident with start {r['start_raw']!r}, "
                               f"end {r['end_raw']!r}")
            first = start or fetch_day
            rows.append({"bw_id": w, "incident": r["incident"], "kind": r["kind"], "code": r["code"],
                         "words": r["words"], "start": first,
                         "end": first if bad else (fetch_day if end is None else end),
                         "open_ended": end is None, "malformed": bool(bad)})
    cols = ["bw_id", "incident", "kind", "code", "words", "start", "end", "open_ended", "malformed"]
    return pd.DataFrame(rows, columns=cols)


def season_days(year: int) -> list[date]:
    d0 = date(year, 5, 1)
    return [d0 + timedelta(days=i) for i in range((date(year, 9, 30) - d0).days + 1)]


def label_days(incidents: pd.DataFrame, sites: dict[str, str]) -> pd.DataFrame:
    """Every site-day, 1 May to 30 September 2020-2026: "incident" when an algae incident listing the site is open
    that day (start day to end day, both counted); else "excluded" when any other or untyped incident is; else
    "control". `sites`: bw_id -> water body."""
    rows = [(s, sites[s], d, y) for s in sorted(sites) for y in YEARS for d in season_days(y)]
    out = pd.DataFrame(rows, columns=["bw_id", "water_body", "date", "season"])
    inc = np.zeros(len(out), dtype=bool)
    exc = np.zeros(len(out), dtype=bool)
    for r in incidents.itertuples(index=False):
        m = ((out["bw_id"] == r.bw_id) & (out["date"] >= r.start) & (out["date"] <= r.end)).to_numpy()
        if r.kind == "algae":
            inc |= m
        else:
            exc |= m
    out["label"] = np.where(inc, "incident", np.where(exc, "excluded", "control"))
    return out


# --- readings -----------------------------------------------------------------------------------------------
def scenes(features: pd.DataFrame, sites: set[str]) -> pd.DataFrame:
    """#377's usable scenes with a reading, one per site and UTC date (sat.one_per_date)."""
    s = sat.one_per_date(features[features["bw_id"].isin(sites)])
    return s.assign(scene_date=pd.to_datetime(s["scene_date"]).dt.date)


def attach_readings(days: pd.DataFrame, sc: pd.DataFrame, window_days: int = PAIR_DAYS) -> pd.DataFrame:
    """A day d takes the latest usable scene at its site dated d - window to d. Adds reading and scene_date (NaN and
    None where there is none)."""
    d = days.drop(columns=[c for c in ("reading", "scene_date") if c in days]).copy()
    d["_t"] = pd.to_datetime(d["date"])
    d["_i"] = np.arange(len(d))
    s = sc[["bw_id", "scene_date", "reading"]].copy()
    s["_t"] = pd.to_datetime(s["scene_date"])
    m = pd.merge_asof(d.sort_values("_t"), s.sort_values("_t"), on="_t", by="bw_id", direction="backward",
                      tolerance=pd.Timedelta(days=window_days))
    m = m.sort_values("_i").set_index(days.index)
    out = days.drop(columns=[c for c in ("reading", "scene_date") if c in days]).copy()
    out["reading"] = m["reading"].astype(float)
    out["scene_date"] = [x if isinstance(x, date) else None for x in m["scene_date"]]
    return out


def half_month(d: date) -> tuple[int, int]:
    return d.month, 0 if d.day <= 15 else 1


def anomalies(days: pd.DataFrame, sc: pd.DataFrame) -> np.ndarray:
    """Each day's reading minus the median reading of usable scenes at the same bathing water in the same calendar
    half-month (1-15, 16-end) of its scene, in the other seasons. NaN when that reference has fewer than
    ANOMALY_MIN_SCENES scenes, or the day has no reading."""
    sc = sc.assign(season=[d.year for d in sc["scene_date"]], hm=[half_month(d) for d in sc["scene_date"]])
    groups = {k: g for k, g in sc.groupby(["bw_id", "hm"])}
    out = np.full(len(days), np.nan)
    for i, (s, sd, r) in enumerate(zip(days["bw_id"], days["scene_date"], days["reading"], strict=True)):
        if sd is None or not np.isfinite(r):
            continue
        g = groups.get((s, half_month(sd)))
        if g is None:
            continue
        ref = g.loc[g["season"] != sd.year, "reading"].to_numpy(dtype=float)
        ref = ref[np.isfinite(ref)]
        if len(ref) >= ANOMALY_MIN_SCENES:
            out[i] = r - float(np.median(ref))
    return out


# --- the statistic ------------------------------------------------------------------------------------------
def stratum_u(values: np.ndarray, is_incident: np.ndarray) -> tuple[float, int]:
    """(Mann-Whitney U of incident over control values, ties a half; n_incident x n_control)."""
    v = np.asarray(values, dtype=float)
    y = np.asarray(is_incident, dtype=bool)
    ok = np.isfinite(v)
    v, y = v[ok], y[ok]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return 0.0, 0
    from scipy.stats import rankdata
    r = rankdata(v)
    return float(r[y].sum() - n1 * (n1 + 1) / 2), n1 * n0


def strata_table(days: pd.DataFrame, value: str = "reading", label: str = "label") -> pd.DataFrame:
    """Per bathing water and season: incident and control days with a value, U and pairs. Excluded days are left
    out. A stratum counts when pairs > 0."""
    d = days[days[label].isin(("incident", "control")) & np.isfinite(days[value].to_numpy(dtype=float))]
    rows = []
    for (s, y, wb), g in d.groupby(["bw_id", "season", "water_body"], sort=True):
        inc = (g[label] == "incident").to_numpy()
        u, n = stratum_u(g[value].to_numpy(dtype=float), inc)
        rows.append({"bw_id": s, "season": int(y), "water_body": wb, "incident_days": int(inc.sum()),
                     "control_days": int((~inc).sum()), "U": u, "pairs": n, "auc": u / n if n else float("nan")})
    cols = ["bw_id", "season", "water_body", "incident_days", "control_days", "U", "pairs", "auc"]
    return pd.DataFrame(rows, columns=cols)


def pooled_s(table: pd.DataFrame) -> float:
    t = table[table["pairs"] > 0]
    return float(t["U"].sum() / t["pairs"].sum()) if len(t) else float("nan")


def boot_s(table: pd.DataFrame, n: int | None = None, seed: int = SEED) -> np.ndarray:
    """S for each cluster-bootstrap draw: water bodies with a counted stratum, drawn with replacement (sorted
    order). N_BOOT draws unless n is given."""
    n = N_BOOT if n is None else n
    t = table[table["pairs"] > 0]
    keys = np.array(sorted(t["water_body"].unique()))
    if len(keys) == 0:
        return np.full(n, np.nan)
    u = t.groupby("water_body")["U"].sum().reindex(keys).to_numpy()
    p = t.groupby("water_body")["pairs"].sum().reindex(keys).to_numpy()
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        k = rng.integers(0, len(keys), size=len(keys))
        out[i] = u[k].sum() / p[k].sum()
    return out


def interval(draws: np.ndarray) -> tuple[float, float]:
    v = np.asarray(draws, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return float("nan"), float("nan")
    return float(np.percentile(v, LO)), float(np.percentile(v, HI))


def label_s(s: float, lo: float, hi: float, secondary_harm: bool = False) -> str:
    """The near-miss labels on d = S - 0.5, with B and H above (sat.label, the framework's order)."""
    if not all(math.isfinite(x) for x in (s, lo, hi)):
        return "No data"
    return sat.label(s - 0.5, lo - 0.5, hi - 0.5, B, H, secondary_harm=secondary_harm)


def rotate_labels(days: pd.DataFrame, rng: np.random.Generator) -> pd.Series:
    """The shift placebo: in each site-season with an incident day, the whole day-label pattern (incident, excluded,
    control) is moved round the 153-day season by an offset drawn from 1 to 152, wrapping at the ends. Readings stay
    on their days. Site-seasons are taken in sorted order, one draw each."""
    out = days["label"].copy()
    for (_s, _y), g in sorted(days.groupby(["bw_id", "season"]), key=lambda kv: kv[0]):
        if not (g["label"] == "incident").any():
            continue
        g = g.sort_values("date")
        k = int(rng.integers(1, len(g)))
        out.loc[g.index] = np.roll(g["label"].to_numpy(), k)
    return out


def placebo(days: pd.DataFrame, n: int | None = None, seed: int = SEED) -> np.ndarray:
    n = N_PLACEBO if n is None else n
    rng = np.random.default_rng(seed)
    vals = np.empty(n)
    for i in range(n):
        d = days.assign(label=rotate_labels(days, rng))
        vals[i] = pooled_s(strata_table(d))
    return vals


def placebo_summary(real: float, vals: np.ndarray) -> dict:
    v = np.asarray(vals, dtype=float)
    ok = v[np.isfinite(v)]
    p95 = float(np.percentile(ok, 95)) if len(ok) else float("nan")
    k190 = float(np.sort(ok)[189]) if len(ok) >= 190 else float("nan")
    return {"real": real, "p95": p95, "rank_190th": k190, "at_or_above_real": int((ok >= real).sum()),
            "without_value": int((~np.isfinite(v)).sum()),
            "lowest": float(ok.min()) if len(ok) else float("nan"),
            "median": float(np.median(ok)) if len(ok) else float("nan"),
            "highest": float(ok.max()) if len(ok) else float("nan"),
            "holds": bool(math.isfinite(real) and real > p95 and real > k190)}


def gate(days: pd.DataFrame, table: pd.DataFrame, incidents: pd.DataFrame) -> dict:
    """Counted on days with a reading, in counted strata."""
    t = table[table["pairs"] > 0]
    counted = set(zip(t["bw_id"], t["season"], strict=True))
    d = days[(days["label"] == "incident") & np.isfinite(days["reading"].to_numpy(dtype=float))]
    d = d[[(s, y) in counted for s, y in zip(d["bw_id"], d["season"], strict=True)]]
    alg = incidents[incidents["kind"] == "algae"]
    contributing = set()
    for r in alg.itertuples(index=False):
        hit = d[(d["bw_id"] == r.bw_id) & (d["date"] >= r.start) & (d["date"] <= r.end)]
        if len(hit):
            contributing.add(r.incident)
    out = {"incident_days_with_reading": int(len(d)), "incidents_with_a_day": len(contributing),
           "water_bodies": int(t["water_body"].nunique()), "strata": int(len(t))}
    out["judged"] = bool(out["incident_days_with_reading"] >= GATE_INCIDENT_DAYS
                         and out["incidents_with_a_day"] >= GATE_INCIDENTS
                         and out["water_bodies"] >= GATE_WATER_BODIES and out["strata"] >= GATE_STRATA)
    return out


def lolo(table: pd.DataFrame) -> dict:
    """S with each water body (with a counted stratum) left out in turn."""
    t = table[table["pairs"] > 0]
    out = {}
    for wb in sorted(t["water_body"].unique()):
        rest = t[t["water_body"] != wb]
        out[wb] = pooled_s(rest) if len(rest) else None
    return out


def summarise(table: pd.DataFrame, secondary_harm: bool = False) -> dict:
    s = pooled_s(table)
    lo, hi = interval(boot_s(table))
    return {"S": s, "L": lo, "U": hi, "d": s - 0.5, "label": label_s(s, lo, hi, secondary_harm),
            "strata": int((table["pairs"] > 0).sum()), "pairs": int(table["pairs"].sum())}


def score(days: pd.DataFrame, incidents: pd.DataFrame, sc: pd.DataFrame) -> dict:
    """Every stated figure. `days`: labelled site-days with readings attached (attach_readings) and water_body."""
    table = strata_table(days)
    out = {"gate": gate(days, table, incidents), "strata": table.to_dict("records")}
    groups = {}
    for name, members in (("Lake District", table["water_body"].isin(sat.LAKE_DISTRICT)),
                          ("lowland", ~table["water_body"].isin(sat.LAKE_DISTRICT))):
        g = table[members]
        groups[name] = summarise(g) if (g["pairs"] > 0).any() else {"label": "No data"}
    harm = any(g["label"] in ("Possible harm", "Harm") for g in groups.values())
    primary = summarise(table, secondary_harm=harm)
    out["primary"] = {**primary, "B": B, "H": H}
    out["groups"] = groups
    pl = placebo(days)
    out["placebo"] = placebo_summary(primary["S"], pl)
    an = days.assign(anomaly=anomalies(days, sc))
    at = strata_table(an, value="anomaly")
    a_s = pooled_s(at)
    a_lo, a_hi = interval(boot_s(at))
    out["anomaly"] = {"S": a_s, "L": a_lo, "U": a_hi, "strata": int((at["pairs"] > 0).sum()),
                      "holds": bool(math.isfinite(a_s) and a_s >= ANOMALY_S_MIN and a_lo > 0.5)}
    lv = lolo(table)
    computed = [v for v in lv.values() if v is not None and math.isfinite(v)]
    out["lolo"] = {"by_water_body_left_out": lv,
                   "holds": bool(len(computed) >= 2 and all(v > LOLO_S_MIN for v in computed))}
    out["groups_hold"] = not harm
    holds = out["placebo"]["holds"] and out["anomaly"]["holds"] and out["lolo"]["holds"] and not harm
    if not out["gate"]["judged"]:
        verdict = "Too few to judge"
    elif primary["label"] == "Better" and holds:
        verdict = "Passes"
    elif primary["label"] == "Promising, not shown" and holds:
        verdict = "Promising, not shown"
    else:
        verdict = "Fails"
    out["verdict"] = verdict
    return out


# --- the saved fetch ------------------------------------------------------------------------------------------
def load_fetch(path: Path, sites: list[str]) -> tuple[list[dict], date]:
    """incidents.json from incident_fetch.py: the stop rules on completeness, then the records and the fetch day."""
    f = json.loads(Path(path).read_text())
    got = [r["bw_id"] for r in f["responses"]]
    if sorted(got) != sorted(sites) or len(set(got)) != len(got):
        raise StopRule(f"the fetch holds {sorted(got)}, not one response for each of {sorted(sites)}")
    records = []
    for r in f["responses"]:
        if r["status"] != 200:
            raise StopRule(f"{r['bw_id']}: HTTP {r['status']}")
        if r["url"] != HISTORY_URL.format(r["bw_id"], PAGE_SIZE):
            raise StopRule(f"{r['bw_id']}: unexpected URL {r['url']}")
        records += parse_items(check_page(r["body"], r["bw_id"]))
    return records, date.fromisoformat(f["fetch_day"])
