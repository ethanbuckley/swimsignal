"""scripts/hindcast_scotland.py (Scotland plan, task S3) on small made-up fixtures: the label rule,
the sets, the baselines, the rain the run needs and its refusal, the leads fetch's pacing, and
Gate A's verdict. No real Scottish Water row and no network call."""

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hindcast_scotland as hs


def T(s):
    return pd.Timestamp(s, tz="UTC")


@dataclasses.dataclass
class StubModel:
    """predict_pooled = a logistic of the day's rain, shifted by the log long-term average; the
    site offsets as SpillModel fits and applies them (prior 15)."""

    trained_on: str = "stub"
    site_offset: dict = dataclasses.field(default_factory=dict)
    site_n: dict = dataclasses.field(default_factory=dict)

    def predict_pooled(self, df):
        z = 0.4 * (df["rain_d"].to_numpy() - 8) + (df["log_lta_spills"].to_numpy() - np.log1p(20))
        return np.clip(1 / (1 + np.exp(-z)), 1e-4, 1 - 1e-4)

    def fit_site_offsets(self, df):
        t = pd.DataFrame({"s": df["site_id"], "y": df["y"].astype(float), "p": self.predict_pooled(df)}).groupby("s").sum()
        self.site_offset = np.log((t["y"] + 15) / (t["p"] + 15)).to_dict()
        return self

    def predict(self, df):
        p = self.predict_pooled(df)
        z = np.log(p / (1 - p)) + df["site_id"].map(self.site_offset).fillna(0).to_numpy()
        return 1 / (1 + np.exp(-z))


def _ev(rows):
    df = pd.DataFrame(rows, columns=["site_id", "site_name", "event_start", "event_end", "duration_published_h"])
    df["event_start"] = pd.to_datetime(df["event_start"], utc=True, format="mixed")
    df["event_end"] = pd.to_datetime(df["event_end"], utc=True, format="mixed")
    df["duration_h"] = (df["event_end"] - df["event_start"]).dt.total_seconds() / 3600
    df["year"] = df["event_start"].dt.tz_convert("Europe/London").dt.year
    df["lat"], df["lon"], df["source"] = 55.9, -3.2, "test"
    return df


# ---------------------------------------------------------------------------- labels

def test_labels_cut_unknown_duration_day_records_and_repeats():
    ev = _ev([
        ("S", "a", "2025-03-01 10:00", "2025-03-01 10:15:30", None),   # exactly 15 min 30 s: dropped
        ("S", "a", "2025-03-02 10:00", "2025-03-02 10:15:31", None),   # 1 s longer: kept
        ("S", "a", "2025-03-03 23:30", "2025-03-04 01:00", None),      # two days (GMT: UTC is local)
        ("S", "a", "2025-03-03 23:30", "2025-03-04 01:00", None),      # the same event in the other file
        ("S", "a", "2025-06-30 23:00", None, 2.0),                     # day record: local midnight, 1 July BST
        ("S", "a", "2025-01-10 00:00", None, None),                    # day record, unknown duration: kept
        ("S", "a", "2025-01-20 00:00", None, 0.2),                     # day record, 12 min: dropped
    ])
    days = sorted(hs.labels(ev)["day"].dt.strftime("%m-%d"))
    assert days == ["01-10", "03-02", "03-03", "03-04", "07-01"]


def test_published_duration_wins_over_the_computed_one():
    ev = _ev([("S", "a", "2025-03-01 10:00", "2025-03-01 11:00", 0.25)])   # published 15 min: dropped
    assert hs.labels(ev).empty


# ---------------------------------------------------------------------------- sets

def _cov():
    rows = []
    def add(sid, year, spills, uptime=100.0, lat=55.9, lon=-3.2, atype="CSO", emergency=False):
        rows.append({"site_id": sid, "year": year, "status": "events" if spills is not None else "no data",
                     "spills": spills, "spill_hours": None if spills is None else 10.0 * spills,
                     "edm_operational_pct": uptime, "lta_spills": spills, "lta_basis": "uptime90",
                     "lat": lat, "lon": lon, "asset_type": atype, "emergency": emergency, "in_api": atype is not None})
    for sid, lat, lon in (("A", 55.90, -3.20), ("B", 55.91, -3.21), ("C", 55.80, -4.10), ("D", 55.81, -4.11)):
        add(sid, 2024, 20 + len(rows), lat=lat, lon=lon)
        add(sid, 2025, 15 + len(rows), lat=lat, lon=lon, atype="SSSO" if sid == "D" else "CSO")
    add("E", 2024, 5); add("E", 2025, 5, emergency=True)              # emergency by API type
    add("F", 2024, 5); add("F", 2025, 5, uptime=30.0)                # low uptime in the test year
    add("H", 2024, 5, lat=np.nan, lon=np.nan); add("H", 2025, 5, lat=np.nan, lon=np.nan)
    add("K", 2024, None, lat=56.5, lon=-3.0); add("K", 2025, 8, lat=56.5, lon=-3.0, atype=None)
    add("M", 2024, 3, uptime=np.nan); add("M", 2025, 2, uptime=np.nan)   # unknown uptime kept
    df = pd.DataFrame(rows)
    df["spills"] = df["spills"].astype("Int64")
    return df


def test_overflow_years_sets_and_exclusions():
    oy = hs.overflow_years(_cov(), by_name=set(), authority={"A": "City of Edinburgh"})
    s = oy[oy["year"] == 2025].set_index("site_id")
    assert s.loc[["A", "B", "C", "D", "M"], "set"].tolist() == ["G"] * 5
    assert s.loc["K", "set"] == "N"                                    # no count in 2024
    assert s.loc[["E", "F", "H"], "set"].isna().all()                 # emergency, low uptime, no position
    assert s.loc["K", "type"] == "not in the API" and s.loc["D", "type"] == "SSSO"
    assert s.loc["A", "authority"] == "City of Edinburgh" and s.loc["B", "authority"] == "not in the API"
    t24 = oy[oy["year"] == 2024].set_index("site_id")["set"]             # no 2023 count: set N
    assert (t24.loc[["A", "B", "C", "D", "M"]] == "N").all() and pd.isna(t24.loc["K"])
    by_name = hs.overflow_years(_cov(), by_name={"B"}).set_index(["site_id", "year"])
    assert pd.isna(by_name.loc[("B", 2025), "set"])


def test_emergency_by_name():
    ev = _ev([("X", "Main St CSO", "2025-01-01 10:00", "2025-01-01 12:00", None),
              ("Y", "Pumping station EO", "2025-01-01 10:00", "2025-01-01 12:00", None),
              ("Z", "Emergency overflow 2", "2025-01-01 10:00", "2025-01-01 12:00", None),
              ("W", "GEORGE ST", "2025-01-01 10:00", "2025-01-01 12:00", None)])
    assert hs.emergency_by_name(ev) == {"Y", "Z"}


def test_rain_needs_take_the_year_before_from_2021_only():
    rows = pd.DataFrame({"cell_lat": [55.9, 55.9, np.nan], "cell_lon": [-3.2, -3.2, np.nan], "year": [2021, 2025, 2025]})
    assert hs.rain_needs(rows) == {(55.9, -3.2, 2021), (55.9, -3.2, 2025), (55.9, -3.2, 2024)}
    g = rows.assign(year=[2025, 2025, 2025])
    assert hs.lead_needs(g) == {(55.9, -3.2, 2025)}


def test_lead_calls_are_26_a_cell_year():
    assert hs.lead_calls_for({(55.9, -3.2, 2025)}) == pytest.approx(365 / 14)
    assert hs.lead_calls_for({(55.9, -3.2, 2024)}) == pytest.approx(366 / 14)


# ---------------------------------------------------------------------------- baselines

def test_earlier_rates_own_rate_and_month_fallback():
    oy = pd.DataFrame({"site_id": ["A", "A", "B", "A"], "year": [2023, 2024, 2024, 2025],
                       "eligible": [True, True, False, True]})
    lab = pd.DataFrame({"site_id": ["A"] * 4 + ["B"],
                        "day": [T("2023-01-05"), T("2024-01-05"), T("2024-02-01"), T("2025-01-01"), T("2024-01-09")]})
    own, month = hs.earlier_rates(oy, lab, 2025)
    assert own["A"] == pytest.approx(3 / (365 + 366))                 # 2025's own day is not used
    assert "B" not in own.index                                        # B's 2024 is not eligible
    assert month[1] == pytest.approx(2 / 62) and month[2] == pytest.approx(1 / 57)
    sd = pd.DataFrame({"site_id": ["A", "Z"], "day": [T("2025-02-03"), T("2025-02-03")]})
    b = hs.baseline(sd, own, month)
    assert b[0] == pytest.approx(3 / 731) and b[1] == pytest.approx(1 / 57)
    assert hs.baseline(sd.assign(site_id="Z", day=T("2025-03-01")), own, month)[0] == hs.BASE_CLIP[0]


# ---------------------------------------------------------------------------- the run

def _hourly(cells, years, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31 23:00", freq="h", tz="UTC")
    out = []
    for cl, cn in cells:
        wet = rng.random(len(t) // 24 + 1) < 0.3
        p = np.where(np.repeat(wet, 24)[: len(t)], rng.gamma(1.0, 1.0, len(t)), 0.0)
        out.append(pd.DataFrame({"cell_lat": cl, "cell_lon": cn, "time": t, "precip_mm": p}))
    return pd.concat(out, ignore_index=True)


def _write_cache(cache, rain, leads=True):
    d = cache / "rain"
    d.mkdir(parents=True, exist_ok=True)
    for (cl, cn, y), g in rain.groupby([rain.cell_lat, rain.cell_lon, rain.time.dt.year]):
        g.to_parquet(d / f"archive_{hs.cell_key(cl, cn)}_{y}.parquet", index=False)
        if leads and y == 2025:
            parts = [g.assign(lead=k, precip_mm=g.precip_mm * (1 + 0.1 * k)) for k in range(5)]
            pd.concat(parts).to_parquet(d / f"leads_{hs.cell_key(cl, cn)}_{y}.parquet", index=False)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """Overflows of _cov() with discharges drawn from the stub model's own forecasts in 2024 and
    2025, and rain for those years (written to the cache by _write_cache)."""
    monkeypatch.setattr(hs.config, "CACHE", tmp_path / "cache")
    cov = _cov()
    oy = hs.overflow_years(cov, set())
    cells = sorted({(a, b) for a, b in zip(oy.cell_lat, oy.cell_lon, strict=True) if np.isfinite(a)})
    rain = _hourly(cells, [2023, 2024, 2025])
    from dipcast.model.features import daily_rain_features
    daily = daily_rain_features(rain)
    rng = np.random.default_rng(3)
    ev = []
    for y in (2024, 2025):
        s = hs.sites_for(oy.assign(set=np.where(oy.eligible, "G", None)), cov, y, "G")
        sd = hs.hw.build_site_days(s.assign(lta_spills=20.0), daily, pd.date_range(f"{y}-01-01", f"{y}-12-31", tz=hs.TZ))
        sd = sd[sd.rain_d.notna()]
        hit = sd[rng.random(len(sd)) < StubModel().predict_pooled(hs.hw.features(sd))]
        ev.append(pd.DataFrame({"site_id": hit.site_id, "site_name": "x", "event_start": hit.day + pd.Timedelta(hours=6),
                                "event_end": hit.day + pd.Timedelta(hours=8), "duration_published_h": 2.0}))
    ev = _ev(pd.concat(ev).to_numpy().tolist())
    return {"tmp": tmp_path, "cov": cov, "ev": ev, "rain": rain}


def _paths(world):
    t = world["tmp"]
    world["cov"].to_parquet(t / "cov.parquet")
    world["ev"].to_parquet(t / "ev.parquet")
    (t / "api.json").write_text(json.dumps({"results": [{"ASSET_ID": "A", "LOCAL_AUTHORITY_NAME": "Fife"}]}))
    return ["--events", str(t / "ev.parquet"), "--covariates", str(t / "cov.parquet"),
            "--api-answer", str(t / "api.json"), "--cells", str(t / "none.csv"), "--out", str(t / "out.json")]


def test_run_refuses_while_rain_is_missing(world):
    with pytest.raises(SystemExit, match="Not scoring: .* archive cell-years G needs are not cached"):
        hs.main(_paths(world), models={"holdout": StubModel()})
    assert not (world["tmp"] / "out.json").exists()


def test_run_refuses_without_lead_files_unless_told(world, monkeypatch):
    _write_cache(hs.config.CACHE, world["rain"], leads=False)
    with pytest.raises(SystemExit, match="archived-forecast files"):
        hs.main(_paths(world), models={"holdout": StubModel()})
    monkeypatch.setattr(hs, "MIN_SITES", 2)
    monkeypatch.setattr(hs, "MIN_SPILL_DAYS", 10)
    out = hs.main(_paths(world) + ["--without-leads", "--n-boot", "30"], models={"holdout": StubModel()})
    assert out["gate"]["parts"]["G2 lead 1"] == {"tested": False, "why": "--without-leads"}
    assert out["gate"]["verdict"] in ("NOT COMPLETE", "FAIL")


def test_dry_run_counts_and_writes_nothing(world, capsys):
    out = hs.main(_paths(world) + ["--dry-run"], models={"holdout": StubModel()})
    cv = out["coverage"]
    assert cv["overflow_years_by_year"]["2025"]["G"] == 5 and cv["overflow_years_by_year"]["2025"]["N"] == 1
    assert cv["rain_archive"]["G (required)"]["not listed"]["missing"] == 4     # 2 cells x 2024, 2025
    assert cv["rain_leads_2025"]["missing"] == 2 and cv["rain_leads_2025"]["requests_left"] == 1
    assert not (world["tmp"] / "out.json").exists()
    assert '"rain_leads_2025"' in capsys.readouterr().out


def test_full_run_on_the_fixture(world, monkeypatch):
    _write_cache(hs.config.CACHE, world["rain"])
    hs.rain_path("archive", (56.5, -3.0, 2024)).unlink()               # set N's cell-year only
    monkeypatch.setattr(hs, "MIN_SITES", 2)
    monkeypatch.setattr(hs, "MIN_SPILL_DAYS", 10)
    monkeypatch.setattr(hs, "LEAD_MIN_SITES", 2)
    monkeypatch.setattr(hs, "LEAD_MIN_SPILL_DAYS", 10)
    out = hs.main(_paths(world) + ["--n-boot", "30"], models={"holdout": StubModel()})
    g = out["G"]
    assert g["info"]["overflows"] == 5 and g["info"]["calibration"] == "run"
    f = g["scores"]["forecasts"]
    assert {hs.SCOT, hs.CALIB, hs.DEFAULT, hs.EARLIER, hs.FLAT} <= set(f)
    # The events were drawn from the stub's own forecasts, so the Scottish-covariates arm has skill.
    assert f[hs.SCOT]["bss_vs_earlier_years"] > 0.1
    assert set(g["by_type"]) == {"CSO", "SSSO"} and set(g["by_authority"]) == {"Fife", "not in the API"}
    assert out["N"]["not_run"].endswith("cell-years not cached")
    assert set(out["gate"]["parts"]) == {"G1 lead 0", "G2 lead 1", "G3 lead 2", "G4 lead 3"}
    assert all(p["tested"] for p in out["gate"]["parts"].values())
    assert out["gate"]["verdict"] in ("PASS", "FAIL")
    text = (world["tmp"] / "out.json").read_text()
    assert '"site_id"' not in text


def test_calibration_fits_on_earlier_years_only(world, monkeypatch):
    """An overflow that spilled every day before the test year is raised; the test year's own
    labels do not reach its offset."""
    _write_cache(hs.config.CACHE, world["rain"])
    cov = world["cov"]
    oy = hs.overflow_years(cov, set())
    from dipcast.model.features import daily_rain_features
    daily = daily_rain_features(world["rain"])
    lab = pd.DataFrame({"site_id": "A", "day": pd.date_range("2024-01-01", "2024-12-31", tz=hs.TZ)})
    rows = hs.year_rows(oy, cov, lab, daily, 2025, "G", {"holdout": StubModel()}).assign(year=2025)

    p = hs.calibration(oy, cov, lab, daily, rows, StubModel())
    a, b = rows.site_id == "A", rows.site_id == "B"
    assert (p[a] > rows.loc[a, hs.SCOT].to_numpy()).all()             # A spilled every day of 2024
    assert (p[b] <= rows.loc[b, hs.SCOT].to_numpy() + 1e-12).all()    # B never did


# ---------------------------------------------------------------------------- gate

def _g(lo0, leads):
    lk = {str(k): ({"tested": True, "bss_vs_earlier_years": lo + 0.05, "bss_vs_earlier_years_ci": [lo, lo + 0.1],
                    "passes": lo > 0} if lo is not None else {"tested": False, "why": "x"})
          for k, lo in zip((1, 2, 3), leads, strict=True)}
    return {"G": {"info": {"overflows": 250, "spill_days": 50000},
                  "scores": {"forecasts": {hs.SCOT: {"bss_vs_earlier_years": lo0 + 0.05,
                                                     "bss_vs_earlier_years_ci": [lo0, lo0 + 0.1]}}},
                  "leads": lk}}


@pytest.mark.parametrize("lo0, leads, verdict", [
    (0.1, (0.05, 0.02, 0.01), "PASS"),
    (-0.01, (0.05, 0.02, 0.01), "FAIL"),
    (0.1, (0.05, -0.02, 0.01), "FAIL"),
    (0.1, (0.05, None, 0.01), "NOT COMPLETE"),
    (-0.1, (None, None, None), "FAIL"),
])
def test_gate_verdicts(lo0, leads, verdict):
    assert hs.gate(_g(lo0, leads))["verdict"] == verdict


def test_gate_small_set_is_untested():
    r = _g(0.1, (0.05, 0.02, 0.01))
    r["G"]["info"]["overflows"] = 9
    assert hs.gate(r)["verdict"] == "NOT COMPLETE"


def test_gate_a_is_written_in_the_docstring():
    doc = hs.__doc__
    assert "GATE A" in doc and "Written 11 October 2026" in doc
    assert "lower end of the 95% interval of BSS (Scottish\n  covariates against earlier years) is above zero" in doc
    assert "LEAD_MIN_SITES\n  (20)" in doc and "MIN_SITES (10)" in doc


# ---------------------------------------------------------------------------- --fetch-leads

def test_fetch_leads_paced_budget_pace_and_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(hs.config, "CACHE", tmp_path)
    keys = {(55.9, -3.2 - 0.1 * i, 2025) for i in range(5)}
    got, slept, now = [], [], [0.0]

    def fetch(chunk, year):
        got.append(chunk)
        for cl, cn in chunk:
            p = hs.rain_path("leads", (cl, cn, year))
            p.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({"x": [1]}).to_parquet(p)

    done = hs.fetch_leads_paced(keys, max_calls=100, per_hour=3600, fetch=fetch,
                                sleep=lambda s: slept.append(s), clock=lambda: now[0])
    assert [len(c) for c in got] == [2] and done["files"] == 2          # a second request would pass 100 calls
    assert done["stopped"].startswith("budget")
    done = hs.fetch_leads_paced(keys, max_calls=1000, per_hour=3600, fetch=fetch,
                                sleep=lambda s: slept.append(s), clock=lambda: now[0])
    assert done["files"] == 3 and done["stopped"] is None
    assert slept and slept[0] == pytest.approx(2 * 365 / 14)            # spaced by the calls just made

    def refuse(chunk, year):
        raise RuntimeError("HTTP 429")

    left = {(56.5, -3.0, 2025)}
    done = hs.fetch_leads_paced(left, max_calls=1000, per_hour=3600, fetch=refuse, sleep=lambda s: None)
    assert done["stopped"] == "refused: HTTP 429" and done["requests"] == 1


def test_fetch_leads_needs_a_budget(world):
    with pytest.raises(SystemExit, match="--max-calls"):
        hs.main(_paths(world) + ["--fetch-leads"], models={"holdout": StubModel()})
