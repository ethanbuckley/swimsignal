"""An estimate of a river spot's water temperature, from air temperature, the date and two facts about the river.

The model passed for rivers in docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md: on 3,798 rivers it never saw, in May to
September 2023-25, its typical error (RMSE) was 1.56 C against EA spot samples. Lakes failed and get no estimate; sea
was not judged. So `estimate` answers for a river spot, May to September, and for nothing else.

How it works (all from data/processed/water_temp_model.json, written by
scripts/water_temperature_model_eval/wt_export.py):
  * the day's mean air temperature (London calendar day) at the spot's 0.1 degree rain cell, from the same Open-Meteo
    forecast request as the rain (its past days and today), passed through the test's bridge to the Met Office
    HadUK-Grid air the model was trained on: HadUK = c + d x Open-Meteo;
  * the means over today (a1), the last 7 days (a7) and the last 30 days (a30);
  * a Mohseni curve in a7, plus a boosted-tree correction from a1, a7, a30, the day of the year, the water type,
    the river's network length upstream and the cell's elevation.
The trees are walked here with numpy; the export checked them against scikit-learn to 1e-9.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

MODEL_PATH = config.PROCESSED / "water_temp_model.json"
LOCAL_TZ = "Europe/London"
RIVER_SNAP_M = 250.0          # the test's rule for putting a point on a river (wt_protocol.RIVER_SNAP_M)


def mohseni(a7, mu, alpha, beta, gamma):
    return mu + (alpha - mu) / (1.0 + np.exp(gamma * (beta - np.asarray(a7, dtype=float))))


class WaterTempModel:
    def __init__(self, d: dict):
        self.d = d
        self.features = list(d["features"])
        self.curves = {t: tuple(p) for t, p in d["curves"].items()}
        self.type_code = dict(d["type_code"])
        self.months = set(d["months"])
        self.bridge = (float(d["bridge"]["c"]), float(d["bridge"]["d"]))
        self.within_c = float(d["test"]["shown_within_c"])
        g = d["gbm"]
        self.baseline = float(g["baseline"])
        self.known = np.asarray(g["known_cat_bitsets"], dtype=np.int64).reshape(-1, 8) if g["known_cat_bitsets"] \
            else np.zeros((0, 8), dtype=np.int64)
        self.f_idx_map = np.asarray(g["f_idx_map"], dtype=np.int64)
        self.column_order = [int(c) for c in g.get("column_order", range(len(self.features)))]
        self.categories = {int(c): np.asarray(v, dtype=float) for c, v in (g.get("categories") or {}).items()}
        self.trees = []
        for t in g["trees"]:
            self.trees.append({k: np.asarray(v) for k, v in t.items() if k != "left_cat_bitsets"}
                              | {"left_cat_bitsets": np.asarray(t["left_cat_bitsets"], dtype=np.int64).reshape(-1, 8)})

    def _internal(self, X: np.ndarray) -> np.ndarray:
        """The columns as the trees index them: scikit-learn puts categorical inputs first, each as the position of
        its value among the fit's sorted categories (an unseen value is missing), then the numeric ones."""
        cols = []
        for c in self.column_order:
            x = X[:, c]
            cats = self.categories.get(c)
            if cats is not None:
                code = np.full(len(x), np.nan)
                for k, value in enumerate(cats):
                    code[x == value] = k
                x = code
            cols.append(x)
        return np.column_stack(cols) if cols else X

    @staticmethod
    def _bits(bitsets: np.ndarray, rows: np.ndarray, cats: np.ndarray) -> np.ndarray:
        """Whether category cats[i] is set in bitsets[rows[i]] (8 words of 32 bits, as scikit-learn keeps them)."""
        return ((bitsets[rows, cats // 32] >> (cats % 32)) & 1).astype(bool)

    def correction(self, X: np.ndarray) -> np.ndarray:
        """The boosted trees' sum for each row of X (columns in `features` order), as scikit-learn predicts it:
        a number goes left when <= the threshold; a missing value, or a category the fit never saw, goes where the
        node sends missing values. All rows walk each tree together, one level at a time."""
        X = self._internal(np.atleast_2d(np.asarray(X, dtype=float)))
        out = np.full(len(X), self.baseline)
        rows = np.arange(len(X))
        for t in self.trees:
            node = np.zeros(len(X), dtype=np.int64)
            while True:
                active = ~t["leaf"][node].astype(bool)
                if not active.any():
                    break
                n = node[active]
                f = t["feature"][n].astype(np.int64)
                v = X[rows[active], f]
                miss = t["missing_left"][n].astype(bool)
                go = np.where(np.isnan(v), miss, v <= t["threshold"][n])
                cat = t["categorical"][n].astype(bool)
                if cat.any():
                    vc = v[cat]
                    ok = np.isfinite(vc) & (vc >= 0) & (vc < 256) & (vc == np.floor(np.nan_to_num(vc, nan=-1)))
                    ci = np.where(ok, np.nan_to_num(vc, nan=0), 0).astype(np.int64)
                    fc = f[cat]
                    known = ok & self._bits(self.known, self.f_idx_map[fc], ci) if len(self.known) else ok & False
                    left_cat = self._bits(t["left_cat_bitsets"], t["bitset"][n[cat]].astype(np.int64), ci)
                    go[cat] = np.where(known, left_cat, miss[cat])
                node[active] = np.where(go, t["left"][n], t["right"][n])
            out += t["value"][node]
        return out

    def predict_rows(self, df: pd.DataFrame) -> np.ndarray:
        """Stage 1 (the type's curve in a7) plus the correction, for a frame with `features` and `type`."""
        s1 = np.array([mohseni(a7, *self.curves[t]) if t in self.curves else np.nan
                       for t, a7 in zip(df["type"], df["a7"], strict=True)], dtype=float)
        return s1 + self.correction(df[self.features].to_numpy(float))


def load(path: Path = MODEL_PATH) -> WaterTempModel | None:
    try:
        return WaterTempModel(json.loads(Path(path).read_text()))
    except (OSError, ValueError, KeyError) as e:
        log.warning("water temperature model not loaded (%s): no estimates", e)
        return None


def daily_air(hourly: pd.DataFrame) -> pd.Series:
    """London calendar-day means of `air_c` from hourly UTC rows (`time`); a day counts only when every one of its
    hours (23, 24 or 25) has a value."""
    if hourly is None or hourly.empty or "air_c" not in hourly:
        return pd.Series(dtype=float)
    s = hourly.drop_duplicates("time").set_index("time")["air_c"].astype(float).dropna().sort_index()
    if s.empty:
        return pd.Series(dtype=float)
    local = s.index.tz_convert(LOCAL_TZ)
    out = {}
    for d, v in s.groupby(local.normalize()):
        nxt = (d + pd.Timedelta(hours=36)).normalize()
        if len(v) == int(round((nxt - d).total_seconds() / 3600)):
            out[d.tz_localize(None)] = float(v.mean())
    return pd.Series(out, dtype=float).sort_index()


def upstream_km(net, lon: float, lat: float) -> float | None:
    """The test's catchment size for a point: network length upstream of where the point meets its nearest
    inlandRiver or tidalRiver link within 250 m, in km. None off the network."""
    from shapely.geometry import Point

    from dipcast.network.rivers import lonlat_to_bng
    x, y = lonlat_to_bng(lon, lat)
    rl = net.links[net.links["form"].isin(["inlandRiver", "tidalRiver"])]
    idx = rl.sindex.nearest(Point(x, y), return_all=False, max_distance=RIVER_SNAP_M)
    if idx.shape[1] == 0:
        return None
    row = rl.iloc[int(idx[1, 0])]
    frac = float(row.geometry.project(Point(x, y), normalized=True))
    return (float(net.upstream_m.get(row["start_node"], 0.0)) + frac * float(row["length"])) / 1000.0


def estimate(model: WaterTempModel | None, hourly: pd.DataFrame, today: pd.Timestamp, upstream: float | None,
             elevation: float | None, kind: str = "river") -> dict | None:
    """About how warm a river spot's water is today, or None: not a river, outside May to September, no model, or
    not all 30 days of air. `hourly` is the spot cell's forecast frame (time, air_c); `today` its London date."""
    if model is None or kind != "river" or "river" not in model.curves:
        return None
    today = pd.Timestamp(pd.Timestamp(today).date())
    if today.month not in model.months:
        return None
    day = daily_air(hourly)
    days = pd.date_range(today - pd.Timedelta(days=29), today, freq="D")
    s = day.reindex(days)
    if s.isna().any():
        return None
    c, d = model.bridge
    s = c + d * s
    doy = today.day_of_year
    ang = 2 * np.pi * doy / 365.25
    up = np.log10(upstream) if upstream is not None and upstream > 0 else np.nan
    feats = {"a1": s.iloc[-1], "a7": s.iloc[-7:].mean(), "a30": s.mean(), "doy_sin": np.sin(ang), "doy_cos": np.cos(ang),
             "type_code": model.type_code["river"], "log_lake_area": np.nan, "log_upstream_km": up,
             "elevation": np.nan if elevation is None else float(elevation)}
    row = pd.DataFrame([{**feats, "type": "river"}])
    t = float(model.predict_rows(row)[0])
    if not np.isfinite(t):
        return None
    return {"temp_c": int(round(t)), "within_c": model.within_c, "date": today.date().isoformat()}
