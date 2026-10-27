"""scripts/lake_algae_incident_eval (docs/LAKE-ALGAE-INCIDENT-TEST-2026-10.md), on synthetic data only: no network, no
incident history, no satellite reading. The type rule against the API reference's table; the page stop rules; one
record per incident; day labels; pairing; the stratified statistic; the gate; a reading that tracks incident days
passes; a reading that only rises through the season, or only tells a green lake from a clear one, does not; the
fetch's caps and its one-fetch rule."""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lake_algae_incident_eval"))
import incident_fetch as fe
import algae_incidents as inc
import incident_score as sco

ROOT = Path(__file__).resolve().parents[1]


# --- items in the API's JSON shape (values made up) -----------------------------------------------------------
def item(incident: str, waters: list[str], code: str | None = "014", words: str | None = "harmful algae",
         start: str | None = "2025-07-01T10:00:00", end: str | None = None, record: str = "2025-07-01T10:05:00"):
    it = {"_about": f"http://environment.data.gov.uk/data/bathing-water-quality/pollution-incident/{incident}"
                    f"/recordDateTime/x",
          "bathingWater": [{"eubwidNotation": w, "name": {"_value": w, "_datatype": "langString"}} for w in waters],
          "incidentNotation": incident, "som_recordDateTime": {"_value": record, "_datatype": "dateTime"}}
    if len(waters) == 1:
        it["bathingWater"] = it["bathingWater"][0]
    if code is not None or words is not None:
        t = {"_about": f"http://environment.data.gov.uk/def/incident-type/{code}"}
        if code is not None:
            t["notation"] = code
        if words is not None:
            t["name"] = {"_value": words, "_datatype": "langString", "_lang": "en"}
            t["label"] = [{"_value": words, "_datatype": "langString", "_lang": "en"}]
        it["incidentType"] = t
    if start is not None:
        it["startOfIncident"] = {"_value": start, "_datatype": "dateTime"}
    if end is not None:
        it["endOfIncident"] = {"_value": end, "_datatype": "dateTime"}
    return it


def page(items, per_page=inc.PAGE_SIZE, nxt=False):
    res = {"items": items, "itemsPerPage": per_page, "page": 0, "startIndex": 1}
    if nxt:
        res["next"] = "https://environment.data.gov.uk/doc/...&_page=1"
    return {"format": "linked-data-api", "version": "0.2", "result": res}


# --- the type rule ----------------------------------------------------------------------------------------------
def test_type_table_names_algae_once():
    named = [c for c, w in inc.INCIDENT_TYPES.items() if inc.ALGA.search(w)]
    assert named == [inc.ALGAE_CODE] and inc.INCIDENT_TYPES[inc.ALGAE_CODE] == inc.ALGAE_WORDS


def test_incident_kind():
    assert inc.incident_kind(item("a", ["ukx-00001"])["incidentType"])[0] == "algae"
    assert inc.incident_kind(item("a", ["ukx-00001"], "010", "sewage")["incidentType"])[0] == "other"
    assert inc.incident_kind(None)[0] == "untyped"
    # The code from the URI when notation is missing.
    t = item("a", ["ukx-00001"], None, "harmful algae")["incidentType"]
    t["_about"] = "http://environment.data.gov.uk/def/incident-type/014"
    assert inc.incident_kind(t)[:2] == ("algae", "014")
    # Words with odd case and spacing still match.
    assert inc.incident_kind(item("a", ["x"], "014", " Harmful  Algae ")["incidentType"])[0] == "algae"
    with pytest.raises(inc.StopRule):
        inc.incident_kind(item("a", ["x"], "014", "blue-green bloom")["incidentType"])
    with pytest.raises(inc.StopRule):
        inc.incident_kind(item("a", ["x"], "021", "algal scum")["incidentType"])


# --- pages and records ------------------------------------------------------------------------------------------
W1, W2 = "ukd1203-45625", "ukd1203-45650"


def test_check_page_stop_rules():
    good = page([item("1", [W1])])
    assert len(inc.check_page(good, W1)) == 1
    with pytest.raises(inc.StopRule):
        inc.check_page(page([item("1", [W1])], per_page=50), W1)
    with pytest.raises(inc.StopRule):
        inc.check_page(page([item(str(i), [W1]) for i in range(inc.PAGE_SIZE)]), W1)
    with pytest.raises(inc.StopRule):
        inc.check_page(page([item("1", [W1])], nxt=True), W1)
    with pytest.raises(inc.StopRule):
        inc.check_page(page([item("1", [W2])]), W1)
    with pytest.raises(inc.StopRule):
        inc.check_page({"result": {}}, W1)


def test_latest_record_per_incident():
    recs = inc.parse_items([
        item("1", [W1, W2], end="2025-07-05T09:00:00", record="2025-07-05T09:01:00"),
        item("1", [W1, W2], end=None, record="2025-07-01T10:05:00"),
        item("1", [W1, W2], end="2025-07-05T09:00:00", record="2025-07-05T09:01:00"),   # same record, other site
    ])
    best = inc.latest_records(recs)
    assert len(best) == 1 and best[0]["end"] == date(2025, 7, 5)
    clash = inc.parse_items([item("1", [W1], end="2025-07-05T09:00:00", record="t"),
                             item("1", [W1], end="2025-07-06T09:00:00", record="t")])
    with pytest.raises(inc.StopRule):
        inc.latest_records(clash)
    with pytest.raises(inc.StopRule):
        inc.parse_items([{"incidentType": None}])


def test_incidents_at_sites_and_day_labels():
    fetch_day = date(2026, 10, 27)
    recs = inc.parse_items([
        item("a", [W1, W2], start="2025-07-01T23:50:00", end="2025-07-03T00:10:00"),
        item("b", [W1], "010", "sewage", start="2025-07-02T08:00:00", end="2025-07-10T08:00:00"),
        item("c", [W2], start="2026-09-29T12:00:00"),                    # no end: open to the fetch day
        item("d", ["ukx9999-00000"], start="2025-06-01T12:00:00"),       # not a test site
        item("e", [W1], "015", "oil or fuel", start="2025-08-10T08:00:00", end="2025-08-01T08:00:00"),  # malformed
    ])
    t = inc.incidents_at_sites(recs, {W1, W2}, fetch_day)
    assert sorted(t["incident"]) == ["a", "a", "b", "c", "e"]
    c = t[t["incident"] == "c"].iloc[0]
    assert c["end"] == fetch_day and c["open_ended"]
    assert int(t["malformed"].sum()) == 1
    days = inc.label_days(t, {W1: "Windermere", W2: "Windermere"}).set_index(["bw_id", "date"])["label"]
    assert days[(W1, date(2025, 6, 30))] == "control"
    assert days[(W1, date(2025, 7, 1))] == "incident"          # start day counted
    assert days[(W1, date(2025, 7, 3))] == "incident"          # end day counted
    assert days[(W1, date(2025, 7, 4))] == "excluded"          # sewage still open
    assert days[(W1, date(2025, 7, 11))] == "control"
    assert days[(W2, date(2025, 7, 4))] == "control"           # sewage was at W1 only
    assert days[(W2, date(2026, 9, 30))] == "incident"         # open to the fetch day, cut at season end
    assert days[(W1, date(2025, 8, 10))] == "excluded"         # malformed non-algae: its start day only
    assert days[(W1, date(2025, 8, 11))] == "control"
    bad = inc.parse_items([item("z", [W1], start="2025-08-10T08:00:00", end="2025-08-01T08:00:00")])
    with pytest.raises(inc.StopRule):
        inc.incidents_at_sites(bad, {W1}, fetch_day)
    with pytest.raises(inc.StopRule):
        inc.incidents_at_sites(inc.parse_items([item("z", [W1], start=None)]), {W1}, fetch_day)


# --- pairing and the statistic ------------------------------------------------------------------------------
def features_frame(rows):
    return pd.DataFrame([{"bw_id": s, "water_body": "X", "tile": "T", "item_id": f"{s}-{d}-{k}", "scene_date": str(d),
                          "clear_core": c, "n_core": 20, "usable": u, "reading": r}
                         for k, (s, d, r, u, c) in enumerate(rows)])


def test_attach_readings_window():
    f = features_frame([(W1, date(2025, 7, 1), 0.1, True, 20), (W1, date(2025, 7, 5), 0.5, True, 20),
                        (W1, date(2025, 7, 5), 0.9, True, 10),           # same date, fewer clear pixels: not used
                        (W1, date(2025, 7, 3), 0.7, False, 20)])         # not usable
    sc = inc.scenes(f, {W1})
    days = pd.DataFrame({"bw_id": W1, "date": [date(2025, 6, 30), date(2025, 7, 1), date(2025, 7, 4),
                                               date(2025, 7, 5), date(2025, 7, 8), date(2025, 7, 9)]})
    r = inc.attach_readings(days, sc)
    assert np.isnan(r["reading"].iloc[0])
    assert r["reading"].iloc[1:5].tolist() == [0.1, 0.1, 0.5, 0.5]     # d - 3 counted
    assert np.isnan(r["reading"].iloc[5])                               # d - 4 not
    assert r["scene_date"].iloc[4] == date(2025, 7, 5)
    r0 = inc.attach_readings(days, sc, window_days=0)
    assert r0["reading"].notna().sum() == 2


def test_stratified_u_by_hand():
    u, n = inc.stratum_u(np.array([3.0, 1.0, 2.0, 2.0]), np.array([True, False, False, True]))
    # incident 3 beats 1 and 2 (2); incident 2 beats 1, ties 2 (1.5): U = 3.5 of 4 pairs
    assert (u, n) == (3.5, 4)
    assert inc.stratum_u(np.array([1.0, np.nan]), np.array([True, False])) == (0.0, 0)
    t = pd.DataFrame({"water_body": ["A", "B"], "U": [3.5, 0.0], "pairs": [4, 2]})
    assert inc.pooled_s(t) == pytest.approx(3.5 / 6)


def test_labels_on_s():
    assert inc.label_s(0.70, 0.56, 0.80) == "Better"
    assert inc.label_s(0.60, 0.47, 0.75) == "Promising, not shown"
    assert inc.label_s(0.60, 0.47, 0.75, secondary_harm=True) != "Promising, not shown"
    assert inc.label_s(0.48, 0.40, 0.60) == "Possible harm"
    assert inc.label_s(float("nan"), 0.4, 0.6) == "No data"


# --- whole runs on synthetic lakes ------------------------------------------------------------------------------
SITES = {"ukd0000-00001": "Windermere", "ukd0000-00002": "Windermere", "ukd0000-00003": "Coniston Water",
         "ukf0000-00004": "Rutland Water", "ukj0000-00005": "Frensham Great Pond", "uki0000-00006": "The Serpentine",
         "ukf0000-00007": "Colwick Country Park, West Lake"}
GREEN, FRENSHAM = "ukf0000-00004", "ukj0000-00005"
YEARS = (2023, 2024, 2025, 2026)


@pytest.fixture(autouse=True)
def few_years(monkeypatch):
    monkeypatch.setattr(inc, "YEARS", YEARS)
    monkeypatch.setattr(inc, "N_BOOT", 300)
    monkeypatch.setattr(inc, "N_PLACEBO", 200)


def synthetic(kind: str, seed: int = 1):
    """Incidents of 10 to 25 days at each site in two or three seasons, at varied times of the season, and scenes
    every 2 days. kind: "day" (reading up on incident days), "season" (reading rises through the season and the
    incidents sit late), "lake" (a green lake with incidents, no link to the day)."""
    rng = np.random.default_rng(seed)
    records, frows = [], []
    n = 0
    windows = {}
    for s in sorted(SITES):
        for y in YEARS:
            if rng.random() < 0.35:
                continue
            length = int(rng.integers(10, 26))
            if kind == "season":
                start = date(y, 8, 1) + timedelta(days=int(rng.integers(0, 30)))
            else:
                start = date(y, 5, 1) + timedelta(days=int(rng.integers(0, 150 - length)))
            end = start + timedelta(days=length)
            n += 1
            records.append(item(f"i{n}", [s], start=f"{start}T09:00:00", end=f"{end}T09:00:00", record=f"r{n}"))
            windows[(s, y)] = (start, end)
    green = {s: (0.3 if s == GREEN else 0.0) for s in SITES}
    for s in sorted(SITES):
        for y in YEARS:
            for d in inc.season_days(y)[::2]:
                r = green[s] + rng.normal(0, 0.05)
                if kind == "season":
                    r += 0.003 * (d - date(y, 5, 1)).days
                w = windows.get((s, y))
                if kind == "day" and w and w[0] <= d <= w[1]:
                    r += 0.12
                frows.append((s, d, r, True, 20))
    sizes = {s: {"name": s, "water_body": wb, "in_test": True} for s, wb in SITES.items()}
    return inc.parse_items(records), features_frame(frows), sizes


def test_day_signal_passes():
    recs, f, sizes = synthetic("day")
    rep = sco.score_frames(recs, date(2026, 10, 27), f, sizes)
    r = rep["result"]
    assert r["gate"]["judged"]
    assert r["primary"]["label"] == "Better"
    assert r["placebo"]["holds"] and r["anomaly"]["holds"] and r["lolo"]["holds"]
    assert r["verdict"] == "Passes"


def test_season_trend_alone_does_not_pass():
    recs, f, sizes = synthetic("season")
    r = sco.score_frames(recs, date(2026, 10, 27), f, sizes)["result"]
    assert r["primary"]["S"] > 0.65                  # raw S rewards the season's rise
    assert not r["anomaly"]["holds"]                 # the half-month anomaly does not
    assert r["verdict"] != "Passes"


def test_green_lake_alone_does_not_pass():
    recs, f, sizes = synthetic("lake")
    r = sco.score_frames(recs, date(2026, 10, 27), f, sizes)["result"]
    assert abs(r["primary"]["S"] - 0.5) < 0.1
    assert r["verdict"] != "Passes"


def test_too_few_to_judge():
    recs, f, sizes = synthetic("day")
    one = [x for x in recs if x["waters"] == [FRENSHAM]][:1]
    rep = sco.score_frames(one, date(2026, 10, 27), f, sizes)
    assert not rep["result"]["gate"]["judged"]
    assert rep["result"]["verdict"] == "Too few to judge"
    assert np.isfinite(rep["result"]["primary"]["S"])   # still reported as description
    assert "without_frensham_2026" in rep["description"]


def test_placebo_is_seeded():
    recs, f, sizes = synthetic("day")
    sites = {k: v["water_body"] for k, v in sizes.items()}
    t = inc.incidents_at_sites(recs, set(sites), date(2026, 10, 27))
    days = inc.attach_readings(inc.label_days(t, sites), inc.scenes(f, set(sites)))
    a, b = inc.placebo(days, n=5), inc.placebo(days, n=5)
    assert np.array_equal(a, b)
    rot = inc.rotate_labels(days, np.random.default_rng(0))
    for _, g in days.assign(rot=rot).groupby(["bw_id", "season"]):
        assert (g["label"] == "incident").sum() == (g["rot"] == "incident").sum()


# --- the fetch --------------------------------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def iter_bytes(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


class FakeHttp:
    def __init__(self, answers):
        self.answers, self.urls = answers, []

    @contextlib.contextmanager
    def stream(self, method, url, headers=None):
        self.urls.append(url)
        status, body = self.answers(url)
        yield FakeResponse(status, body)


def ok_answers(url):
    w = url.split("eubwidNotation=")[1].split("&")[0]
    return 200, json.dumps(page([item("1", [w])])).encode()


def test_client_rules(tmp_path):
    sleeps = []
    c = fe.Client(ledger=tmp_path / "l.jsonl", client=FakeHttp(ok_answers), sleep=sleeps.append, clock=lambda: 0.0)
    url = inc.HISTORY_URL.format(W1, inc.PAGE_SIZE)
    c.get(url)
    c.get(url)
    assert sleeps == [fe.PAUSE_S]
    with pytest.raises(fe.Stop):
        c.get("https://example.com/x")
    with pytest.raises(fe.Stop):
        c.get(url, headers={"Authorization": "x"})
    stop = fe.Client(client=FakeHttp(lambda u: (429, b"")), sleep=lambda s: None)
    with pytest.raises(fe.Stop):
        stop.get(url)
    capped = fe.Client(client=FakeHttp(ok_answers), sleep=lambda s: None)
    capped.requests = fe.MAX_REQUESTS
    with pytest.raises(fe.Stop):
        capped.get(url)
    assert len((tmp_path / "l.jsonl").read_text().splitlines()) == 2


def test_fetch_once_and_load(tmp_path):
    feats = tmp_path / "features.parquet"
    feats.write_bytes(b"not the real file")
    with pytest.raises(inc.StopRule):            # a hash that is not #377's
        fe.fetch(tmp_path / "out", feats, inc.sha256(feats), sites=[W1, W2])
    with pytest.raises(inc.StopRule):            # #377's hash, but the file differs
        fe.fetch(tmp_path / "out", feats, inc.FEATURES_SHA256, sites=[W1, W2])
    # The rest with the hash check bypassed (the real file is not used in tests).
    out = tmp_path / "out"
    http = FakeHttp(ok_answers)
    orig = inc.check_hash
    inc.check_hash = lambda p, h: None
    try:
        h = fe.fetch(out, feats, inc.FEATURES_SHA256, client=fe.Client(client=http, sleep=lambda s: None),
                     sites=[W1, W2])
        with pytest.raises(inc.StopRule):
            fe.fetch(out, feats, inc.FEATURES_SHA256, client=fe.Client(client=http, sleep=lambda s: None),
                     sites=[W1, W2])
    finally:
        inc.check_hash = orig
    assert len(http.urls) == 2 and (out / "incidents.sha256").read_text().strip() == h
    records, day = inc.load_fetch(out / "incidents.json", [W1, W2])
    assert len(records) == 2 and isinstance(day, date)
    with pytest.raises(inc.StopRule):
        inc.load_fetch(out / "incidents.json", [W1, W2, "ukd1101-45800"])


def test_fetch_plan_fits_caps():
    sites = fe.test_sites()
    assert len(sites) == 14 and len(sites) <= fe.MAX_REQUESTS
    sat_doc = (ROOT / "docs" / "LAKE-ALGAE-SATELLITE-TEST-2026-10.md").read_text()
    assert inc.FEATURES_SHA256 in sat_doc
    doc = (ROOT / "docs" / "LAKE-ALGAE-INCIDENT-TEST-2026-10.md").read_text()
    for x in (inc.FEATURES_SHA256, str(inc.SEED), "`014`", '"harmful algae"'):
        assert x in doc
