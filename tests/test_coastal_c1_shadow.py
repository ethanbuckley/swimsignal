"""docs/COASTAL-C1-SHADOW-2027.md: C1 at issue time, logged once a day per English beach, May to September. Made-up
rain and samples only; a scratch state database."""

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from dipcast import coastal_c1_shadow as sh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "coastal_c1"))
import c1  # noqa: E402

SITE, PT = "ukc1101-06000", [54.66467, -1.18604]
NOW = pd.Timestamp("2027-07-14T07:30:00+01:00")


def cache(tmp, a, b, mm, now=NOW, hours=96, issued="2027-07-14T05:00:00+00:00"):
    noon = now.tz_convert("Europe/London").normalize() + pd.Timedelta(hours=12)
    t = pd.date_range(noon - pd.Timedelta(hours=hours - 1), noon, freq="h").tz_convert("UTC")
    pd.DataFrame({"cell_lat": a, "cell_lon": b, "time": t, "precip_mm": mm, "air_c": 15.0,
                  "issued_at": pd.Timestamp(issued)}).to_parquet(tmp / f"forecast_{a:.3f}_{b:.3f}.parquet")


def snap(sample=None):
    return {"sites": [{"id": SITE, "sample": sample or {"state": "none"}}]}


def test_the_figures_are_c1s_own_code_on_the_frozen_file():
    doc = sh.frozen()
    assert doc is not None
    tab, mods = doc["site_tables"]["over_500"], doc["models"]["over_500"]
    s = tab["sites"][SITE]
    rate = np.array([(s["k"] + tab["m"] * tab["p0"]) / (s["n"] + tab["m"])])
    month, last = np.array([7]), np.array([[np.log10(140) - 1, 0.0]])
    rain = np.array([[6.0, 20.0]])
    f = sh.figures(doc, SITE, 7, 140.0, 6.0, 20.0)
    assert f["p_c1"] == pytest.approx(c1.predict(mods["C1"], c1.design(rate, month, last, rain))[0])
    assert f["p_c0"] == pytest.approx(c1.predict(mods["C0"], c1.design(rate, month, last, None))[0])
    assert f["p_r"] == pytest.approx(c1.predict(mods["R"], c1.design(rate, month, None, None))[0])
    unknown = sh.figures(doc, "not-a-site", 7, None, None, None)
    assert unknown["site_rate"] == pytest.approx(tab["p0"]) and unknown["p_c1"] is None


def test_one_row_a_day_from_06_00_in_season_with_the_rain_to_midday(tmp_path):
    doc = sh.frozen()
    cache(tmp_path, 54.7, -1.2, 0.25)
    smp = {"state": "ok", "taken_at": "2027-07-07T10:53:00+01:00", "ecoli": {"value": 140.0, "qualifier": "="}}
    rows = sh.rows_for(snap(smp), {SITE: PT}, NOW, tmp_path, set(), "t", doc)
    r = dict(zip(sh.COLUMNS, rows[0]))
    assert len(rows) == 1 and r["rain_24h"] == pytest.approx(6.0) and r["rain_72h"] == pytest.approx(18.0)
    assert r["rain_km"] == 0.0 and r["last_ecoli"] == 140.0 and r["p_c1"] is not None and r["fallback"] is None
    assert str(r["issue_day"]) == "2027-07-14"
    assert sh.rows_for(snap(), {SITE: PT}, NOW, tmp_path, {SITE}, "t", doc) == [], "already logged today"
    assert sh.rows_for(snap(), {SITE: PT}, pd.Timestamp("2027-07-14T05:30:00+01:00"), tmp_path, set(), "t", doc) == []
    assert sh.rows_for(snap(), {SITE: PT}, pd.Timestamp("2027-10-14T08:00:00+01:00"), tmp_path, set(), "t", doc) == []
    old = {"state": "ok", "taken_at": "2026-09-11T10:53:00+01:00", "ecoli": {"value": 900.0, "qualifier": "="}}
    r_old = dict(zip(sh.COLUMNS, sh.rows_for(snap(old), {SITE: PT}, NOW, tmp_path, set(), "t", doc)[0]))
    assert r_old["last_ecoli"] is None, "last year's sample is not this season's last sample"


def test_no_covered_rain_logs_c0_as_the_fallback(tmp_path):
    doc = sh.frozen()
    cache(tmp_path, 54.7, -1.2, 0.25, hours=30)                                    # 72 h window under 90%
    r = dict(zip(sh.COLUMNS, sh.rows_for(snap(), {SITE: PT}, NOW, tmp_path, set(), "t", doc)[0]))
    assert r["p_c1"] is None and r["fallback"] == "C0" and r["p_c0"] is not None
    cache(tmp_path, 54.7, -1.2, 0.25, issued="2027-07-12T05:00:00+00:00")         # too old by its own fetch time
    assert dict(zip(sh.COLUMNS, sh.rows_for(snap(), {SITE: PT}, NOW, tmp_path, set(), "t", doc)[0]))["p_c1"] is None
    cache(tmp_path, 54.8, -1.2, 0.1)                                               # a neighbour square instead
    r = dict(zip(sh.COLUMNS, sh.rows_for(snap(), {SITE: PT}, NOW, tmp_path, set(), "t", doc)[0]))
    assert r["rain_cell_lat"] == 54.8 and r["rain_km"] > 1 and r["p_c1"] is not None


def test_log_day_writes_once_a_day_to_its_own_table(tmp_path):
    cache(tmp_path, 54.7, -1.2, 0.25)
    db = tmp_path / "state.duckdb"
    a = sh.log_day(snap(), {SITE: PT}, NOW, tmp_path, "t", path=db)
    b = sh.log_day(snap(), {SITE: PT}, NOW + pd.Timedelta(hours=3), tmp_path, "t", path=db)
    assert a["rows"] == 1 and a["with_c1"] == 1 and b["rows"] == 0 and b["already"] == 1
    con = duckdb.connect(str(db))
    assert con.execute(f"SELECT count(*) FROM {sh.TABLE}").fetchone()[0] == 1
    con.close()
    assert sh.log_day(snap(), {SITE: PT}, pd.Timestamp("2026-11-28T08:00:00+00:00"), tmp_path, "t", path=db)["state"] == "out of season"
