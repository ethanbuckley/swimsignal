"""The regional routing shadow (src/dipcast/shadow_regional.py, docs/REGIONAL-ROUTING-2026-11.md): routing, the off
switch, inputs left alone, and the rows it logs."""

import numpy as np
import pandas as pd

from dipcast import shadow_regional as sr
from dipcast.model.features import ALL_FEATURES

TZ = "Europe/London"


class Fixed:
    def __init__(self, p):
        self.p = p

    def predict(self, df):
        return np.full(len(df), self.p)


def _case():
    days = pd.date_range("2026-11-05", periods=3, freq="D", tz=TZ)
    ov = pd.DataFrame({"site_id": ["A1", "U1", "W1"],
                       "company": ["Anglian Water", "United Utilities", "Dwr Cymru Welsh Water"]})
    rows = []
    for sid in ov["site_id"]:
        for d in days:
            # rain_d is itself a model input, so it is set after the others are blanked
            rows.append({"site_id": sid, "day": d, **{f: np.nan for f in ALL_FEATURES},
                         "rain_d": np.nan if (sid == "A1" and d == days[2]) else 1.0})
    sd = pd.DataFrame(rows)
    sd["ok"] = sd["rain_d"].notna()
    p_raw = np.array([[0.1, 0.1, np.nan], [0.3, 0.3, 0.3], [0.5, 0.5, 0.5]])
    return days, ov, sd, p_raw


def test_eight_companies_take_v2_others_keep_production_and_missing_rain_stays_missing():
    days, ov, sd, p_raw = _case()
    out = sr.routed(sd, ov, days, p_raw, model=Fixed(0.9))
    assert out["v2"].tolist() == [True, False, False]
    assert np.allclose(out["p"][0, :2], 0.9) and np.isnan(out["p"][0, 2])
    assert np.array_equal(out["p"][1:], p_raw[1:])


def test_inputs_are_not_altered():
    days, ov, sd, p_raw = _case()
    sd0, ov0, p0 = sd.copy(), ov.copy(), p_raw.copy()
    sr.routed(sd, ov, days, p_raw, model=Fixed(0.9))
    pd.testing.assert_frame_equal(sd, sd0)
    pd.testing.assert_frame_equal(ov, ov0)
    assert np.array_equal(p_raw, p0, equal_nan=True)


def test_off_without_the_frozen_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "V2_FILE", tmp_path / "missing.pkl")
    sr.clear_cache()
    assert sr.v2_model() is None
    days, ov, sd, p_raw = _case()
    assert sr.routed(sd, ov, days, p_raw) is None
    (tmp_path / "other.pkl").write_bytes(b"another model")
    monkeypatch.setattr(sr, "V2_FILE", tmp_path / "other.pkl")
    sr.clear_cache()
    assert sr.v2_model() is None
    sr.clear_cache()


def test_the_committed_file_is_the_frozen_model():
    sr.clear_cache()
    assert sr.v2_model() is not None


def test_logs_leads_from_zero_in_its_own_table(tmp_path):
    import duckdb
    days, ov, sd, p_raw = _case()
    days = days.insert(0, days[0] - pd.Timedelta(days=1))          # a past day, as the forecast's grid has
    p_raw = np.concatenate([np.full((3, 1), 0.2), p_raw], axis=1)
    sd_past = sd[sd["day"] == sd["day"].min()].assign(day=days[0])
    out = sr.routed(pd.concat([sd_past, sd]), ov, days, p_raw, model=Fixed(0.9))
    issued = pd.Timestamp("2026-11-05 09:00", tz="UTC")
    db = tmp_path / "state.duckdb"
    n = sr.log_shadow(issued, 54.0, -2.0, days, ov, p_raw, p_raw * 0.5, out, "spill=abc", path=db)
    assert n == 9                                                   # 3 overflows x leads 0-2; the past day not logged
    con = duckdb.connect(str(db))
    t = con.execute(f"SELECT * FROM {sr.TABLE} ORDER BY site_id, lead").df()
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    con.close()
    assert sr.TABLE in tables and con is not None
    assert t["lead"].tolist() == [0, 1, 2] * 3
    a = t[t["site_id"] == "A1"]
    assert a["route"].unique().tolist() == ["v2_offsets"] and a["p_regional"].isna().tolist() == [False, False, True]
    u = t[t["site_id"] == "U1"]
    assert (u["route"] == "production").all() and np.allclose(u["p_regional"], u["p_raw"])
    assert np.allclose(u["p_cal"], u["p_raw"] * 0.5)
    assert set(t["rule"]) == {"regional-v1"} and set(t["v2_sha"]) == {sr.V2_SHA256[:16]}


def test_the_pre_window_check_reads_the_table(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import regional_shadow_check as chk
    days, ov, sd, p_raw = _case()
    out = sr.routed(sd, ov, days, p_raw, model=Fixed(0.9))
    db = tmp_path / "state.duckdb"
    sr.log_shadow(pd.Timestamp("2026-11-05 09:00", tz="UTC"), 54.0, -2.0, days, ov, p_raw, p_raw, out, "v", path=db)
    import duckdb
    con = duckdb.connect(str(db))
    rows = con.execute(f"SELECT * FROM {sr.TABLE}").df()
    con.close()
    assert chk.check(rows) == []
    assert chk.window(rows)[1:] == ("2026-11-06", "2026-12-03")
    bad = rows.copy()
    bad.loc[bad["route"] == "production", "p_regional"] = 0.99
    assert any("differ from production" in e for e in chk.check(bad))
