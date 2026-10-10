"""scripts/check_ecoli_wales.py (Wales plan, task W10) on a tiny made-up fixture: reading NRW's
archive layout from a zip, the '<' and '>' rules, the station screen, the sampling-day bootstrap and
the verdict. No real NRW rows are kept in the repository."""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_ecoli_wales as cw

COLUMNS = ["station_number", "station_name", "station_type", "easting", "northing", "ngr", "local_authority",
           "sampling_datetime", "sampling_reason", "reason_group", "sampling_medium", "sampling_mechanism",
           "parameter_shortname", "parameter_name", "sample_value", "coded_value", "unit_name", "unit_symbol",
           "sign", "method_name", "deviating_result"]
RIVER, ANY = "RIVER / RUNNING SURFACE WATER", "ANY WATER"


def _row(sid, name, when, value, sign="---", stype="FRESHWATER - UNSPECIFIED", medium=RIVER, param=cw.PARAM,
         deviating=""):
    return [sid, name, stype, "300000", "250000", "", "", when, "", "", medium, "SPOT", "", param, value, "",
            "number per 100 millitres", "NO/100ml", sign, "", deviating]


FIXTURE = [
    _row("S1", "AFON TEST @ BRIDGE", "2025-06-03 11:20:00", "120"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-06-10 12:05:00", "10", sign="<"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-06-17 10:40:00", "100000", sign=">"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-06-24 10:40:00", "1e+006"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-07-01 10:40:00", "1100", sign="<"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-07-08 10:40:00", "500", sign=">"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-07-15 10:40:00", "300", deviating="Yes"),
    _row("S1", "AFON TEST @ BRIDGE", "2025-07-22 10:40:00", "300", param="Coliforms, Total : Presumptive : MF"),
    _row("S2", "AFON TEST U/S TESTTOWN STW OUTFALL", "2025-06-03 11:50:00", "950"),
    _row("S3", "SSO+TEST STREAM OUTFALL", "2025-06-03 12:00:00", "5000"),
    _row("S4", "TEST BAY PIPE DISCHARGE", "2025-06-03 12:00:00", "5000"),
    _row("S5", "TEST WORKS FINAL EFFLUENT", "2025-06-03 12:00:00", "5000",
         stype="SEWAGE DISCHARGES - FINAL/TREATED EFFLUENT - WATER COMPANY", medium=ANY),
    _row("S6", "TEST CANAL", "2025-06-03 12:00:00", "200", stype="FRESHWATER - CANALS - NON CLASSIFIED"),
    _row("S7", "TEST PILL", "2025-06-03 12:00:00", "200", medium="ESTUARINE WATER"),
    _row("S8", "AFON HEN @ FORD", "2012-06-03 12:00:00", "200", medium=ANY),
]


@pytest.fixture
def archive(tmp_path):
    csv = tmp_path / "Test_2020_01_01_to_2029_12_31_Water_Quality_Archive.csv"
    pd.DataFrame(FIXTURE, columns=COLUMNS).to_csv(csv, index=False)
    z = tmp_path / "Test_2020_01_01_to_2029_12_31_Water_Quality_Archive.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(csv, csv.name)
    csv.unlink()
    return z


def test_read_wqa_keeps_ecoli_rows_from_zip(archive):
    d = cw.read_wqa([archive])
    assert len(d) == len(FIXTURE) - 1                 # the coliform row is not E. coli
    assert d["value"].iloc[3] == 1_000_000            # "1e+006" parses
    assert str(d["time"].dt.tz) == cw.TZ


@pytest.mark.parametrize("sign,value,want", [
    ("---", 900, 0.0), ("---", 901, 1.0), ("---", 120, 0.0),
    ("<", 10, 0.0), ("<", 901, 0.0), ("<", 1100, np.nan),
    (">", 100000, 1.0), (">", 900, 1.0), (">", 500, np.nan),
    ("---", np.nan, np.nan),
])
def test_exceeds_sign_rule(sign, value, want):
    got = cw.exceeds(sign, value)
    assert (np.isnan(got) and np.isnan(want)) or got == want


def test_log_count_sign_rule():
    assert cw.log_count("<", 10) == pytest.approx(np.log10(5))
    assert cw.log_count(">", 100000) == pytest.approx(5.0)
    assert cw.log_count("---", 0) == 0.0
    # '<10' ranks below every plain count of 10 or more; '>100000' above 100000
    assert cw.log_count("<", 10) < cw.log_count("---", 10) < cw.log_count(">", 100000)


def test_screen_rules(archive):
    s, why = cw.screen(cw.read_wqa([archive]))
    assert set(s["station_number"]) == {"S1", "S2"}    # river points only; U/S an outfall is river water
    assert why["before_2023"] == 1
    assert why["lab_flagged"] == 1
    assert why["not_river_water"] == 5                 # SSO outfall, pipe, effluent, canal, estuary
    s1 = s[s["station_number"] == "S1"].sort_values("time")
    assert s1["y"].tolist()[:4] == [0.0, 0.0, 1.0, 1.0]
    assert np.isnan(s1["y"].iloc[4]) and np.isnan(s1["y"].iloc[5])   # '<1100' and '>500' unknown
    assert s["lat"].between(51, 53).all() and s["lon"].between(-4, -3).all()


def test_river_hint():
    assert cw.river_hint("R WYE @ ABERNANT") == "River Wye"
    assert cw.river_hint("Tywi Swing Bridge BW") == "River Tywi"
    assert cw.river_hint("TOWY DRYSLWYN ROAD BRIDGE") == "River Tywi"
    assert cw.river_hint("BRYNMILL STREAM") is None


def test_day_draws_resample_whole_days():
    days = np.array(["a", "a", "a", "b", "c", "c"])
    for idx in cw.day_draws(days, n_boot=50, seed=1):
        drawn = pd.Series(days[idx]).value_counts()
        assert all(drawn[d] % (days == d).sum() == 0 for d in drawn.index)   # whole days only


def _scored(n_days=30, per_day=3, seed=0, signal=True):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        wet = rng.random() < 0.3
        for k in range(per_day):
            rain = rng.gamma(2, 6) if wet else rng.gamma(1, 1)
            y = float(rng.random() < (0.7 if (wet and signal) else 0.1))
            rows.append({"station_number": f"S{k}", "station_name": f"S{k}", "day": pd.Timestamp("2025-05-01") + pd.Timedelta(days=d),
                         "y": y, "value": 2000.0 if y else 100.0, "log_ecoli": 3.3 if y else 2.0,
                         "rain_48h": rain, "exposure": rain / 50, "climatology": 0.2, "flat": 0.25,
                         "rain_only_model": min(0.9, 0.05 + rain / 40),
                         "ecoli_estimate": min(0.95, 0.05 + rain / 30), "upstream_overflows": 3})
    return pd.DataFrame(rows)


def test_score_and_verdict():
    s = cw.score(_scored(), n_boot=200)
    assert s["samples"] == 90 and s["sampling_days"] == 30
    est = s["predictors"]["ecoli_estimate"]
    assert est["auc"] > 0.7 and est["auc_ci"][0] <= est["auc"] <= est["auc_ci"][1]
    assert "bss_vs_climatology" in est and "brier" not in s["predictors"]["exposure"]
    v = cw.verdict(s)
    assert v["verdict"] in {"SKILL", "NO SKILL SHOWN"}
    small = cw.score(_scored(n_days=10), n_boot=50)
    assert cw.verdict(small)["verdict"] == "CANNOT CONCLUDE"


def test_weighted_calls():
    assert cw.weighted_calls(pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-14")) == 1
    assert cw.weighted_calls(pd.Timestamp("2026-04-01"), pd.Timestamp("2026-09-30")) == 14
