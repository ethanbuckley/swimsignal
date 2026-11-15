"""The coastal C1 rain fetcher's rules (docs/COASTAL-C1-PROTOCOL-2026-11.md, section 3), offline: every answer comes
from a stub, no request leaves the machine, and no sample result is read."""

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from dipcast.ingest import rainfall

HERE = Path(__file__).resolve().parents[1] / "scripts" / "coastal_c1"
spec = importlib.util.spec_from_file_location("coastal_c1_fetch_rain", HERE / "fetch_rain.py")
fr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fr
spec.loader.exec_module(fr)

DAY1 = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
DAY2 = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


@pytest.fixture
def sites(tmp_path):
    """Twelve made-up mapped points in twelve cells, and one point with no archive point (left out)."""
    rows = [{"site_id": f"s{i}", "lat": 50.0 + i * 0.1, "lon": -4.0, "wqa_point": f"P{i}"} for i in range(12)]
    rows.append({"site_id": "nomap", "lat": 55.0, "lon": -1.0, "wqa_point": None})
    p = tmp_path / "sites.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def body_for(p: dict, hours: int | None = None) -> bytes:
    lats, lons = p["latitude"].split(","), p["longitude"].split(",")
    t = pd.date_range(p["start_date"], f"{p['end_date']} 23:00", freq="h")
    if hours is not None:
        t = t[:hours]
    items = [{"latitude": float(a) + 0.02, "longitude": float(b), "elevation": 5.0,
              "hourly": {"time": t.strftime("%Y-%m-%dT%H:%M").tolist(), "precipitation": [0.1] * len(t)}}
             for a, b in zip(lats, lons, strict=True)]
    return json.dumps(items if len(items) > 1 else items[0]).encode()


class Stub:
    """Answers in turn from `script` (a status, or a callable of the params), then 200s."""

    def __init__(self, script=()):
        self.script, self.calls = list(script), []

    def __call__(self, url, p):
        self.calls.append((url, p))
        s = self.script.pop(0) if self.script else 200
        if callable(s):
            return s(p)
        if s is None:
            return fr.Answer(None, b"", "ConnectTimeout")
        if s == 200:
            return fr.Answer(200, body_for(p))
        return fr.Answer(s, json.dumps({"error": True, "reason": "made up"}).encode())


def go(out, sites, stub, when=DAY1, cap=fr.DAILY_CAP, sleeps=None):
    return fr.run(out, get=stub, now=lambda: when, sleep=(sleeps.append if sleeps is not None else lambda s: None),
                  cap=cap, sites=sites)


def test_no_request_before_22_november(tmp_path, sites):
    stub = Stub()
    assert go(tmp_path / "o", sites, stub, when=datetime(2026, 11, 21, 23, 59, tzinfo=UTC)) == fr.TOO_EARLY
    assert stub.calls == [] and not (tmp_path / "o" / "ledger.jsonl").exists()


def test_weight_is_open_meteos_rule_as_the_build_counts_it():
    for n, days, v in [(10, 160, 1), (5, 160, 1), (1, 14, 1), (3, 365, 1), (7, 6, 3), (2, 400, 12)]:
        assert fr.call_weight(n, days, v) == rainfall.call_weight(n, days, v)
    assert fr.season_days(2016)[2] == 160   # leap years change nothing: 24 Apr to 30 Sep
    assert fr.job_weight(2026, [(0, 0)] * 10) == pytest.approx(10 * 0.1 * 160 / 14)


def test_the_real_fetch_is_sized_before_any_call():
    d = fr.dry_run()
    assert (d["cells"], d["seasons"], d["requests"]) == (185, 15, 285)
    assert d["calls"] == pytest.approx(3171.4, abs=0.1)
    assert d["days_at_cap"] == 4 and d["max_requests_a_day"] == 87


def test_request_asks_for_era5_land_in_utc_for_one_season(tmp_path, sites):
    stub = Stub()
    go(tmp_path / "o", sites, stub)
    url, p = stub.calls[0]
    assert url == fr.URL and p["models"] == "era5_land" and p["timezone"] == "UTC" and p["hourly"] == "precipitation"
    assert (p["start_date"], p["end_date"]) == ("2026-04-24", "2026-09-30")
    assert len(p["latitude"].split(",")) == fr.BATCH
    assert [c[1]["start_date"][:4] for c in stub.calls[:4]] == ["2026", "2026", "2025", "2025"]   # fit seasons first


def test_cap_stops_the_day_and_the_next_day_resumes_to_complete(tmp_path, sites):
    out, w10 = tmp_path / "o", fr.call_weight(10, 160)
    cap = 3 * w10 + 1   # room for three full requests a day
    stub = Stub()
    assert go(out, sites, stub, cap=cap) == fr.OK
    rows = fr.ledger_rows(out)
    assert fr.spent_on(rows, "2026-11-22") <= cap
    n1 = len(stub.calls)
    assert go(out, sites, stub, cap=cap) == fr.OK and len(stub.calls) == n1   # same day: nothing more sent
    for k in range(30):
        go(out, sites, stub, when=(pd.Timestamp(DAY2) + pd.Timedelta(days=k)).to_pydatetime(), cap=cap)
        if (out / "complete.json").exists():
            break
    done = json.loads((out / "complete.json").read_text())
    assert done["cell_seasons"] == 12 * 15 and done["refusals"] == 0
    assert len(stub.calls) == 15 * 2   # 12 cells: two requests a season, none repeated
    for day in {r["day"] for r in fr.ledger_rows(out)}:
        assert fr.spent_on(fr.ledger_rows(out), day) <= cap
    f = pd.read_parquet(fr.cell_file(out, 2012, (50.0, -4.0)))
    assert len(f) == 160 * 24 and f["time"].min() == pd.Timestamp("2012-04-24", tz="UTC")
    assert f["grid_lat"].iloc[0] == pytest.approx(50.02)   # where Open-Meteo took it from, kept


@pytest.mark.parametrize("status", [429, 403, 401])
def test_a_refusal_stops_at_once_and_for_the_rest_of_the_day(tmp_path, sites, status):
    out = tmp_path / "o"
    stub = Stub([200, status])
    assert go(out, sites, stub) == fr.REFUSED
    rows = fr.ledger_rows(out)
    assert [r["outcome"] for r in rows] == ["ok", "refused"] and len(stub.calls) == 2
    assert go(out, sites, stub) == fr.REFUSED and len(stub.calls) == 2   # no request sent again today
    assert go(out, sites, stub, when=DAY2) == fr.OK   # the next UTC day carries on


def test_a_limit_reason_in_a_400_is_a_refusal_and_another_400_is_a_fault(tmp_path, sites):
    limit = fr.Answer(400, json.dumps({"error": True, "reason": "Daily API request limit exceeded"}).encode())
    assert go(tmp_path / "a", sites, Stub([lambda p: limit])) == fr.REFUSED
    assert go(tmp_path / "b", sites, Stub([400])) == fr.FAILED
    assert fr.ledger_rows(tmp_path / "b")[-1]["outcome"] == "failed"


def test_a_5xx_is_tried_twice_more_and_every_try_counts(tmp_path, sites):
    out, sleeps = tmp_path / "o", []
    assert go(out, sites, Stub([503, None, 200]), cap=fr.call_weight(10, 160) * 3 + 1, sleeps=sleeps) == fr.OK
    rows = fr.ledger_rows(out)
    assert [r["outcome"] for r in rows] == ["retry", "retry", "ok"]
    assert 30.0 in sleeps and 90.0 in sleeps
    assert fr.spent_on(rows, "2026-11-22") == pytest.approx(3 * fr.call_weight(10, 160), abs=0.01)


def test_three_failed_tries_stop_the_run(tmp_path, sites):
    out = tmp_path / "o"
    assert go(out, sites, Stub([502, 502, 502])) == fr.FAILED
    assert [r["outcome"] for r in fr.ledger_rows(out)] == ["retry", "retry", "failed"]
    assert not (out / "rain").exists()


def test_a_short_answer_is_never_saved_as_whole(tmp_path, sites):
    out = tmp_path / "o"
    assert go(out, sites, Stub([lambda p: fr.Answer(200, body_for(p, hours=100))])) == fr.FAILED
    assert fr.ledger_rows(out)[-1]["outcome"] == "bad_answer"
    assert not list((out / "rain").rglob("*.parquet")) if (out / "rain").exists() else True


def test_pace_between_requests(tmp_path, sites):
    sleeps, stub = [], Stub()
    go(tmp_path / "o", sites, stub, cap=fr.call_weight(10, 160) * 3 + 1, sleeps=sleeps)
    assert len(stub.calls) == 4 and sleeps == [fr.PACE_S] * 3   # 10 + 2 cells a season, two seasons; a pause between


def test_ledger_line_has_what_the_protocol_names(tmp_path, sites):
    out = tmp_path / "o"
    go(out, sites, Stub(), cap=fr.call_weight(10, 160) + 1)
    r = fr.ledger_rows(out)[0]
    assert {"at", "day", "season", "cells", "first_cell", "weight", "attempt", "status", "bytes", "sha256",
            "outcome"} <= set(r)
