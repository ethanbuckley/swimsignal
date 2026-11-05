"""The exploratory buoy check's reader (scripts/lake_temperature_eval/lt_buoy_check.py): the depth is found by its
header label, never by position, and an empty depth column stops the run. On 27 Oct 2026 a column index read
Windermere South's 2 m series as "1 m"; the published 1 m column is empty."""

import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lake_temperature_eval"))
import lt_buoy_check as bc  # noqa: E402

HEAD = "Date GMT,Water temperature,Water temperature,Water temperature,,\ndepth,1m,2m,4m,,\n"


def _zip(tmp_path, rows: str, name="sbas.csv"):
    p = tmp_path / "buoy.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(f"data/{name}", HEAD + rows)
    return (str(p), f"data/{name}", "%d/%m/%Y %H:%M")


def test_the_depth_is_found_by_its_label_and_an_empty_column_stops_the_run(tmp_path):
    rows = "".join(f"01/06/2016 {h:02d}:00,,{12 + h / 100:.2f},{11 + h / 100:.2f},4.4,1.0\n" for h in range(24))
    src = _zip(tmp_path, rows)
    two = bc.read_buoy([src], "2m")
    assert list(two) == [pd.Timestamp("2016-06-01")] and len(two[pd.Timestamp("2016-06-01")]) == 24
    assert two[pd.Timestamp("2016-06-01")][0] == pytest.approx(12.0)          # the 2m column, not the empty 1m
    assert bc.read_buoy([src], "4m")[pd.Timestamp("2016-06-01")][0] == pytest.approx(11.0)
    with pytest.raises(ValueError, match="1m column has no values"):
        bc.read_buoy([src], "1m")
    with pytest.raises(ValueError, match="no 0.5m column"):
        bc.read_buoy([src], "0.5m")


def test_a_day_counts_only_with_enough_hours_and_only_from_may_to_september():
    obs = {pd.Timestamp("2016-06-01"): [10.0] * 18, pd.Timestamp("2016-06-02"): [11.0] * 17,
           pd.Timestamp("2016-04-30"): [9.0] * 24, pd.Timestamp("2016-10-01"): [9.0] * 24}
    s = bc.daily(obs, 2016)
    assert list(s.index) == [pd.Timestamp("2016-06-01")] and s.iloc[0] == 10.0
    assert list(bc.daily(obs, 2016, min_hours=0).index) == [pd.Timestamp("2016-06-01"), pd.Timestamp("2016-06-02")]
