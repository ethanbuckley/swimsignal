"""The lake E. coli range (docs/LAKE-RANGE-HINDCAST-TEST-2026-11.md, docs/LAKE-RANGE-WORDING-2026-11.md): at every
lake spot a forecast computes, the reading a sample would most likely show each day and the range 8 in 10 samples
would fall in, from the frozen rule `lake-range-v1`. The forecast gives it on each day (`ecoli_range`, shown on the
spot's page) and logs it in its own table, `shadow_lake_range_v1`, in the state database, for the 2027 read.

lake-range-v1 is the candidate PR #584 tested on 2012-2022 lake seasons: a censored normal model of log10 E. coli with
its own lake noise level and a random intercept per bathing water (scripts/lake_range_hindcast.py `export`, fitted on
the 2023-26 rows). Its `basis`, which the page words: "tested", a lake bathing water in that test (its own level);
"own samples", a lake bathing water with its own level from 2023-26 but not in the test; "average lake", any other
lake, at the average lake's level. It reads the same inputs as the spot's E. coli figure (ecoli.features: rain at
the spot, the exposure, season), so it costs no request.

It sets no level, colour or alert. Without the model file, or with a file of another hash, it is off and the page
says "Not estimated", as before.

Each in-season day at a lake bathing water with its own samples also carries `usual` and `direction`
(docs/LAKE-RANGE-DIRECTION-PROPOSAL-2026-11.md): usual is lake-range-v1's likely reading for the same lake on the same
date with the lake's typical inputs (USUAL_FILE: the median rain over 48 h and 24 h and the median exposure on its own
2023-26 sample days, scripts/lake_range_usual.py); direction is "higher" at twice usual or more, "lower" at half or
less, else "about", on the figures as published. Not at "average lake" spots, not out of season, not without the file.
Neither is logged: the shadow table is unchanged.
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
# The lake bathing waters in the 2012-2022 test (#584): Windermere x4 and Frensham Great Pond.
TESTED = frozenset({"ukd1203-45625", "ukd1203-45650", "ukd1203-45675", "ukd1203-45700", "ukj2310-11945"})
SITE_RADIUS_M = 100        # a spot this close to a bathing water's spots.csv position is that bathing water
SEASON = range(5, 10)      # the months the EA samples, and the test's
USUAL_FILE = config.PROCESSED / "lake_range_usual.v1.json"
USUAL_SHA256 = "8be2d127bc168d0dca73fdc6ef3ba53e926a92263aec6349475c8b107fdfb040"
HIGHER, LOWER = 2.0, 0.5   # fixed in the proposal before any 2027 sample
LAB_LIMIT = 10             # the page says "under 10" below it
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


@lru_cache(maxsize=1)
def usual_inputs() -> dict | None:
    """Each lake bathing water's typical inputs, or None (no usual line) when the file is missing, is not the
    committed one, or was made for another model file."""
    if not USUAL_FILE.exists():
        log.info("lake usual line off: %s missing", USUAL_FILE.name)
        return None
    got = hashlib.sha256(USUAL_FILE.read_bytes()).hexdigest()
    if got != USUAL_SHA256:
        log.warning("lake usual line off: %s is %s, not %s", USUAL_FILE.name, got[:12], USUAL_SHA256[:12])
        return None
    u = json.loads(USUAL_FILE.read_text())
    return u if u.get("model_sha256") == SHA256 else None


def clear_cache() -> None:
    model.cache_clear()
    usual_inputs.cache_clear()


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
    """lake-range-v1 for each row of X (ecoli.features' frame, one row a day), or None with the model off. A row with
    a missing input gets NaN, never a range computed as if it were dry. Inputs are not altered."""
    m = m if m is not None else model()
    if m is None or X is None or not len(X):
        return None
    bw = site_for(m, lat, lon)
    ok = np.isfinite(X[m["cols"]].to_numpy(dtype=float)).all(axis=1)
    q = _quantiles(m, X.fillna(0.0), bw)
    nan = lambda a: np.where(ok, a, np.nan)   # noqa: E731
    return {"bw_id": bw, "basis": basis(bw), "low": nan(q[0.1]), "median": nan(q[0.5]), "high": nan(q[0.9]),
            "usual": usual(m, bw, X)}


def usual(m: dict, bw: str | None, X: pd.DataFrame, typical: dict | None = None) -> np.ndarray:
    """The likely reading on each row's date with the lake's typical inputs in place of the day's (the date terms
    are X's own); all NaN at a lake with no typical inputs (no own samples, or the file off)."""
    from dipcast.model.ecoli import features
    typical = typical if typical is not None else usual_inputs()
    t = ((typical or {}).get("sites") or {}).get(bw) if bw is not None else None
    if t is None or not len(X):
        return np.full(len(X), np.nan)
    f = features([t["rain_48h"]], [t["rain_24h"]], [t["risk"]], [1.0], [pd.Timestamp("2026-07-01")])
    Xu = X.copy()
    for c in ("lrain48", "lrain24", "logit_risk", "lake", "lake_x_lrain48"):
        Xu[c] = float(f[c].iloc[0])
    return _quantiles(m, Xu[m["cols"]].fillna(0.0), bw, qs=(0.5,))[0.5]


def direction(today: float | None, usual_: float | None) -> str | None:
    """Higher, lower or about usual, on the figures as published (two significant figures). Both under the lab's
    limit read "under 10" alike, so about usual. None without both figures."""
    if today is None or usual_ is None or not (np.isfinite(today) and np.isfinite(usual_)) or usual_ <= 0:
        return None
    if today < LAB_LIMIT and usual_ < LAB_LIMIT:
        return "about"
    return "higher" if today >= HIGHER * usual_ else "lower" if today <= LOWER * usual_ else "about"


def compared(out: dict, j: int, day) -> dict:
    """`usual` and `direction` for day j's published range, or {}: only in season, at a lake bathing water with its
    own samples, with a range and a usual reading."""
    if out.get("basis") not in ("tested", "own samples") or pd.Timestamp(day).month not in SEASON:
        return {}
    today, u = sig2(out["median"][j]), sig2(out.get("usual", np.full(j + 1, np.nan))[j])
    d = direction(today, u)
    return {} if d is None else {"usual": u, "direction": d}


def basis(bw: str | None) -> str:
    return "average lake" if bw is None else "tested" if bw in TESTED else "own samples"


def sig2(v: float) -> float | None:
    """Two significant figures, as the page gives them; None for a missing value."""
    return None if v is None or not np.isfinite(v) else float(f"{float(v):.2g}")


def log_shadow(issued_at: pd.Timestamp, lat: float, lon: float, days: pd.DatetimeIndex, r48: np.ndarray,
               r24: np.ndarray, risk: np.ndarray, out: dict, version: str | None, path=None) -> int:
    """Append one lake spot's rows (leads 0 and later) to TABLE; returns the rows written."""
    from dipcast.forecast_log import LOCAL_TZ, _LOCK, _conn, append_rows
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
            append_rows(con, TABLE, COLUMNS, rows)
        finally:
            con.close()
    return len(rows)
