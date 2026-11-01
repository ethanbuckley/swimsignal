"""The lake E. coli range shadow (docs/LAKE-RANGE-HINDCAST-TEST-2026-11.md, docs/LAKE-RANGE-WORDING-2026-11.md): at
every lake spot a forecast computes, the reading a sample would most likely show each day and the range 8 in 10
samples would fall in, from the frozen rule `lake-range-v1`, logged in its own table, `shadow_lake_range_v1`, in the
state database.

lake-range-v1 is the candidate PR #584 tested on 2012-2022 lake seasons: a censored normal model of log10 E. coli with
its own lake noise level and a random intercept per bathing water (scripts/lake_range_hindcast.py `export`, fitted on
the 2023-26 rows). A lake bathing water in the file uses its own intercept weights; any other lake uses the average
lake's ("average lake"). It reads the same inputs as the spot's E. coli figure (ecoli.features: rain at the spot,
the exposure, season), so it costs no request.

Nothing here changes a forecast or a page: no page, alert, level or published score reads the table. Without the
model file, or with a file of another hash, it is off.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.special import logsumexp, ndtr

from dipcast import config

log = logging.getLogger(__name__)

RULE = "lake-range-v1"
TABLE = "shadow_lake_range_v1"
FILE = config.PROCESSED / "ecoli_lake_range.json"
SHA256 = "5566b12e5fc6acc1686f2aeb201ec2b9f8cd7e38a39f4352de314c5e32c3fcca"
SITE_RADIUS_M = 100        # a spot this close to a bathing water's spots.csv position is that bathing water
SEASON = range(5, 10)      # the months the EA samples, and the test's
COLUMNS = ("issued_at", "issue_day", "lat", "lon", "bw_id", "basis", "target_day", "lead", "in_season",
           "rain_48h", "rain_24h", "risk", "median", "low", "high", "rule", "model_sha", "version")


@lru_cache(maxsize=1)
def model() -> dict | None:
    """The frozen model, or None (the shadow is off) when the file is missing or is not the frozen one."""
    if not FILE.exists():
        log.info("lake range shadow off: %s missing", FILE.name)
        return None
    got = hashlib.sha256(FILE.read_bytes()).hexdigest()
    if got != SHA256:
        log.warning("lake range shadow off: %s is %s, not %s", FILE.name, got[:12], SHA256[:12])
        return None
    return json.loads(FILE.read_text())


def clear_cache() -> None:
    model.cache_clear()


def site_for(m: dict, lat: float, lon: float) -> str | None:
    """The bathing water whose spots.csv position is within SITE_RADIUS_M of the spot, or None."""
    best, best_d = None, SITE_RADIUS_M
    for bw, s in m["sites"].items():
        dy = (s["lat"] - lat) * 111_195.0
        dx = (s["lon"] - lon) * 111_195.0 * np.cos(np.radians(lat))
        d = float(np.hypot(dx, dy))
        if d <= best_d:
            best, best_d = bw, d
    return best


def _quantiles(m: dict, X: pd.DataFrame, bw: str | None, qs=(0.1, 0.5, 0.9)) -> dict[float, np.ndarray]:
    """Quantiles of the predictive distribution of E. coli per 100 ml: a mixture over the intercept's nodes, each a
    normal on log10 with the lake noise, solved by bisection on the mixture CDF (as the research script does)."""
    cols = m["cols"]
    Z = np.column_stack([np.ones(len(X))] + [(X[c].to_numpy(dtype=float) - m["mean"][c]) / m["sd"][c] for c in cols])
    mu = Z @ np.asarray(m["beta"])
    logw = np.asarray(m["sites"][bw]["log_weights"] if bw is not None else m["log_prior"])
    w = np.exp(logw - logsumexp(logw))
    u = np.sqrt(2.0) * m["tau"] * np.asarray(m["nodes"])
    s = m["sigma_lake"]
    out = {}
    for q in qs:
        lo, hi = np.full(len(X), -2.0), np.full(len(X), 7.0)
        for _ in range(40):
            mid = (lo + hi) / 2
            below = (w[None, :] * ndtr((mid[:, None] - mu[:, None] - u[None, :]) / s)).sum(1) < q
            lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
        out[q] = 10 ** ((lo + hi) / 2)
    return out


def ranges(lat: float, lon: float, X: pd.DataFrame, m: dict | None = None) -> dict | None:
    """lake-range-v1 for each row of X (ecoli.features' frame, one row a day), or None with the shadow off. A row with
    a missing input gets NaN, never a range computed as if it were dry. Inputs are not altered."""
    m = m if m is not None else model()
    if m is None or X is None or not len(X):
        return None
    bw = site_for(m, lat, lon)
    ok = np.isfinite(X[m["cols"]].to_numpy(dtype=float)).all(axis=1)
    q = _quantiles(m, X.fillna(0.0), bw)
    nan = lambda a: np.where(ok, a, np.nan)   # noqa: E731
    return {"bw_id": bw, "basis": "site" if bw else "average lake",
            "low": nan(q[0.1]), "median": nan(q[0.5]), "high": nan(q[0.9])}


def log_shadow(issued_at: pd.Timestamp, lat: float, lon: float, days: pd.DatetimeIndex, r48: np.ndarray,
               r24: np.ndarray, risk: np.ndarray, out: dict, version: str | None, path=None) -> int:
    """Append one lake spot's rows (leads 0 and later) to TABLE; returns the rows written."""
    from dipcast.forecast_log import LOCAL_TZ, _LOCK, _conn
    issue_day = issued_at.tz_convert(LOCAL_TZ).date()

    def _f(x):
        return None if x is None or not np.isfinite(x) else float(x)
    rows = []
    for j, d in enumerate(days):
        lead = (d.date() - issue_day).days
        if lead < 0:
            continue
        rows.append((issued_at, issue_day, lat, lon, out["bw_id"], out["basis"], d.date(), lead, d.month in SEASON,
                     _f(r48[j]), _f(r24[j]), _f(risk[j]), _f(out["median"][j]), _f(out["low"][j]), _f(out["high"][j]),
                     RULE, SHA256[:16], version))
    if not rows:
        return 0
    with _LOCK:
        con = _conn(path)
        try:
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    issued_at TIMESTAMPTZ, issue_day DATE, lat DOUBLE, lon DOUBLE, bw_id VARCHAR, basis VARCHAR,
                    target_day DATE, lead INTEGER, in_season BOOLEAN, rain_48h DOUBLE, rain_24h DOUBLE, risk DOUBLE,
                    median DOUBLE, low DOUBLE, high DOUBLE, rule VARCHAR, model_sha VARCHAR, version VARCHAR)""")
            con.executemany(f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})", rows)
        finally:
            con.close()
    return len(rows)
