"""The pre-registered 2027 evaluation (docs/PREREGISTRATION-2027.md): scripts/evaluate_2027.py on a
small made-up fixture whose figures are worked out here by other means, the frozen files against
the hashes the protocol records, and the code's bands, warning lines and matching rules against the
values the protocol registered."""

import hashlib
import itertools
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "eval2027"
PROTOCOL = ROOT / "docs" / "PREREGISTRATION-2027.md"
JUNE = (date(2027, 6, 1), date(2027, 6, 2))
FROZEN = {"spill": "s1", "cal": "c1", "ecoli": "e1", "rain": "open-meteo-forecast"}


def _script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    return __import__(name)


E = _script("evaluate_2027")


def _sites():
    return E.read_published(FIX / "sites.csv", dtype=str, keep_default_na=False)


def _clim():
    return json.loads((FIX / "climatology.json").read_text())


def _pairs_auc(y, p):
    """AUC by counting every (event, non-event) pair: 1 if the event's forecast is higher, 0.5 if equal."""
    pos = [pi for yi, pi in zip(y, p, strict=True) if yi]
    neg = [pi for yi, pi in zip(y, p, strict=True) if not yi]
    return sum(1.0 if a > b else 0.5 if a == b else 0.0 for a, b in itertools.product(pos, neg)) / (len(pos) * len(neg))


# The fixture's eight scored rows in the window and the list: (lead, p, observed, climatology column).
ROWS = [(0, 0.80, 1, 0.05), (1, 0.40, 1, 0.05), (0, 0.10, 0, 0.05),   # A
        (0, 0.15, 0, 0.60), (0, 0.70, 0, 0.10),                        # B
        (0, 0.10, 0, 0.02), (0, 0.39, 1, 0.02), (1, 0.05, 0, 0.02)]    # C


def _stratum(res, name):
    return next(s for s in res["strata"] if s["stratum"] == name)


# ------------------------------------------------------------------ spill forecasts

def test_spill_scores_on_the_fixture_match_a_hand_count():
    res = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=50, seed=1)
    assert res["rows_read"] == 11 and res["rows_in_window"] == 9   # 31 May and lead 5 fall outside
    assert res["rows_outside_list"] == 1 and res["outside_list_overflows"] == 1   # Z
    lead, p, y, c = (np.array(x, dtype=float) for x in zip(*ROWS, strict=True))
    season = np.clip(c * 2.0, 0.001, 0.95)   # June's factor in the fixture is 2; B's 1.2 is capped
    for name, m in (("all leads", np.ones(8, bool)), ("same day (lead 0)", lead == 0), ("in advance (leads 1-4)", lead >= 1)):
        s = _stratum(res, name)
        assert s["n"] == m.sum() and s["events"] == y[m].sum()
        assert s["brier"] == pytest.approx(np.mean((p[m] - y[m]) ** 2))
        assert s["skill_season_site"] == pytest.approx(1 - np.mean((p[m] - y[m]) ** 2) / np.mean((season[m] - y[m]) ** 2))
        assert s["skill_site_rate"] == pytest.approx(1 - np.mean((p[m] - y[m]) ** 2) / np.mean((c[m] - y[m]) ** 2))
        assert s["auc"] == pytest.approx(_pairs_auc(y[m], p[m]))
    s = _stratum(res, "all leads")
    # A value on a cut is in the band above: 0.15 moderate, 0.40 high, 0.70 very high; 0.39 moderate.
    assert [r["n"] for r in s["reliability"]] == [3, 2, 1, 2]
    assert s["reliability"][1]["observed"] == pytest.approx(0.5)     # 0.15 (dry) and 0.39 (spilled)
    w = s["warning"]
    assert (w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (2, 1, 1, 4)
    assert w["n"] == s["n"] == 8                                      # the same rows as the Brier score
    assert w["share_correct"] == pytest.approx(6 / 8) and w["always_no_correct"] == pytest.approx(5 / 8)


def test_every_eligible_overflow_day_is_a_cell_scored_or_not():
    res = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=10, seed=1)
    cov = res["coverage"]
    assert cov["eligible_overflows"] == 4 and cov["days"] == 2
    overall, *by_lead = cov["overall_and_by_lead"]
    assert (overall["cells"], overall["scored"], overall["not_scored"]) == (40, 8, 32)   # 4 x 2 days x 5 leads
    assert [(r["lead"], r["cells"], r["scored"]) for r in by_lead] == [(0, 8, 6), (1, 8, 2), (2, 8, 0), (3, 8, 0), (4, 8, 0)]
    assert {r["company"]: (r["cells"], r["scored"]) for r in cov["by_company"]} == {"Co1": (20, 5), "Co2": (20, 3)}
    assert {r["water"]: (r["cells"], r["scored"]) for r in cov["by_water"]} == {"lake": (10, 2), "river": (30, 6)}
    assert cov["unscored_by_reason"] is None


def test_the_unscored_file_gives_reasons_for_eligible_season_rows_only(tmp_path):
    u = tmp_path / "unscored.csv"
    u.write_text("# notes\noverflow_id,day,lead,reason\nD,2027-06-01,0,max_gap\nD,2027-06-02,0,max_gap\n"
                 "A,2027-06-02,1,missed_deadline\nZ,2027-06-01,0,max_gap\nD,2027-05-01,0,max_gap\n")
    res = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=10, seed=1, unscored=u)
    assert res["coverage"]["unscored_by_reason"] == {"max_gap": 2, "missed_deadline": 1}


def test_only_the_frozen_models_rows_are_scored_when_stamps_are_published():
    res = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=10, seed=1, model=FROZEN)
    v = res["versions"]
    assert v["checked"] and v["left_out"] == 1                          # B on 2 June, spill=s2
    assert v["rows_by_label"]["frozen model"] == 7
    assert _stratum(res, "all leads")["n"] == 7
    # A published file with no version column: nothing can be told apart, and the output says so.
    plain = pd.read_csv(FIX / "spills.csv", comment="#").drop(columns="version")
    _, info = E.split_versions(plain, FROZEN, None, None)
    assert info == {"checked": False, "why": "no version column in the published file"}


def test_a_repeated_row_stops_the_evaluation(tmp_path):
    text = (FIX / "spills.csv").read_text()
    row = next(x for x in text.splitlines() if x.startswith("A,Co1,2027-06-01,0,"))
    (tmp_path / "s.csv").write_text(text + row + "\n")
    with pytest.raises(SystemExit, match="repeated"):
        E.evaluate_spills(tmp_path / "s.csv", _sites(), _clim(), *JUNE, resamples=10, seed=1)


def test_the_bootstrap_is_fixed_by_its_seed_and_brackets_the_estimate():
    a = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=200, seed=7)
    b = E.evaluate_spills(FIX / "spills.csv", _sites(), _clim(), *JUNE, resamples=200, seed=7)
    assert E.clean(a["strata"]) == E.clean(b["strata"])   # NaN (an undefined AUC) never equals itself
    s = _stratum(a, "all leads")
    assert s["ci"]["brier"]["lo"] <= s["brier"] <= s["ci"]["brier"]["hi"]
    assert a["bootstrap"] == {"sites": 3, "blocks": 1, "resamples": 200, "seed": 7}   # A, B, C; 1-2 June is one block


def test_two_way_weights_multiply_site_and_block_draws():
    boot = E.Bootstrap(np.array(["a", "a", "b"]), np.array([0, 1, 1]), resamples=1, seed=0)
    s, b = boot.draws[0]
    assert np.array_equal(boot.weights(0, np.arange(3)), np.array([s[0] * b[0], s[0] * b[1], s[1] * b[1]], dtype=float))


def test_blocks_are_seven_days_from_the_first_of_may():
    days = pd.Series([date(2027, 5, 1), date(2027, 5, 7), date(2027, 5, 8), date(2027, 9, 30), date(2027, 4, 30)])
    assert list(E.block_of(days)) == [0, 0, 1, 21, -1]


# ------------------------------------------------------------------ the E. coli estimate

def test_ecoli_pairs_samples_and_the_river_warning_table():
    res = E.evaluate_ecoli(FIX / "ecoli.csv", _sites(), _clim(), date(2027, 6, 1), date(2027, 6, 30), resamples=50, seed=1)
    assert res["samples_outside_list"] == 1                 # X9
    assert res["pairs_issued_after_sample"] == 1            # R1's 8 June lead 0, issued at 11:00 for a 10:00 sample
    cov = res["coverage"]
    assert cov["samples"] == 5 and cov["samples_over_900"] == 2   # 900 itself is not over 900
    assert {r["water"]: (r["samples"], r["cells"], r["scored"], r["samples_with_no_forecast"]) for r in cov["by_water"]} == {
        "river": (4, 20, 4, 1), "lake": (1, 5, 1, 0)}
    w = res["warning_rivers"]   # one row per sample, its latest forecast: R1 1 Jun 0.30 (over), R1 8 Jun 0.05, R2 1 Jun 0.25
    assert (w["hits"], w["misses"], w["false_alarms"], w["quiet_correct"]) == (1, 0, 1, 1)
    assert w["samples"] == 4 and w["samples_with_no_forecast"] == 1 and w["too_few_to_judge"]
    s = _stratum(res, "river: same day (lead 0)")
    y, p, ref = np.array([1, 0]), np.array([0.30, 0.25]), np.array([0.3, 0.2])   # R2 has no site rate: the river rate
    assert s["brier"] == pytest.approx(np.mean((p - y) ** 2))
    assert s["skill_season_site"] == pytest.approx(1 - np.mean((p - y) ** 2) / np.mean((ref - y) ** 2))
    assert s["auc"] == pytest.approx(1.0) and s["group"] == "primary"
    assert _stratum(res, "lake: same day (lead 0)")["group"] == "water"


def test_an_observed_column_that_disagrees_with_the_count_stops_the_evaluation(tmp_path):
    text = (FIX / "ecoli.csv").read_text().replace("R2,river,2027-06-01T09:00+01:00,2027-06-01,900,0", "R2,river,2027-06-01T09:00+01:00,2027-06-01,900,1")
    (tmp_path / "e.csv").write_text(text)
    with pytest.raises(SystemExit, match="disagrees"):
        E.evaluate_ecoli(tmp_path / "e.csv", _sites(), _clim(), date(2027, 6, 1), date(2027, 6, 30), resamples=10, seed=1)


def test_a_run_with_changed_settings_says_it_is_not_the_registered_one(tmp_path, capsys):
    out = tmp_path / "r.json"
    E.main(["--spills", str(FIX / "spills.csv"), "--ecoli", str(FIX / "ecoli.csv"), "--sites", str(FIX / "sites.csv"),
            "--climatology", str(FIX / "climatology.json"), "--from", "2027-06-01", "--to", "2027-06-30",
            "--resamples", "20", "--out", str(out)])
    res = json.loads(out.read_text())   # strict JSON: an undefined AUC is null, not NaN
    assert res["registered_settings"] is False and res["label"].startswith("NOT the registered analysis")
    assert "Spill forecasts, same day (lead 0)" in capsys.readouterr().out


def test_the_registered_settings_and_frozen_files_give_the_registered_label(tmp_path):
    """The real list and climatology, the default season, draws and seed: the registered analysis.
    The fixture's overflows are not on the real list, so every cell is counted as not scored."""
    out = tmp_path / "r.json"
    E.main(["--spills", str(FIX / "spills.csv"), "--out", str(out)])
    res = json.loads(out.read_text())
    assert res["registered_settings"] is True and res["label"] == "registered analysis"
    assert all(f["as_registered"] for f in res["frozen_files"].values())
    cov = res["spills"]["coverage"]["overall_and_by_lead"][0]
    assert (cov["cells"], cov["scored"]) == (1089 * 153 * 5, 0)
    assert len(res["spills"]["coverage"]["by_block"]) == 22


# ------------------------------------------------------------------ the frozen model and git

def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo, files: dict, msg: str) -> str:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "--short=7", "HEAD")


def test_code_changes_after_the_tag_tell_a_candidate_from_a_deviation(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    config = "RIVER_VELOCITY_MS = 0.5\nT90_HOURS = 30.0   # die-off\nLIVE_FEEDS = {'a': 'https://one'}\n"
    _commit(repo, {"data/processed/spill_model.pkl": "m1", "data/processed/lead_calibration.json": "{}",
                   "data/processed/ecoli_model.json": "{}", "src/dipcast/config.py": config,
                   "src/dipcast/model/transport.py": "x = 1\n", "src/dipcast/forecast_log.py": "y = 1\n"}, "frozen")
    _git(repo, "tag", "eval-2027-model")
    feed = _commit(repo, {"src/dipcast/config.py": config.replace("https://one", "https://two")}, "a feed moved")
    scorer = _commit(repo, {"src/dipcast/forecast_log.py": "y = 2\n"}, "scoring rule")
    physics = _commit(repo, {"src/dipcast/config.py": config.replace("30.0", "24.0").replace("https://one", "https://two")}, "T90")
    model = _commit(repo, {"src/dipcast/model/transport.py": "x = 2\n"}, "model code")
    assert E.code_changes(repo, "eval-2027-model", feed) == {"known": True, "model": [], "watched": []}
    assert E.code_changes(repo, "eval-2027-model", scorer)["watched"] == ["src/dipcast/forecast_log.py"]
    assert E.code_changes(repo, "eval-2027-model", physics)["model"] == ["config.py T90_HOURS"]
    assert E.code_changes(repo, "eval-2027-model", model)["model"] == ["src/dipcast/model/transport.py", "config.py T90_HOURS"]
    assert E.code_changes(repo, "eval-2027-model", "0000000") == {"known": False}
    hashes = E.frozen_hashes(repo, "eval-2027-model")
    assert hashes == {"spill": hashlib.md5(b"m1").hexdigest()[:8], "cal": hashlib.md5(b"{}").hexdigest()[:8],
                      "ecoli": hashlib.md5(b"{}").hexdigest()[:8], "rain": "open-meteo-forecast"}
    stamp = lambda sha, spill=hashes["spill"]: (f"spill={spill};cal={hashes['cal']};ecoli={hashes['ecoli']};"
                                                f"code=0.1.0+{sha};rain=open-meteo-forecast")
    df = pd.DataFrame({"version": [stamp(feed), stamp(scorer), stamp(physics), stamp(model), stamp(feed, "ffffffff"), None]})
    kept, info = E.split_versions(df, hashes, repo, "eval-2027-model")
    assert list(kept.index) == [0, 1] and info["left_out"] == 4


# ------------------------------------------------------------------ what the protocol registered

def test_the_bands_and_warning_lines_are_the_sites_own():
    from dipcast import forecast_log
    from dipcast.model import transport
    rules = (ROOT / "src" / "dipcast" / "site" / "levels.js").read_text()
    cuts = lambda name: tuple(float(x) for x in re.search(rf"{name} = \[([^\]]+)\]", rules).group(1).split(","))
    assert E.SPILL_CUTS == cuts("SPILL_CUTS") and E.ECOLI_CUTS == cuts("ECOLI_CUTS")
    assert transport.LOW_CUT == E.SPILL_CUTS[0]
    edges = [0.1499, 0.15, 0.3999, 0.40, 0.6999, 0.70]
    assert [transport.risk_label(x) for x in edges] == [E.BANDS[i] for i in E.band_index(edges, E.SPILL_CUTS)]
    assert list(E.band_index([0.0999, 0.10, 0.2499, 0.25, 0.4999, 0.50], E.ECOLI_CUTS)) == [0, 1, 1, 2, 2, 3]
    assert (E.SPILL_WARN_AT, E.ECOLI_WARN_AT) == (forecast_log.SPILL_WARN_AT, forecast_log.ECOLI_WARN_AT)
    assert E.SPILL_WARN_AT == E.SPILL_CUTS[1] and E.ECOLI_WARN_AT == E.ECOLI_CUTS[1]   # both the High risk line
    assert "export const HIGH = 2;" in (ROOT / "push" / "src" / "shared.js").read_text()


def test_the_scoring_rules_are_those_the_protocol_registered():
    """The live scorer writes the rows the evaluation reads. These are its rules as registered on
    4 October 2026; changing one before the tag means amending the protocol, and after it is a deviation."""
    import inspect

    from dipcast import forecast_log
    from dipcast.model import forecast
    assert (forecast_log.DECISION_HOUR, forecast_log.MIN_KNOWN_POLLS, forecast_log.MAX_GAP_H) == (8, 6, 8.0)
    assert (E.ECOLI_MIN_SAMPLES, E.ECOLI_MIN_OVER) == (forecast_log.ECOLI_MIN_SAMPLES, forecast_log.ECOLI_MIN_EXCEEDANCES)
    assert forecast_log.LOCAL_TZ == "Europe/London"
    assert set(E.SPILL_COLUMNS) <= set(forecast_log.SCORED_COLUMNS)
    assert 'm["y"] = (m["ecoli"] > 900)' in inspect.getsource(forecast_log.verify_ecoli) and E.ECOLI_THRESHOLD == 900
    assert 'm[m["issued_at"] < m["sample_time"]]' in inspect.getsource(forecast_log.verify_ecoli)
    assert list(forecast.ECOLI_SEASON_MONTHS) == [5, 6, 7, 8, 9]


def test_the_frozen_files_match_the_hashes_in_the_protocol():
    recorded = E.recorded_hashes(PROTOCOL)
    for name in ("scripts/evaluate_2027.py", "scripts/make_eval2027.py", "data/eval2027/sites.csv", "data/eval2027/climatology.json"):
        assert recorded.get(name) == hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name


def test_the_frozen_site_list_reads_whole_and_names_every_inland_bathing_water():
    sites = E.read_published(ROOT / "data" / "eval2027" / "sites.csv", dtype=str, keep_default_na=False)
    assert sites.groupby("unit").size().to_dict() == {"bathing_water": 38, "overflow": 1089}
    assert not sites.duplicated(["unit", "id"]).any() and (sites["company"] != "").all()
    assert sites.loc[sites["id"] == "AWS00056", "company"].item() == "Anglian Water"   # its name holds a '#'
    assert set(sites["water"]) == {"river", "lake", "both"}
    inland = json.loads((ROOT / "data" / "raw" / "bathing_waters_inland.json").read_text())
    assert set(sites.loc[sites["unit"] == "bathing_water", "id"]) == {b["id"] for b in inland}
    clim = json.loads((ROOT / "data" / "eval2027" / "climatology.json").read_text())
    f = clim["spill_month"]["factor"]
    days = clim["spill_month"]["calendar_days"]
    assert sum(f[m] * days[m] for m in f) / sum(days.values()) == pytest.approx(1.0, abs=1e-3)   # averages 1 over the year
    assert set(clim["ecoli_site"]["rate"]) == {b["id"] for b in inland}


# ------------------------------------------------------------------ the maker's rules

def test_the_maker_keeps_live_overflows_once_with_the_kinds_they_reach():
    M = _script("make_eval2027")
    spots = [{"id": "r", "kind": "river"}, {"id": "l", "kind": "lake"}]
    up = {"r": [{"site_id": "X", "has_live": True, "company": "C"}, {"site_id": "Y", "has_live": False, "company": "C"}],
          "l": [{"site_id": "X", "has_live": True, "company": "C"}, {"site_id": "W", "has_live": True, "company": "C"}]}
    out = M.eligible_overflows(spots, up)
    assert out[["id", "water", "spots"]].values.tolist() == [["W", "lake", "l"], ["X", "both", "l;r"]]


def test_the_maker_counts_spill_days_on_local_days_and_smooths_site_rates():
    M = _script("make_eval2027")
    ev = pd.DataFrame({"site_id": ["a", "a", "b"],
                       "event_start": pd.to_datetime(["2025-06-30T23:30:00Z", "2025-06-30T23:45:00Z", "2025-01-10T10:00:00Z"]),
                       "event_end": pd.to_datetime(["2025-07-01T00:30:00Z", "2025-07-01T00:40:00Z", "2025-01-11T10:00:00Z"])})
    sd = M.spill_days_local(ev)   # 23:30 UTC on 30 June is 00:30 on 1 July in London: one day, not two
    assert [str(pd.Timestamp(d).date()) for d in sd.loc[sd["site_id"] == "a", "day"]] == ["2025-07-01"]
    f = M.month_factors(ev, years=(2025,))
    assert f["spill_days"]["7"] == 1 and f["spill_days"]["1"] == 2 and f["factor"]["7"] == pytest.approx((1 / 3) / (31 / 365), abs=1e-4)
    samples = pd.DataFrame({"bw_id": ["s"] * 3, "sample_time": pd.to_datetime(["2025-06-01T10:00Z"] * 3), "ecoli": [100, 901, 900]})
    rates = M.ecoli_site_rates(samples, pd.DataFrame({"id": ["s", "t"]}), years=(2025, 2025))["rate"]
    assert rates == {"s": {"n": 3, "over_900": 1, "rate": round(1.5 / 4, 4)}, "t": {"n": 0, "over_900": 0, "rate": None}}
