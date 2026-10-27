"""The rules of docs/WATER-TEMPERATURE-MODEL-TEST-2026-10.md, as plain functions. No network, no files.

Each function here is one rule of the statement. The tests (tests/test_water_temperature_model_eval.py) check them on
synthetic data. wt_fetch.py and wt_score.py call them; they hold no rule of their own.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

import numpy as np
import pandas as pd

# ---- seasons ------------------------------------------------------------------------------------------------------
TRAIN_YEARS = tuple(range(2000, 2023))   # amendment 2 (27 Oct, before any score): was 2018-2022
BRIDGE_YEAR = 2018                       # the Open-Meteo -> HadUK bridge is fitted on this season's air only
OM_YEARS = (BRIDGE_YEAR, 2023, 2024, 2025)
ELEV_DAY = "2018-06-01"                  # one-day requests for the elevation of cells with no other answer
OM_ELEV_CAP = 1_500.0
HADUK_MAX_M = 10_000.0
TEST_YEARS = (2023, 2024, 2025)
MONTHS = (5, 6, 7, 8, 9)                 # rows: 1 May to 30 September, by local date
AIR_FROM, AIR_TO = "04-01", "09-30"      # air: from 1 April, for the 30-day averages of early May
AIR_DAYS = 183                           # 1 April to 30 September inclusive

# ---- water types --------------------------------------------------------------------------------------------------
FRESH_CODES = "2AZZ,2GZZ"
SEA_CODES = "2IZZ,2IAZ,2IBZ,2ICZ"
MATERIAL_TYPE = {                        # the CSV gives the material's label, not its code
    "RIVER / RUNNING SURFACE WATER": "river",            # 2AZZ
    "POND / LAKE / RESERVOIR WATER": "lake",             # 2GZZ
    "SEA WATER": "sea",                                  # 2IZZ
    "SEA WATER AT HIGH TIDE": "sea",                     # 2IAZ
    "SEA WATER AT LOW TIDE": "sea",                      # 2IBZ
    "SEA WATER - INTERTIDAL": "sea",                     # 2ICZ
}
TYPES = ("river", "lake", "sea")
VALUE_MIN, VALUE_MAX = -1.0, 35.0        # the live tile's plausibility range

# ---- groups -------------------------------------------------------------------------------------------------------
RIVER_SNAP_M = 250.0
LAKE_POLY_M = 100.0
LAKE_LINK_M = 250.0
NAMED_DOWNSTREAM_M = 50_000.0
SEA_SQUARE_M = 10_000.0
N_FOLDS = 5

# ---- the verdict --------------------------------------------------------------------------------------------------
RMSE_MAX = {"river": 2.0, "lake": 1.5}
GATE_WATERS, GATE_ROWS = 30, 300
N_BOOT, SEED = 2000, 20261027
SMALL_UPSTREAM_KM, UPLAND_M = 20.0, 200.0

# ---- Open-Meteo ---------------------------------------------------------------------------------------------------
OM_TOTAL_CAP = 20_000.0
OM_DAY_CAP = 9_500.0                     # amended 27 Oct, before any score (was 6,000): Ethan, for speed
OM_HOUR_CAP = 4_700.0                    # rolling hour, under the free tier's 5,000 an hour
OM_BATCH = 25
MIN_TRAIN_SEASONS = 3


# ================================================================== rows
def water_type(material_label: str | None) -> str | None:
    """river, lake or sea from the CSV's sampleMaterialType label; None for anything else (left out)."""
    if not isinstance(material_label, str):
        return None
    return MATERIAL_TYPE.get(material_label.strip().upper())


def parse_result(text) -> float | None:
    """The result as a number, or None: text such as '<0.5' or 'n/a' is not a number and is dropped."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        v = float(text)
        return v if math.isfinite(v) else None
    s = str(text).strip()
    if not s or s[0] in "<>":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def clean_rows(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The archive's rows to one row per point and local date, with counts of everything dropped.

    `raw` has the CSV's columns: id, samplingPoint.notation, samplingPoint.easting, samplingPoint.northing,
    phenomenonTime, sampleMaterialType, result, unit. Returns columns point, date, temp, type, easting, northing,
    n_readings; the point's type is the type most of its kept rows have (a tie goes to river)."""
    counts: dict[str, int] = {"raw": int(len(raw))}
    d = raw.drop_duplicates("id")
    counts["duplicate_id"] = int(len(raw) - len(d))
    d = d.assign(row_type=d["sampleMaterialType"].map(water_type))
    counts["other_material"] = int(d["row_type"].isna().sum())
    d = d[d["row_type"].notna()]
    unit_ok = d["unit"].astype(str).str.strip().str.upper().eq("CELSIUS")
    counts["not_celsius"] = int((~unit_ok).sum())
    d = d[unit_ok]
    v = d["result"].map(parse_result)
    counts["not_a_number"] = int(v.isna().sum())
    d = d.assign(temp=v)[v.notna()]
    rng_ok = d["temp"].between(VALUE_MIN, VALUE_MAX)
    counts["out_of_range"] = int((~rng_ok).sum())
    d = d[rng_ok]
    t = pd.to_datetime(d["phenomenonTime"].astype(str).str.slice(0, 19), errors="coerce")
    counts["bad_time"] = int(t.isna().sum())
    d = d.assign(date=t.dt.normalize())[t.notna()]
    d = d[d["date"].dt.month.isin(MONTHS)]
    pt = (d.groupby(["samplingPoint.notation", "row_type"]).size().unstack(fill_value=0)
          .reindex(columns=list(TYPES), fill_value=0))
    order = {t: i for i, t in enumerate(TYPES)}      # river first, so a tie goes to river
    ptype = pt.apply(lambda r: max(TYPES, key=lambda t: (r[t], -order[t])), axis=1)
    g = d.groupby(["samplingPoint.notation", "date"])
    out = g.agg(temp=("temp", "mean"), n_readings=("temp", "size"),
                easting=("samplingPoint.easting", "first"), northing=("samplingPoint.northing", "first")).reset_index()
    out = out.rename(columns={"samplingPoint.notation": "point"})
    out["type"] = out["point"].map(ptype)
    counts["kept_rows"] = int(len(out))
    counts["days_with_more_than_one_reading"] = int((out["n_readings"] > 1).sum())
    return out, counts


def season_of(date: pd.Series) -> pd.Series:
    """'train' for 2018-2022, 'test' for 2023-2025, None otherwise (May-September only, already filtered)."""
    y = pd.to_datetime(date).dt.year
    return pd.Series(["train" if v in TRAIN_YEARS else ("test" if v in TEST_YEARS else None) for v in y],
                     index=date.index, dtype=object)


# ================================================================== groups and folds
def norm_name(name) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    return " ".join(name.strip().lower().split())


def named_rivers(links: pd.DataFrame) -> dict[str, str]:
    """link id -> river id for every named link. A river is a set of links with the same name (trimmed, case
    ignored) that touch at a node; its id is 'river:<name>:<smallest link id>'. `links` has id, watercourse_name,
    start_node, end_node."""
    named = links.assign(nm=links["watercourse_name"].map(norm_name))
    named = named[named["nm"].notna()]
    parent: dict[str, str] = {i: i for i in named["id"]}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    ends = pd.concat([named[["id", "nm", "start_node"]].rename(columns={"start_node": "node"}),
                      named[["id", "nm", "end_node"]].rename(columns={"end_node": "node"})])
    for _, ids in ends.groupby(["nm", "node"])["id"]:
        ids = list(ids)
        r0 = find(ids[0])
        for other in ids[1:]:
            r1 = find(other)
            if r1 != r0:
                parent[max(r0, r1)] = min(r0, r1)
                r0 = min(r0, r1)
    root = {i: find(i) for i in parent}
    members: dict[str, list[str]] = {}
    for i, r in root.items():
        members.setdefault(r, []).append(i)
    nm = dict(zip(named["id"], named["nm"], strict=True))
    out = {}
    for ids in members.values():
        rid = f"river:{nm[ids[0]]}:{min(ids)}"
        for i in ids:
            out[i] = rid
    return out


def first_named_downstream(graph, start_node: str, river_of: dict[str, str],
                           max_m: float = NAMED_DOWNSTREAM_M) -> str | None:
    """The river id of the nearest named link downstream of `start_node` along the network, within max_m; None if
    there is none. `graph` is a networkx DiGraph whose edges carry 'link' and 'length'. Ties in distance go to the
    smaller link id."""
    import heapq
    best: dict[str, float] = {start_node: 0.0}
    heap = [(0.0, "", start_node)]
    while heap:
        d, _, n = heapq.heappop(heap)
        if d > best.get(n, math.inf):
            continue
        hits = []
        for s in graph.successors(n):
            e = graph.edges[n, s]
            if e.get("link") in river_of:
                hits.append(e["link"])
        if hits:
            return river_of[min(hits)]
        for s in graph.successors(n):
            e = graph.edges[n, s]
            nd = d + float(e.get("length", 0.0))
            if nd <= max_m and nd < best.get(s, math.inf):
                best[s] = nd
                heapq.heappush(heap, (nd, str(e.get("link", "")), s))
    return None


def sea_group(easting: float, northing: float) -> str:
    return f"sea:{int(easting // SEA_SQUARE_M)}_{int(northing // SEA_SQUARE_M)}"


def fold_of(group_id: str, k: int = N_FOLDS) -> int:
    return int(hashlib.sha256(group_id.encode()).hexdigest(), 16) % k


def small_upland(type_: str, upstream_km: float, elevation_m: float) -> bool:
    """A small upland stream: a river point with under 20 km of network upstream and a cell elevation of 200 m or
    more. Unknown upstream length is not small."""
    return (type_ == "river" and upstream_km is not None and np.isfinite(upstream_km)
            and upstream_km < SMALL_UPSTREAM_KM and elevation_m is not None and np.isfinite(elevation_m)
            and elevation_m >= UPLAND_M)


def catchment_band(type_: str, upstream_km: float) -> str | None:
    if type_ != "river":
        return None
    if upstream_km is None or not np.isfinite(upstream_km):
        return "unknown"
    return "under 20 km" if upstream_km < 20 else ("20 to 200 km" if upstream_km < 200 else "200 km and over")


def lake_band(type_: str, area_km2: float) -> str | None:
    if type_ != "lake":
        return None
    if area_km2 is None or not np.isfinite(area_km2):
        return "unmatched"
    return "under 1 km2" if area_km2 < 1 else "1 km2 and over"


# ================================================================== air
def air_features(daily: pd.Series, dates: Iterable) -> pd.DataFrame:
    """a1, a7, a30 for each date from one cell's daily mean air series (index: dates). A date whose 30 days are not
    all present gets NaN in every column."""
    s = daily.sort_index()
    s.index = pd.to_datetime(s.index).normalize()
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D")) if len(s) else s
    r7 = full.rolling(7, min_periods=7).mean()
    r30 = full.rolling(30, min_periods=30).mean()
    ok30 = full.notna().rolling(30, min_periods=30).sum().eq(30)
    rows = []
    for d in pd.to_datetime(list(dates)).normalize():
        if d in full.index and bool(ok30.get(d, False)):
            rows.append((full[d], r7[d], r30[d]))
        else:
            rows.append((np.nan, np.nan, np.nan))
    return pd.DataFrame(rows, columns=["a1", "a7", "a30"])


def om_weight(n_cells: int, days: int = AIR_DAYS, variables: int = 1) -> float:
    """Open-Meteo's weight for one request (rainfall.call_weight's rule, copied so the harness runs without src)."""
    v = variables / 10
    return n_cells * max(1.0, v, v * days / 14)


def plan_open_meteo_narrowed(cells_by_year: dict[int, list[str]], all_cells: Iterable[str]) -> dict:
    """Amendment 2: the bridge season and the test seasons, each for the cells with a row that year; and one-day
    elevation requests for every other cell. {"seasons": {year: [cells]}, "elevation_cells": [...], "weight"}."""
    seasons = {y: sorted(set(cells_by_year.get(y, []))) for y in OM_YEARS if cells_by_year.get(y)}
    have = set().union(*seasons.values()) if seasons else set()
    elev = sorted(set(all_cells) - have)
    weight = sum(om_weight(len(c)) for c in seasons.values()) + om_weight(len(elev), days=1)
    return {"seasons": seasons, "elevation_cells": elev, "weight": round(weight, 3),
            "elevation_weight": om_weight(len(elev), days=1), "over_cap": weight > OM_TOTAL_CAP
            or om_weight(len(elev), days=1) > OM_ELEV_CAP}


def fit_bridge(om, hk) -> tuple[float, float]:
    """The bridge: HadUK = c + d x OpenMeteo, least squares on paired daily values (no water temperature)."""
    om = np.asarray(om, float)
    hk = np.asarray(hk, float)
    ok = np.isfinite(om) & np.isfinite(hk)
    d, c = np.polyfit(om[ok], hk[ok], 1)
    return float(c), float(d)


def nearest_valid_cell(cx: np.ndarray, cy: np.ndarray, px, py, max_m: float = HADUK_MAX_M) -> tuple:
    """For points (px, py), the index of the nearest valid grid-cell centre (cx, cy: centres of the cells that have
    values) within max_m, or -1; and the distance. The cell a point falls in is its nearest centre, so a point in a
    valid cell gets that cell."""
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([cx, cy]))
    d, i = tree.query(np.column_stack([np.asarray(px, float), np.asarray(py, float)]), k=1)
    i = np.where(d <= max_m, i, -1)
    return i, d


def plan_open_meteo(cells_by_season: dict[int, list[str]], train_years=TRAIN_YEARS, cap: float = OM_TOTAL_CAP,
                    sea_cells: set[str] | None = None) -> dict:
    """Which cell-seasons to ask for. Over the cap: drop training seasons oldest first, keeping at least three; then
    sea-only cells. Returns {"seasons": {year: [cells]}, "weight": total, "dropped": [notes]}."""
    plan = {y: sorted(set(c)) for y, c in cells_by_season.items()}
    dropped: list[str] = []

    def total(p):
        return sum(om_weight(len(c)) for c in p.values())

    train = sorted(y for y in plan if y in train_years)
    while total(plan) > cap and len([y for y in plan if y in train_years]) > MIN_TRAIN_SEASONS:
        y = train.pop(0)
        dropped.append(f"training season {y}")
        del plan[y]
    if total(plan) > cap and sea_cells:
        plan = {y: [c for c in cs if c not in sea_cells] for y, cs in plan.items()}
        dropped.append("sea-only cells")
    return {"seasons": plan, "weight": round(total(plan), 3), "over_cap": total(plan) > cap, "dropped": dropped}


# ================================================================== models
FEATURES = ["a1", "a7", "a30", "doy_sin", "doy_cos", "type_code", "log_lake_area", "log_upstream_km", "elevation"]
TYPE_CODE = {"river": 0, "lake": 1, "sea": 2}
MOHSENI_P0 = (0.0, 25.0, 13.0, 0.2)                      # mu, alpha, beta, gamma
MOHSENI_LO = (-5.0, 15.0, 0.0, 0.01)
MOHSENI_HI = (10.0, 35.0, 30.0, 2.0)
MOHSENI_MIN_ROWS = 20
GBM_PARAMS = dict(loss="squared_error", learning_rate=0.05, max_iter=400, max_leaf_nodes=31, min_samples_leaf=100,
                  l2_regularization=1.0, early_stopping=False, random_state=0)


def add_doy(df: pd.DataFrame) -> pd.DataFrame:
    doy = pd.to_datetime(df["date"]).dt.dayofyear
    ang = 2 * np.pi * doy / 365.25
    return df.assign(doy=doy, doy_sin=np.sin(ang), doy_cos=np.cos(ang))


def mohseni(a7, mu, alpha, beta, gamma):
    return mu + (alpha - mu) / (1.0 + np.exp(gamma * (beta - np.asarray(a7, dtype=float))))


def fit_mohseni(a7, temp) -> tuple[tuple, bool]:
    """(params, ok). On a failed fit, or fewer than MOHSENI_MIN_ROWS rows, the starting values and ok=False."""
    from scipy.optimize import curve_fit
    if len(np.asarray(a7)) < MOHSENI_MIN_ROWS:
        return MOHSENI_P0, False
    try:
        p, _ = curve_fit(mohseni, np.asarray(a7, float), np.asarray(temp, float), p0=MOHSENI_P0,
                         bounds=(MOHSENI_LO, MOHSENI_HI), maxfev=20000)
        return tuple(float(x) for x in p), True
    except (RuntimeError, ValueError):
        return MOHSENI_P0, False


def fit_doy_baseline(doy, temp, window: int = 31) -> dict:
    """Day-of-year mean, smoothed over a centred window (sum of temperatures in the window / rows in it, wrapping
    round the year). Days with no row in their window take the overall mean."""
    doy = np.asarray(doy, int)
    temp = np.asarray(temp, float)
    s = np.bincount(doy, weights=temp, minlength=367)[1:367]
    n = np.bincount(doy, minlength=367)[1:367].astype(float)
    h = window // 2
    ss = np.zeros(366)
    nn = np.zeros(366)
    for off in range(-h, h + 1):
        ss += np.roll(s, -off)
        nn += np.roll(n, -off)
    mean = float(temp.mean()) if len(temp) else float("nan")
    table = np.where(nn > 0, ss / np.where(nn > 0, nn, 1), mean)
    return {"table": table, "mean": mean}


def predict_doy(model: dict, doy) -> np.ndarray:
    return model["table"][np.asarray(doy, int) - 1]


def fit_air7(a7, temp) -> tuple[float, float]:
    b, a = np.polyfit(np.asarray(a7, float), np.asarray(temp, float), 1)
    return float(a), float(b)


def fit_candidate(train: pd.DataFrame) -> dict:
    """Stage 1 per type (Mohseni on a7), stage 2 one boosted model on the residual. `train` has FEATURES, type,
    temp."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    curves, ok = {}, {}
    resid = np.zeros(len(train))
    for t, g in train.groupby("type"):
        p, good = fit_mohseni(g["a7"], g["temp"])
        curves[t], ok[t] = p, good
        resid[train.index.get_indexer(g.index)] = g["temp"].to_numpy() - mohseni(g["a7"], *p)
    # An input with no value at all in the training rows carries nothing; scikit-learn cannot bin it, so it is left
    # out of that fit (and of its predictions).
    feats = [c for c in FEATURES if np.isfinite(train[c].to_numpy(float)).any()]
    gbm = HistGradientBoostingRegressor(categorical_features=[feats.index("type_code")], **GBM_PARAMS)
    gbm.fit(train[feats].to_numpy(float), resid)
    return {"curves": curves, "fit_ok": ok, "gbm": gbm, "features": feats}


def predict_candidate(model: dict, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(stage 1 alone, stage 1 + stage 2)."""
    s1 = np.full(len(df), np.nan)
    for t, g in df.groupby("type"):
        p = model["curves"].get(t)
        if p is not None:
            s1[df.index.get_indexer(g.index)] = mohseni(g["a7"], *p)
    s2 = model["gbm"].predict(df[model["features"]].to_numpy(float))
    return s1, s1 + s2


# ================================================================== scores and verdict
def rmse(err) -> float:
    e = np.asarray(err, float)
    return float(np.sqrt(np.mean(e ** 2))) if len(e) else float("nan")


def boot_gains(groups, err_cand, err_bases: dict, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """RMSE gains of the candidate over each baseline, with 95% intervals from resampling whole groups (each drawn
    group brings all its rows). Returns {name: {"gain", "lo", "hi"}}."""
    g = pd.Series(np.asarray(groups)).astype(str)
    codes, uniq = pd.factorize(g)
    G = len(uniq)
    cnt = np.bincount(codes, minlength=G).astype(float)
    sse_c = np.bincount(codes, weights=np.asarray(err_cand, float) ** 2, minlength=G)
    sse_b = {k: np.bincount(codes, weights=np.asarray(v, float) ** 2, minlength=G) for k, v in err_bases.items()}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, G, size=(n_boot, G))
    n = cnt[draws].sum(1)
    rc = np.sqrt(sse_c[draws].sum(1) / n)
    out = {}
    for k, s in sse_b.items():
        rb = np.sqrt(s[draws].sum(1) / n)
        gains = rb - rc
        out[k] = {"gain": float(np.sqrt(s.sum() / cnt.sum()) - np.sqrt(sse_c.sum() / cnt.sum())),
                  "lo": float(np.percentile(gains, 2.5)), "hi": float(np.percentile(gains, 97.5))}
    return out


def verdict(type_: str, n_waters: int, n_rows: int, rmse_cand: float, gains: dict) -> dict:
    """The pass rule for rivers or lakes. gains: {"doy": {...}, "air7": {...}} from boot_gains."""
    conds = {
        "gate": n_waters >= GATE_WATERS and n_rows >= GATE_ROWS,
        "beats_doy": gains["doy"]["lo"] > 0,
        "beats_air7": gains["air7"]["lo"] > 0,
        "rmse": rmse_cand <= RMSE_MAX[type_],
    }
    if not conds["gate"]:
        label = "too few to judge"
    else:
        label = "pass" if all(conds.values()) else "fail"
    return {"label": label, "conditions": conds}


def summary(err) -> dict:
    e = np.asarray(err, float)
    if not len(e):
        return {"n": 0}
    return {"n": int(len(e)), "rmse": rmse(e), "bias": float(e.mean()), "mae": float(np.abs(e).mean()),
            "p90_abs": float(np.percentile(np.abs(e), 90))}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
