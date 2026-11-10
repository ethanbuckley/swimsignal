"""The Accuracy page's two simple rules (docs/SIMPLE-REFERENCES-LIVE-2026-11.md): the moved status and rain code gives
the interim read's answers, each rule's chance reads only what was known at the issue, the 10 mm line is strict, and
the aggregated bootstrap is the 2027 pre-registration's."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_2027 as E  # noqa: E402
import interim_usefulness as IU  # noqa: E402

from dipcast import simple_references as sr  # noqa: E402

UTC = "UTC"


def _polls_world(seed: int = 3, n_sites: int = 6, days: int = 6):
    """Random live history, coverage bits and poll log for a few overflows of two companies, and issue times."""
    rng = np.random.default_rng(seed)
    first = date(2026, 10, 10)
    sites = [f"S{i}" for i in range(n_sites)]
    company = {s: "A" if i % 2 else "B" for i, s in enumerate(sites)}
    t0 = pd.Timestamp(first, tz="Europe/London").tz_convert(UTC)
    # Polls: each company polled at irregular times, with one long gap to exercise the 8 h rule.
    polls = []
    for c in ("A", "B"):
        t = t0
        while t < t0 + pd.Timedelta(days=days):
            t += pd.Timedelta(minutes=int(rng.integers(20, 200 if rng.random() > 0.05 else 700)))
            polls.append({"fetched_at": t, "company": c, "n_rows": 1, "n_known": 1, "feed_age_h": 0.1})
    polls = pd.DataFrame(polls)
    # Coverage: most slots current, some not.
    cov = []
    for s in sites:
        for k in range(-1, days + 1):
            bits = 0
            for b in range(48):
                if rng.random() > 0.15:
                    bits |= 1 << b
            cov.append({"site_id": s, "day": first + timedelta(days=k), "n_known": 40, "n_unknown": 0, "n_stale": 0, "slots": bits})
    cov = pd.DataFrame(cov)
    # History: a few spills per site, seen by polls.
    hist = []
    for s in sites:
        for _ in range(int(rng.integers(0, 5))):
            st = t0 + pd.Timedelta(minutes=int(rng.integers(0, days * 1440)))
            en = st + pd.Timedelta(minutes=int(rng.integers(10, 1500)))
            seen = st + pd.Timedelta(minutes=int(rng.integers(0, 120)))
            hist.append({"site_id": s, "company": company[s], "fetched_at": seen, "status": int(seen < en),
                         "latest_event_start": st, "latest_event_end": pd.NaT if seen < en else en})
            hist.append({"site_id": s, "company": company[s], "fetched_at": en + pd.Timedelta(minutes=30), "status": 0,
                         "latest_event_start": st, "latest_event_end": en})
        hist.append({"site_id": s, "company": company[s], "fetched_at": t0, "status": 0,
                     "latest_event_start": pd.NaT, "latest_event_end": pd.NaT})
    hist = pd.DataFrame(hist)
    issued = [t0 + pd.Timedelta(days=d, hours=6, minutes=int(rng.integers(0, 120))) for d in range(1, days)]
    rows = pd.DataFrame([{"site_id": s, "issued_ms": int(t.value // 1_000_000)} for s in sites for t in issued])
    return rows, hist, cov, polls


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_status_matches_the_interim_read(seed):
    rows, hist, cov, polls = _polls_world(seed)
    a = sr.persistence_status(rows, hist, cov, polls)
    b = IU.persistence_status(rows, hist, cov, polls)
    assert (a["known"].to_numpy() == b["known"].to_numpy()).all()
    assert (a["active"].to_numpy() == b["active"].to_numpy()).all()
    assert (a["spilling_now"].to_numpy() == b["spilling_now"].to_numpy()).all()
    assert a["known"].any() and (~a["known"]).any() and a["active"].any()


def test_rain_matches_the_interim_read():
    rng = np.random.default_rng(7)
    log, rows = [], []
    for s in ("X", "Y"):
        for d in range(10):
            issue_day = pd.Timestamp("2026-10-01") + pd.Timedelta(days=d)
            for h in (2, 7, 15):
                ms = int(pd.Timestamp(issue_day, tz="Europe/London").tz_convert(UTC).value // 1_000_000) + h * 3_600_000
                for lead in range(6):
                    rain = None if rng.random() < 0.1 else float(rng.gamma(1, 4))
                    log.append({"site_id": s, "issued_ms": ms, "target_day": issue_day + pd.Timedelta(days=lead), "rain_mm": rain})
                    if h == 7 and lead <= 4 and d > 0:
                        rows.append({"site_id": s, "issued_ms": ms, "target_day": issue_day + pd.Timedelta(days=lead),
                                     "lead": lead, "rain_mm": rain})
    log, rows = pd.DataFrame(log), pd.DataFrame(rows)
    a = sr.rain_48h(rows, log).to_numpy()
    b = IU.rain_48h(rows, log).to_numpy()
    assert np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])
    assert (~np.isnan(a)).sum() > 20


def test_ten_mm_is_dry_and_missing_is_not_wet():
    assert sr.is_wet(np.array([9.9, 10.0, 10.01, np.nan])).tolist() == [False, False, True, False]


def test_chances_read_only_days_before_the_issue():
    # 30 days of rows at lead 1, one side. Every target day before 20 Oct is dry; from 20 Oct every day spills.
    days = pd.date_range("2026-10-01", "2026-10-30")
    tday = np.repeat(days.date, 10)
    y = (pd.to_datetime(tday) >= pd.Timestamp("2026-10-20")).astype(float)
    iday = pd.to_datetime(tday) - pd.Timedelta(days=1)
    p = sr.trailing_chances(iday, tday, np.ones(len(y), int), np.ones(len(y), bool), y, np.ones(len(y), bool),
                            fit_days=28, min_rows=100)
    # Issue day 20 Oct (target 21 Oct): the window is target days 22 Sep to 19 Oct, all dry, 190 rows.
    i = np.flatnonzero(pd.to_datetime(tday) == pd.Timestamp("2026-10-21"))[0]
    assert p[i] == pytest.approx(0.5 / 191)
    # Issue day 22 Oct: target days 20 and 21 Oct spilled (20 rows) of 210.
    i = np.flatnonzero(pd.to_datetime(tday) == pd.Timestamp("2026-10-23"))[0]
    assert p[i] == pytest.approx(20.5 / 211)
    # Under 100 fitting rows: issue days up to 10 Oct have at most 90 earlier rows.
    early = pd.to_datetime(iday) <= pd.Timestamp("2026-10-10")
    assert np.isnan(p[early]).all() and not np.isnan(p[~early]).any()


def test_chances_keep_leads_and_sides_apart_and_skip_rows_the_rule_cannot_judge():
    n = 400
    tday = np.repeat(pd.date_range("2026-10-01", periods=40).date, 10)
    iday = pd.to_datetime(tday) - pd.Timedelta(days=2)
    lead = np.where(np.arange(n) % 2, 2, 1)
    side = np.arange(n) % 4 < 2
    y = side.astype(float)                        # the yes side always spills, the no side never
    ok = np.arange(n) % 10 != 0
    p = sr.trailing_chances(iday, tday, lead, side, y, ok, fit_days=28, min_rows=30)
    assert np.isnan(p[~ok]).all()
    have = ~np.isnan(p)
    assert (p[have & side] > 0.9).all() and (p[have & ~side] < 0.1).all()


def test_aggregated_draws_are_the_preregistration_bootstrap():
    rng = np.random.default_rng(11)
    n = 3000
    site = rng.choice([f"o{i}" for i in range(57)], n)
    block = rng.integers(0, 6, n)
    v = rng.random(n)
    rows = np.flatnonzero(rng.random(n) < 0.6)
    d = sr.Draws(site, block, resamples=50, seed=20270501)
    b = E.Bootstrap(site, block, 50, 20270501)
    got = d.sums(rows, v[rows])
    want = np.array([np.dot(b.weights(r, rows), v[rows]) for r in range(50)])
    assert np.allclose(got, want)


def test_verdicts():
    assert sr.verdict({"lo": 0.01, "hi": 0.2}, False) == "beats"
    assert sr.verdict({"lo": -0.3, "hi": -0.01}, False) == "worse"
    assert sr.verdict({"lo": -0.01, "hi": 0.2}, False) == "unclear"
    assert sr.verdict({"lo": None, "hi": None}, False) == "unclear"
    assert sr.verdict({"lo": 0.1, "hi": 0.2}, True) == "too_few"


def test_score_end_to_end_on_a_small_world(monkeypatch):
    rows, hist, cov, polls = _polls_world(5, n_sites=8, days=6)
    rng = np.random.default_rng(5)
    fc, log = [], []
    for _, r in rows.iterrows():
        t = pd.Timestamp(r["issued_ms"], unit="ms", tz=UTC)
        issue_day = t.tz_convert("Europe/London").date()
        for lead in range(5):
            target = issue_day + timedelta(days=lead)
            rain = float(rng.gamma(1, 6))
            log.append({"site_id": r["site_id"], "issued_ms": r["issued_ms"], "target_day": pd.Timestamp(target), "rain_mm": rain})
            fc.append({"site_id": r["site_id"], "company": "Co A" if r["site_id"] in ("S1", "S3") else "Co B",
                       "issue_day": issue_day, "target_day": target, "lead": lead,
                       "issued_at": t.tz_convert("Europe/London"), "p_cal": float(rng.random() * 0.3),
                       "p_clim": 0.05, "y": int(rng.random() < 0.2), "rain_mm": rain})
    fc, log = pd.DataFrame(fc), pd.DataFrame(log)
    out = sr.score(fc, log, hist, cov, polls, resamples=40, first_day=date(2026, 10, 10))
    assert out["scored_rows"] == len(fc)
    # So few rows that no side reaches 100 fitting rows: nothing is common, and nothing is claimed.
    assert out["common_rows"] == 0
    assert all("skill" not in c for c in out["cells"])
    # With the floor lowered, the rules get chances: each cell scores both rules on the same rows.
    monkeypatch.setattr(sr, "MIN_FIT_ROWS", 1)
    out = sr.score(fc, log, hist, cov, polls, resamples=40, first_day=date(2026, 10, 10))
    assert out["common_rows"] > 0
    cell = next(c for c in out["cells"] if c["company"] == sr.ALL and "skill" in c)
    assert set(cell["skill"]) == {"persistence", "rain", "climatology", "best"}
    assert cell["skill"]["best"] == min(cell["skill"][k] for k in ("persistence", "rain", "climatology"))
    assert set(cell["verdict"].values()) <= {"beats", "worse", "unclear", "too_few"}
    assert cell["rows"] <= cell["status_known"] and cell["rows"] <= cell["rain_known"]
    # A company cell with under 20 spills is too few to judge, whatever its interval.
    small = [c for c in out["cells"] if c["company"] != sr.ALL and "skill" in c and c["spill_rows"] < sr.MIN_SPILL_ROWS]
    assert small and all(v == "too_few" for c in small for v in c["verdict"].values())
