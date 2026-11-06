"""scripts/lake_own_rate_test.py (docs/LAKE-OWN-RATE-TEST-2026-11.md): the shrinkage rule, the committed inputs and
the recorded verdict. The point estimates do not depend on the bootstrap, so a short run reproduces them."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lake_own_rate_test as m  # noqa: E402

SCORES = ROOT / "docs" / "LAKE-OWN-RATE-TEST-2026-11-scores.json"


def test_shrinkage_rule():
    g = np.array([0.02, 0.02, 0.02])
    p = m.shrink(np.array([0, 0, 20]), np.array([0, 10, 100]), g, m.M)
    assert p[0] == 0.02                      # no own samples: the generic forecast
    assert np.isclose(p[1], 0.01)            # ten own samples weigh the same as the generic
    assert abs(p[2] - 0.2) < 0.02            # a hundred own samples: nearly the own rate


def test_the_committed_rows_and_history_are_as_the_record_says():
    rows = m.load_rows()
    assert len(rows) == 637 and rows["bw_id"].nunique() == 12 and rows["catchment"].nunique() == 6
    assert rows["cluster"].nunique() == 18 and int(rows["over900"].sum()) == 16 and int(rows["over500"].sum()) == 30
    hist = m.load_history(set(rows["bw_id"]))
    assert len(hist) == 832 and set(hist["year"]) == {2023, 2024, 2025, 2026}
    ref = m.references(rows, hist, "loyo", 900)
    assert ref["n"].min() == 40 and ref["n"].max() == 61
    fwd = m.references(rows, hist, "fwd", 900)
    assert (fwd.loc[rows["year"] == 2024, "n"] <= 21).all()   # 2024 sees 2023 only
    assert fwd.loc[rows["year"] == 2026, "n"].median() > fwd.loc[rows["year"] == 2025, "n"].median()


def test_the_recorded_scores_come_from_these_inputs_and_match_a_rerun(monkeypatch, tmp_path):
    rec = json.loads(SCORES.read_text())
    assert rec["verdict"] == "fail" and rec["m"] == 10 and rec["skill_margin"] == 0.10
    assert all(not v for k, v in rec["checks"].items() if k[0] in "12G" and "G2" not in k)
    assert rec["checks"]["3 not worse than the plain own rate (point estimate)"]
    for rel, h in rec["inputs_sha256"].items():
        assert m.sha(ROOT / rel) == h, rel
    monkeypatch.setattr(m, "DRAWS", 20)
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "t")])
    m.main()
    got = json.loads((tmp_path / "t-scores.json").read_text())
    for s in m.SCHEMES:
        for line in ("900", "500"):
            a, b = got["schemes"][s]["line"][line], rec["schemes"][s]["line"][line]
            assert a["brier"] == b["brier"] and a["auc"] == b["auc"] and a["events"] == b["events"], (s, line)
    assert got["verdict"] == rec["verdict"]
    rows = pd.read_csv(tmp_path / "t-rows.csv")
    assert len(rows) == 637 and {"candidate", "production", "usual", "own", "last"} <= set(rows)
