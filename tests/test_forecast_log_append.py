"""append_rows stores exactly what executemany stored: the forecast log's rows must not change with the insert."""
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from dipcast.forecast_log import append_rows

COLUMNS = ("ts", "day", "x", "f", "fs", "s", "b", "n")
SCHEMA = "ts TIMESTAMPTZ, day DATE, x DOUBLE, f FLOAT, fs FLOAT[], s VARCHAR, b BOOLEAN, n INTEGER"


def _rows():
    ns = pd.Timestamp("2026-11-09 21:17:39.139781999", tz="UTC")   # executemany truncates to 39.139781
    return [
        (ns, date(2026, 11, 9), 0.1, 0.1, [0.1, None, round(1 / 3, 5)], "A", True, 0),
        (ns.tz_convert("Europe/London"), date(2026, 11, 10), np.float64(54.25), 1e-9, None, None, False, 4),
        (None, None, None, None, [None, None, None], "", None, None),
    ]


def test_append_rows_matches_executemany():
    con = duckdb.connect()
    for t in ("old", "new"):
        con.execute(f"CREATE TABLE {t} ({SCHEMA})")
    con.executemany(f"INSERT INTO old ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})", _rows())
    append_rows(con, "new", COLUMNS, _rows())
    exact = "epoch_ns(ts), day, x, f::VARCHAR, fs::VARCHAR, s, b, n"
    old = con.execute(f"SELECT {exact} FROM old").fetchall()
    assert old == con.execute(f"SELECT {exact} FROM new").fetchall()
    assert old[0][0] == old[1][0] == 1794259059139781000


def test_append_rows_by_name_and_empty():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER, b VARCHAR)")
    append_rows(con, "t", ("b", "a"), [("x", 1)])
    append_rows(con, "t", ("b", "a"), [])
    assert con.execute("SELECT a, b FROM t").fetchall() == [(1, "x")]
