"""scripts/ensemble_rain_check.py: the stated questions and pass rules (docs/ENSEMBLE-RAIN-TEST-2026-11.md),
on synthetic rows, and the join of the scored rows to the forecast log's members."""

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ensemble_rain_check import check, load_rows, partial_spearman, spearman

COMPANIES = ["Anglian Water", "Yorkshire Water", "Wessex Water"]


def frame(unit_rows, seed=1):
    """Rows as load_rows gives them, from (company, day, lead, p, y, m0, m1, m2) per unit of 30 rows."""
    out = []
    for c, day, lead, p, y, m in unit_rows:
        n = len(y)
        out.append(pd.DataFrame({"overflow_id": [f"{c[:3]}{i}" for i in range(n)], "company": c, "day": day, "lead": lead,
                                 "forecast_calibrated": p, "p_db": p, "observed": y, "rain_mm": 2.0,
                                 "m0": m[0], "m1": m[1], "m2": m[2], "r0": 1.0, "r1": 2.0, "r2": 3.0}))
    return pd.concat(out, ignore_index=True)


def units_where(spread_of, seed=0, days=40, n=30, p_of=lambda rng: 0.05):
    """40 days x 3 companies x 3 leads = 360 units of `n` rows. Each unit's spills are drawn at random;
    the members are the headline plus and minus a shift `spread_of(rng, error, n, p)` per row."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(days):
        day = (pd.Timestamp("2026-10-25") + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
        for c in COMPANIES:
            for lead in (2, 3, 4):
                p0 = p_of(rng)
                y = (rng.random(n) < rng.choice([0.0, p0, 4 * p0])).astype(int)
                p = np.full(n, p0)
                err = abs(y.sum() - p.sum())
                delta = spread_of(rng, err, n, p0)
                rows.append((c, day, lead, p, y, (p, np.clip(p + delta, 0, 1), np.clip(p - delta, 0, 1))))
    return frame(rows)


def test_spearman_and_partial():
    a = np.arange(10.0)
    assert spearman(a, a) == pytest.approx(1.0)
    assert spearman(a, -a) == pytest.approx(-1.0)
    rng = np.random.default_rng(3)
    v = rng.random(500)
    a, b = v + 0.01 * rng.random(500), v + 0.01 * rng.random(500)
    assert spearman(a, b) > 0.9                      # both follow v
    assert abs(partial_spearman(a, b, v)) < 0.15     # and nothing else


def test_members_that_know_the_errors_pass_question_1():
    rows = units_where(lambda rng, err, n, p: err / n)
    res = check(rows, n_boot=200)
    assert res["sane"] and res["enough"]
    q1 = res["question1"]
    assert q1["units"] == 360
    assert q1["S1"] and q1["S2"]
    assert res["band"].startswith("stays")


def test_members_that_say_nothing_fail_question_1():
    rows = units_where(lambda rng, err, n, p: rng.random() * 0.05)
    res = check(rows, n_boot=200)
    assert not res["question1"]["S2"]
    assert res["band"] == "comes off the page"


def test_a_spread_that_only_follows_the_size_of_the_forecast_fails_S2():
    # The headline varies by unit; the members' spread is the error the headline itself expects, and no more.
    rows = units_where(lambda rng, err, n, p: 2 * p * (1 - p) * (1 + 0.01 * rng.random()), p_of=lambda rng: rng.uniform(0.01, 0.3))
    q1 = check(rows, n_boot=200)["question1"]
    assert q1["rho"] > 0.2                           # wet units: bigger errors and bigger spreads
    assert not q1["S2"]


def test_a_mean_nearer_what_happened_switches_the_headline():
    rows = units_where(lambda rng, err, n, p: 0.0)
    y = rows["observed"].to_numpy()
    rows = rows.assign(m1=np.where(y == 1, 0.5, 0.0), m2=np.where(y == 1, 0.5, 0.0))
    q2 = check(rows, n_boot=200)["question2"]
    assert q2["brier_mean"] < q2["brier_p"]
    assert q2["M1"] and q2["M2"] and q2["M3"]


def test_a_worse_mean_keeps_the_single_forecast():
    rows = units_where(lambda rng, err, n, p: 0.0)
    y = rows["observed"].to_numpy()
    rows = rows.assign(m1=np.where(y == 1, 0.0, 0.6), m2=np.where(y == 1, 0.0, 0.6))
    res = check(rows, n_boot=200)
    assert not res["question2"]["M1"]
    assert res["headline"] == "stays on the single forecast"


def test_too_little_data_or_a_log_that_disagrees_cannot_pass():
    rows = units_where(lambda rng, err, n, p: err / n, days=5)
    few = check(rows, n_boot=50)
    assert not few["enough"] and few["band"].startswith("too little data")
    rows = units_where(lambda rng, err, n, p: err / n)
    bad = check(rows.assign(p_db=rows["forecast_calibrated"] + 0.01), n_boot=50)
    assert not bad["sane"] and bad["band"].startswith("stopped")
    missing = rows.copy()
    missing.loc[missing.index[: len(missing) // 4], ["m0", "m1", "m2"]] = np.nan   # members on 75% of rows
    assert not check(missing, n_boot=50)["sane"]


def test_load_rows_takes_the_forecast_issued_by_eight(tmp_path):
    db = tmp_path / "log.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""CREATE TABLE forecast_overflows (issued_at TIMESTAMPTZ, issue_day DATE, lat DOUBLE, lon DOUBLE,
        site_id VARCHAR, has_live BOOLEAN, target_day DATE, lead INTEGER, p_raw DOUBLE, p_cal DOUBLE, weight DOUBLE,
        rain_available BOOLEAN, version VARCHAR, rain_mm DOUBLE, travel_h DOUBLE, p_cal_members FLOAT[], rain_members FLOAT[])""")
    rows = [  # 07:10 and 09:30 BST on 25 Oct for 28 Oct (lead 3); the 07:10 one is the decision forecast
        ("2026-10-25 06:10:00+00", 0.20, [0.1, 0.2, 0.3]),
        ("2026-10-25 08:30:00+00", 0.40, [0.9, 0.9, 0.9]),
    ]
    for t, p, m in rows:
        con.execute("INSERT INTO forecast_overflows VALUES (?, '2026-10-25', 54.0, -2.0, 'UU1', TRUE, '2026-10-28', 3, ?, ?, 1.0, TRUE, 'v', 4.0, 1.0, ?, ?)",
                    [t, p, p, m, [3.0, 4.0, 5.0]])
    con.execute("INSERT INTO forecast_overflows VALUES ('2026-10-25 06:00:00+00', '2026-10-25', 54.0, -2.0, 'UU2', TRUE, '2026-10-28', 3, 0.1, 0.1, 1.0, TRUE, 'v', 4.0, 1.0, NULL, NULL)")
    con.close()
    scored = pd.DataFrame({"overflow_id": ["UU1", "UU2"], "company": "United Utilities", "day": "2026-10-28", "lead": 3,
                           "issued_at": "2026-10-25T07:10+01:00", "forecast_raw": [0.2, 0.1], "forecast_calibrated": [0.2, 0.1],
                           "climatology": 0.05, "observed": [1, 0]})
    got = load_rows(str(db), scored, "2026-10-25", "2026-11-21").set_index("overflow_id")
    assert got.loc["UU1", "p_db"] == pytest.approx(0.2)
    assert got.loc["UU1", ["m0", "m1", "m2"]].tolist() == pytest.approx([0.1, 0.2, 0.3])
    assert got.loc["UU1", ["r0", "r1", "r2"]].tolist() == pytest.approx([3.0, 4.0, 5.0])
    assert np.isnan(got.loc["UU2", "m0"])            # logged without members: kept, with none
