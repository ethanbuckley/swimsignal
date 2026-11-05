"""scripts/regional_routing.py: the frozen routing rule (docs/REGIONAL-ROUTING-2026-11.md)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import regional_routing as m  # noqa: E402


class Fixed:
    """A stand-in model that returns one probability for every row and records what it was asked."""

    def __init__(self, p):
        self.p, self.seen = p, []

    def predict(self, df):
        self.seen += list(df["site_id"])
        return np.full(len(df), self.p)


def test_eight_companies_go_to_v2_and_united_utilities_stays():
    df = pd.DataFrame({"company": ["Anglian Water", "United Utilities", "Dwr Cymru Welsh Water", None, "Thames Water"],
                       "site_id": ["a", "u", "w", "n", "t"]})
    v2, prod = Fixed(0.2), Fixed(0.7)
    p, r = m.predict(df, v2, prod)
    assert r.tolist() == ["v2_offsets", "production", "production", "production", "v2_offsets"]
    assert p.tolist() == [0.2, 0.7, 0.7, 0.7, 0.2]
    assert v2.seen == ["a", "t"] and prod.seen == ["u", "w", "n"]


def test_the_rule_names_exactly_the_nine_minus_united_utilities():
    from dipcast.model.training import NINE
    assert set(m.EIGHT) == set(NINE) - {"United Utilities"}


def test_a_wrong_model_file_is_refused(tmp_path):
    f = tmp_path / "x.pkl"
    f.write_bytes(b"not the model")
    with pytest.raises(SystemExit):
        m.check_v2(f)
