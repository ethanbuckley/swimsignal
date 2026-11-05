"""docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md: the stated protocol as functions of arrays and frames, no network.

Stage 1 (stage1.py) and the coverage prototype (coverage.py) use the pixel half: the water mask, the site's water,
core pixels, the size rule, the per-scene clear rule and the reading. Stage 2 (stage2.py) uses the rest: pairing, the
gate, the models, the hold-outs, the bootstrap, the labels, the placebo and the stop rules. tests/test_lake_algae_sat_eval.py
checks each on synthetic data.

Choices fixed here, before any reading or check was seen, and listed in the statement ("Harness choices"):
* The water mask's denominator also leaves out SCL 0 (no data) and 1 (saturated or defective): a pixel the scene did
  not see is not evidence of land.
* The connected piece is found inside a square of COMPONENT_RADIUS_M around the point, not the whole tile.
* A core pixel is a pixel of the site's water whose 8 neighbours are all in the connected piece; the 300 m cut is not
  a shore.
* A pixel whose B4 or B5 reflectance (after scale and offset) is 0 or less, or no data, has no NDCI and is left out of
  the median. A usable scene where every clear core pixel lacks NDCI gives no reading.
* A training fold whose outcomes are all 0 or all 1 predicts that rate (R1) for every model.
* Brier is the mean of (p - y)^2. AUC is sklearn's roc_auc_score; a draw with no event or no non-event gives no AUC
  and is counted.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

# --- pixels -------------------------------------------------------------------------------------------------
PIXEL_M = 20
WATER = 6
NOT_SEEN = (0, 1, 3, 8, 9, 10, 11)        # left out of the water vote: no data, defective, shadow, cloud, cirrus, snow
CLEAR = (2, 4, 5, 6, 7)                   # clear for the per-scene rule
SITE_RADIUS_M = 300
COMPONENT_RADIUS_M = 1000
MIN_CORE = 9
MIN_CLEAR_SHARE = 0.80

# --- pairing, gate, models ----------------------------------------------------------------------------------
PAIR_DAYS = 3
DESCRIPTION_PAIR_DAYS = (0, 7)
SEASON_MONTHS = (5, 6, 7, 8, 9)
YEARS = tuple(range(2020, 2027))
GATE_EVENTS, GATE_WATER_BODIES, GATE_PER_SEASON, GATE_SEASONS = 30, 4, 5, 3
AUC_MIN = 0.65
N_BOOT, N_PLACEBO, SEED = 2000, 200, 20261026
LO, HI = 1.25, 98.75                      # two outcomes judged: 97.5% intervals
LO4, HI4 = 0.625, 99.375                  # CLMS judged too (four comparisons): 98.75%
CAL_TOL = {"A": 0.03, "B": 0.01}
# B and H from the published lake rate in algae.py's docstring (310 of 1,304 seen, 63 objectionable), fixed in the
# statement: B = 0.02 x p(1 - p), H = B / 2.
MARGINS = {"A": (0.0036, 0.0018), "B": (0.0009, 0.00046)}
LEVELS = {
    "No material present": (0, "none seen"),
    "Trace present - 1 or 2 items": (1, "a trace (1 or 2 items)"),
    "Some at intervals - 3 to 6 items": (2, "some at intervals (3 to 6 items)"),
    "Sufficient to be objectionable >6 items": (3, "enough to be objectionable (more than 6 items)"),
}

WATER_BODY = {
    "Windermere, Lakeside YMCA": "Windermere", "Windermere, Millerground Landing": "Windermere",
    "Windermere, Rayrigg Meadow": "Windermere", "Windermere, Fellfoot": "Windermere",
    "Coniston Water, Brown Howe": "Coniston Water", "Coniston Water, Boating Centre": "Coniston Water",
    "Coniston Water, Monk Coniston": "Coniston Water",
    "Rutland Water Whitwell Creek": "Rutland Water", "Rutland Water Sykes Lane": "Rutland Water",
    "Derwent Water at Crow Park": "Derwent Water",
    "Colwick Country Park (West Lake)": "Colwick Country Park, West Lake",
    "Cotswold Country Park and Beach": "Cotswold Country Park lake",
    "Hampstead Heath (Ladies Pond)": "Hampstead Heath Ladies Pond",
    "Hampstead Heath (Mens Pond)": "Hampstead Heath Men's Pond",
    "Hampstead Heath (Mixed Pond)": "Hampstead Heath Mixed Pond",
    "The Serpentine - Hyde Park": "The Serpentine",
    "Frensham Great Pond": "Frensham Great Pond",
    "Henleaze Lake": "Henleaze Lake",
}
LAKE_DISTRICT = {"Windermere", "Coniston Water", "Derwent Water"}


class StopRule(RuntimeError):
    """A stated stop rule failed: nothing is scored, and that is reported first."""


def lake_sites(raw_json: Path) -> pd.DataFrame:
    """The 18 lake bathing waters with their water body, from data/raw/bathing_waters_inland.json."""
    import json
    d = pd.DataFrame(json.loads(Path(raw_json).read_text()))
    d = d[d["kind"] == "lake"].rename(columns={"id": "bw_id"})[["bw_id", "name", "lat", "lon", "wqa_point"]]
    missing = sorted(set(d["name"]) - set(WATER_BODY))
    if missing:
        raise StopRule(f"lake sites with no water body: {missing}")
    return d.assign(water_body=d["name"].map(WATER_BODY)).reset_index(drop=True)


def water_mask(scl_stack: np.ndarray) -> np.ndarray:
    """(scenes, rows, cols) SCL -> water where SCL is 6 in at least half the scenes that saw the pixel."""
    s = np.asarray(scl_stack)
    seen = ~np.isin(s, NOT_SEEN)
    n_seen = seen.sum(axis=0)
    n_water = (s == WATER).sum(axis=0)
    return (n_seen > 0) & (2 * n_water >= n_seen)


def _label8(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage
    return ndimage.label(mask, structure=np.ones((3, 3), dtype=int))[0]


def site_water(mask: np.ndarray, centre_rc: tuple[float, float], pixel_m: float = PIXEL_M,
               radius_m: float = SITE_RADIUS_M) -> tuple[np.ndarray, np.ndarray]:
    """(the connected piece holding the water pixel nearest the point, that piece cut to radius_m of the point).
    centre_rc is the point in fractional pixel coordinates of `mask` (row, col of pixel centres at i + 0.5)."""
    rows, cols = np.indices(mask.shape)
    d2 = ((rows + 0.5 - centre_rc[0]) ** 2 + (cols + 0.5 - centre_rc[1]) ** 2) * pixel_m ** 2
    empty = np.zeros_like(mask, dtype=bool)
    if not mask.any():
        return empty, empty
    nearest = np.unravel_index(np.argmin(np.where(mask, d2, np.inf)), mask.shape)
    lab = _label8(mask)
    piece = lab == lab[nearest]
    return piece, piece & (d2 <= radius_m ** 2)


def core_pixels(piece: np.ndarray, site: np.ndarray) -> np.ndarray:
    """Pixels of the site's water whose 8 neighbours are all in the connected piece. Off-grid neighbours are not
    water."""
    p = np.pad(piece, 1, constant_values=False)
    allw = np.ones_like(piece, dtype=bool)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            allw &= p[1 + dr:1 + dr + piece.shape[0], 1 + dc:1 + dc + piece.shape[1]]
    return site & allw


def passes_size_rule(core: np.ndarray) -> bool:
    return int(core.sum()) >= MIN_CORE


def scene_clear(scl: np.ndarray, core: np.ndarray) -> tuple[int, bool]:
    """(clear core pixels, usable): usable when at least 80% of the core pixels are clear."""
    n = int(core.sum())
    clear = int((np.isin(scl, CLEAR) & core).sum())
    return clear, n > 0 and clear >= MIN_CLEAR_SHARE * n


def reflectance(dn: np.ndarray, band: dict) -> np.ndarray:
    """DN to reflectance with the item's raster:bands scale and offset. Refuses a band without them (stop rule):
    the offset changed with processing baseline 04.00 in January 2022."""
    if band is None or "scale" not in band or "offset" not in band:
        raise StopRule("an item lacks raster:bands scale or offset")
    nodata = band.get("nodata", 0)
    r = dn.astype(float) * float(band["scale"]) + float(band["offset"])
    return np.where(dn == nodata, np.nan, r)


def b4_to_20m(b4: np.ndarray) -> np.ndarray:
    """10 m to the 20 m grid, 2 x 2 mean; a block with any no-data pixel is no data."""
    h, w = b4.shape[0] // 2 * 2, b4.shape[1] // 2 * 2
    return b4[:h, :w].reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))


def ndci(b4: np.ndarray, b5: np.ndarray) -> np.ndarray:
    """(B5 - B4) / (B5 + B4), NaN where either reflectance is missing or 0 or less."""
    ok = (b4 > 0) & (b5 > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(ok, (b5 - b4) / (b5 + b4), np.nan)


def scene_reading(scl: np.ndarray, core: np.ndarray, index: np.ndarray) -> tuple[int, bool, float]:
    """(clear core pixels, usable, median index over clear core pixels; NaN when not usable or nothing valid)."""
    clear, usable = scene_clear(scl, core)
    if not usable:
        return clear, False, float("nan")
    v = index[np.isin(scl, CLEAR) & core]
    v = v[np.isfinite(v)]
    return clear, True, float(np.median(v)) if len(v) else float("nan")


def one_per_date(features: pd.DataFrame) -> pd.DataFrame:
    """Usable scenes, one per site and UTC date: the most clear core pixels; on a tie, the first item id."""
    f = features[features["usable"] & features["reading"].notna()]
    f = f.sort_values(["bw_id", "scene_date", "clear_core", "item_id"], ascending=[True, True, False, True])
    return f.drop_duplicates(["bw_id", "scene_date"], keep="first").reset_index(drop=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_hash(path: Path, committed: str) -> None:
    """Stage 2 refuses a features (or checks) file whose SHA-256 differs from the committed one."""
    got = sha256(path)
    if got != committed.strip().lower():
        raise StopRule(f"{Path(path).name}: SHA-256 {got} differs from the committed {committed.strip()}")


def check_levels(levels: dict) -> None:
    """The level map must reproduce algae.LEVELS exactly."""
    if levels != LEVELS:
        raise StopRule("the level map differs from algae.LEVELS")


# --- checks and pairing -------------------------------------------------------------------------------------
def prepare_checks(checks: pd.DataFrame, sites: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Checks at the lake sites, 1 May to 30 September, 2020-2026, with level, outcomes A and B, the local date, the
    month, the season and the previous check's level at the same site and season ('none' for the first). A wording
    not in LEVELS is dropped and counted."""
    c = checks.merge(sites[["wqa_point", "bw_id", "water_body"]], on="wqa_point", how="inner")
    t = pd.to_datetime(c["sample_time"])
    c = c.assign(sample_time=t, date=t.dt.date, month=t.dt.month, season=t.dt.year)
    c = c[c["month"].isin(SEASON_MONTHS) & c["season"].isin(YEARS)]
    known = c["result"].isin(LEVELS)
    dropped = int((~known).sum())
    c = c[known].copy()
    c["level"] = c["result"].map(lambda r: LEVELS[r][0])
    c["A"] = (c["level"] >= 1).astype(int)
    c["B"] = (c["level"] >= 3).astype(int)
    c = c.sort_values(["bw_id", "sample_time"]).drop_duplicates(["bw_id", "sample_time"]).reset_index(drop=True)
    prev = c.groupby(["bw_id", "season"])["level"].shift(1)
    c["prev"] = prev.map(lambda v: "none" if pd.isna(v) else str(int(v)))
    return c, dropped


def pair(checks: pd.DataFrame, scenes: pd.DataFrame, window_days: int = PAIR_DAYS) -> pd.DataFrame:
    """Each check on local date d takes the latest usable scene at its site dated d - window to d (the scene's UTC
    date). Adds reading, scene_date, scene_item and lag_days; NaN reading where there is none."""
    s = scenes[["bw_id", "scene_date", "item_id", "reading"]].copy()
    s["scene_date"] = pd.to_datetime(s["scene_date"]).dt.date
    out = []
    by_site = {k: g.sort_values("scene_date") for k, g in s.groupby("bw_id")}
    for r in checks.itertuples(index=False):
        g = by_site.get(r.bw_id)
        hit = None
        if g is not None:
            lo = r.date - pd.Timedelta(days=window_days).to_pytimedelta()
            m = g[(g["scene_date"] >= lo) & (g["scene_date"] <= r.date)]
            if len(m):
                hit = m.iloc[-1]
        out.append((hit["reading"] if hit is not None else np.nan, hit["scene_date"] if hit is not None else None,
                    hit["item_id"] if hit is not None else None,
                    (r.date - hit["scene_date"]).days if hit is not None else np.nan))
    p = checks.copy()
    p[["reading", "scene_date", "scene_item", "lag_days"]] = pd.DataFrame(out, index=p.index)
    p["reading"] = p["reading"].astype(float)
    return p


def gate(rows: pd.DataFrame, outcome: str) -> dict:
    y = rows[outcome]
    ev = rows[y == 1]
    per_season = ev.groupby("season").size()
    by_wb = ev.groupby("water_body").size()
    ok = (len(ev) >= GATE_EVENTS and (by_wb >= 1).sum() >= GATE_WATER_BODIES
          and (per_season >= GATE_PER_SEASON).sum() >= GATE_SEASONS)
    return {"events": int(len(ev)), "rows": int(len(rows)), "water_bodies_with_events": int((by_wb >= 1).sum()),
            "seasons_with_5": int((per_season >= GATE_PER_SEASON).sum()),
            "by_water_body": {k: int(v) for k, v in by_wb.items()},
            "by_season": {int(k): int(v) for k, v in per_season.items()}, "judged": bool(ok)}


# --- models and hold-outs -----------------------------------------------------------------------------------
MONTH_COLS = [f"m{m}" for m in SEASON_MONTHS]
PREV_COLS = ["p0", "p1", "p2", "p3", "pnone"]
R2_COLS = MONTH_COLS + PREV_COLS
M1_COLS = ["reading"]
M2_COLS = R2_COLS + ["reading"]
MODELS = {"R1": None, "R2": R2_COLS, "M1": M1_COLS, "M2": M2_COLS}


def design(rows: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=rows.index)
    for m in SEASON_MONTHS:
        X[f"m{m}"] = (rows["month"] == m).astype(float)
    for p in ("0", "1", "2", "3", "none"):
        X[f"p{p}"] = (rows["prev"] == p).astype(float)
    X["reading"] = rows["reading"].astype(float)
    return X


def fit_predict(Xtr: pd.DataFrame, ytr: np.ndarray, Xte: pd.DataFrame, cols: list[str] | None) -> np.ndarray:
    """R1 (cols None): the training rate. Otherwise ecoli.fit: logistic regression on standardised inputs, C = 1."""
    if len(ytr) == 0:   # a fold with no training rows (one season or one water body in all): no prediction
        return np.full(len(Xte), np.nan)
    rate = float(np.mean(ytr))
    if cols is None or ytr.min() == ytr.max():
        return np.full(len(Xte), rate)
    from dipcast.model.ecoli import fit
    return fit(Xtr, ytr, cols).predict(Xte)


def hold_out(rows: pd.DataFrame, outcome: str, by: str) -> pd.DataFrame:
    """Predictions for every row from models fitted without its group (`water_body` for LOWO, `season` for LOSO)."""
    X, y = design(rows), rows[outcome].to_numpy()
    pred = pd.DataFrame(index=rows.index, columns=list(MODELS), dtype=float)
    for g in sorted(rows[by].unique()):
        te = (rows[by] == g).to_numpy()
        for name, cols in MODELS.items():
            pred.loc[te, name] = fit_predict(X[~te], y[~te], X[te], cols)
    return pred


def brier(p, y) -> float:
    """Over rows with a prediction (a fold with no training rows gives none; their count is reported)."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(p)
    return float(np.mean((p[ok] - y[ok]) ** 2)) if ok.any() else float("nan")


def auc(score, y) -> float:
    s, y = np.asarray(score, dtype=float), np.asarray(y)
    ok = np.isfinite(s)
    s, y = s[ok], y[ok]
    if len(y) == 0 or y.min() == y.max():
        return float("nan")
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def cluster_draws(clusters: np.ndarray, n: int = N_BOOT, seed: int = SEED) -> list[np.ndarray]:
    """Row indices for each cluster-bootstrap draw: water bodies drawn with replacement, sorted cluster order."""
    rng = np.random.default_rng(seed)
    keys = np.array(sorted(set(clusters)))
    idx = {k: np.flatnonzero(clusters == k) for k in keys}
    draws = []
    for _ in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        draws.append(np.concatenate([idx[k] for k in pick]))
    return draws


def boot_interval(values: np.ndarray, levels: tuple[float, float] = (LO, HI)) -> tuple[float, float, int]:
    v = np.asarray(values, dtype=float)
    ok = np.isfinite(v)
    if not ok.any():
        return float("nan"), float("nan"), int((~ok).sum())
    return float(np.percentile(v[ok], levels[0])), float(np.percentile(v[ok], levels[1])), int((~ok).sum())


def gain_with_interval(y, p_ref, p_new, clusters, draws=None, levels: tuple[float, float] = (LO, HI)) -> dict:
    """Brier gain (ref minus new), point and cluster-bootstrap interval."""
    y, p_ref, p_new = (np.asarray(a, dtype=float) for a in (y, p_ref, p_new))
    draws = draws if draws is not None else cluster_draws(np.asarray(clusters))
    g = [brier(p_ref[i], y[i]) - brier(p_new[i], y[i]) for i in draws]
    lo, hi, bad = boot_interval(np.array(g), levels)
    return {"d": brier(p_ref, y) - brier(p_new, y), "L": lo, "U": hi, "draws_without_value": bad}


def label(d: float, L: float, U: float, B: float, H: float, secondary_harm: bool = False) -> str:
    """The near-miss labels (docs/LAKE-ECOLI-LINE-TEST-2026-10.md addendum), the first that fits."""
    if d >= B and L > 0:
        return "Better"
    if d > 0 and L <= 0 and L > -H and not secondary_harm:
        return "Promising, not shown"
    if -H < L and U < B:
        return "No useful difference"
    if L <= -H and d <= 0:
        return "Possible harm"
    if U < 0:
        return "Harm"
    if L <= -H and U >= B:
        return "Too uncertain"
    return "Unlabelled"


def placebo_aucs(rows: pd.DataFrame, outcome: str, n: int = N_PLACEBO, seed: int = SEED) -> np.ndarray:
    """Pooled AUC of the raw reading with readings shuffled within each water body and season (sorted group order)."""
    rng = np.random.default_rng(seed)
    y = rows[outcome].to_numpy()
    r = rows["reading"].to_numpy(dtype=float)
    idx = rows.reset_index(drop=True).groupby(["water_body", "season"], sort=True).indices
    groups = [np.asarray(idx[k]) for k in sorted(idx)]
    out = np.empty(n)
    for i in range(n):
        s = r.copy()
        for g in groups:
            s[g] = r[rng.permutation(g)]
        out[i] = auc(s, y)
    return out


def placebo_passes(real: float, placebo: np.ndarray) -> dict:
    p95 = float(np.percentile(placebo, 95))
    ranked = np.sort(placebo)
    k190 = float(ranked[189]) if len(ranked) >= 190 else float("nan")
    return {"real": real, "p95": p95, "rank_190th": k190, "at_or_above_real": int((placebo >= real).sum()),
            "passes": bool(real > p95 and real > k190)}


def seasons_needed(n_seasons: int) -> int:
    return math.ceil(2 * n_seasons / 3)


def score_outcome(rows: pd.DataFrame, outcome: str, levels: tuple[float, float] = (LO, HI), gate_fn=None) -> dict:
    """Every stated figure for one outcome. `rows`: paired checks with a reading at sites past the size rule.
    levels: the interval's percentiles ((LO4, HI4) when CLMS is judged too); gate_fn: gate, or clms_gate."""
    gate_fn = gate_fn or gate
    B, H = MARGINS[outcome]
    y = rows[outcome].to_numpy()
    clusters = rows["water_body"].to_numpy()
    out = {"gate": gate_fn(rows, outcome)}
    lowo, loso = hold_out(rows, outcome, "water_body"), hold_out(rows, outcome, "season")
    draws = cluster_draws(clusters)
    tables = {}
    for name, pred in (("LOWO", lowo), ("LOSO", loso)):
        tables[name] = {m: {"brier": brier(pred[m], y), "auc": auc(pred[m], y),
                            "rows_without_prediction": int(pred[m].isna().sum())} for m in MODELS}
    out["tables"] = tables
    prim = gain_with_interval(y, lowo["R2"], lowo["M2"], clusters, draws, levels)
    # Condition 5: the primary comparison for the Lake District and the lowland waters, each its own bootstrap.
    groups = {}
    for gname, members in (("Lake District", rows["water_body"].isin(LAKE_DISTRICT)),
                           ("lowland", ~rows["water_body"].isin(LAKE_DISTRICT))):
        m = members.to_numpy()
        if m.sum() and len(set(clusters[m])) >= 1:
            gi = gain_with_interval(y[m], lowo["R2"].to_numpy()[m], lowo["M2"].to_numpy()[m], clusters[m],
                                    levels=levels)
            gi["label"] = label(gi["d"], gi["L"], gi["U"], B, H)
            groups[gname] = gi
    harm = any(g["label"] == "Harm" for g in groups.values())
    prim["label"] = label(prim["d"], prim["L"], prim["U"], B, H, secondary_harm=harm)
    out["primary"] = {**prim, "B": B, "H": H}
    out["groups"] = groups
    # 1. Ranking, unfitted.
    a = auc(rows["reading"], y)
    a_draws = np.array([auc(rows["reading"].to_numpy()[i], y[i]) for i in draws])
    lo, hi, bad = boot_interval(a_draws, levels)
    c1 = {"auc": a, "L": lo, "U": hi, "draws_without_auc": bad, "holds": bool(a >= AUC_MIN and lo > 0.5)}
    # 2. LOWO, M1 against R1.
    g2 = gain_with_interval(y, lowo["R1"], lowo["M1"], clusters, draws, levels)
    c2 = {**g2, "holds": bool(g2["d"] >= B and g2["L"] > 0)}
    # 3. LOSO, M2 against R2, pooled and by season with 5 or more events.
    pooled = brier(loso["R2"], y) - brier(loso["M2"], y)
    by_season = {}
    for s in sorted(rows["season"].unique()):
        m = (rows["season"] == s).to_numpy()
        if y[m].sum() >= GATE_PER_SEASON:
            by_season[int(s)] = brier(loso["R2"].to_numpy()[m], y[m]) - brier(loso["M2"].to_numpy()[m], y[m])
    need = seasons_needed(len(by_season))
    pos = sum(v > 0 for v in by_season.values())
    c3 = {"pooled": pooled, "by_season": by_season, "positive": pos, "needed": need,
          "holds": bool(pooled > 0 and len(by_season) > 0 and pos >= need)}
    # 4. Placebo.
    pl = placebo_aucs(rows, outcome)
    c4 = {**placebo_passes(a, pl), "lowest": float(np.nanmin(pl)), "median": float(np.nanmedian(pl)),
          "highest": float(np.nanmax(pl))}
    c4["holds"] = c4.pop("passes")
    # 5. No group labelled Harm.
    c5 = {"labels": {k: v["label"] for k, v in groups.items()}, "holds": not harm}
    # 6. Calibration, LOWO M2.
    mean_f, rate = float(np.mean(lowo["M2"])), float(np.mean(y))
    c6 = {"mean_forecast": mean_f, "observed": rate, "tolerance": CAL_TOL[outcome],
          "holds": bool(abs(mean_f - rate) <= CAL_TOL[outcome])}
    out["conditions"] = {"1": c1, "2": c2, "3": c3, "4": c4, "5": c5, "6": c6}
    judged = out["gate"]["judged"]
    all_hold = all(c["holds"] for c in out["conditions"].values())
    if not judged:
        verdict = "Too few to judge"
    elif prim["label"] == "Better" and all_hold:
        verdict = "Passes"
    elif prim["label"] == "Promising, not shown" and all(out["conditions"][k]["holds"] for k in ("1", "4", "5", "6")):
        verdict = "Promising, not shown: to the 2027 forward step"
    else:
        verdict = "Fails"
    out["verdict"] = verdict
    return out


# --- CLMS Lake Water Quality 100 m v2: the first candidate, benchmarked before custom NDCI ---------------------
# Stated in the revision of 26 October 2026, before any CLMS pixel was read (none has been: download needs a CDSE
# account). Fetching is not built: it waits on Ethan's decision about an account. These functions fix the rules.
CLMS_LAG_DAYS = 4            # "Within 4 days after the end of the synthesis period" (the product page)
CLMS_MIN_PIXELS = 3          # 100 m pixels whose centre is on a core 20 m pixel within 300 m of the point
CLMS_MIN_DEKADS = 8          # usable dekads of the 15 from May to September, in 2025
CLMS_MIN_WATER_BODIES = GATE_WATER_BODIES
CLMS_SEASONS = (2024, 2025, 2026)
CLMS_INVALID_FLAGS = ("L1_invalid", "bright_pixels", "cloud", "snow_ice", "land", "chla_invalid",
                      "atmospheric_correction_failure", "floating_macrophytes_or_mixed_pixel")


def clms_site_pixels(centres_rc: np.ndarray, core: np.ndarray, centre_rc: tuple[float, float],
                     pixel_m: float = PIXEL_M, radius_m: float = SITE_RADIUS_M) -> np.ndarray:
    """Which CLMS pixels count at a site: those whose centre, given in fractional pixel coordinates of the stage 1
    window (row, col), lies on a core pixel and within radius_m of the point. Returns a boolean per centre."""
    c = np.asarray(centres_rc, dtype=float).reshape(-1, 2)
    r, k = np.floor(c[:, 0]).astype(int), np.floor(c[:, 1]).astype(int)
    inside = (r >= 0) & (r < core.shape[0]) & (k >= 0) & (k < core.shape[1])
    on_core = np.zeros(len(c), dtype=bool)
    on_core[inside] = core[r[inside], k[inside]]
    d = np.hypot(c[:, 0] - centre_rc[0], c[:, 1] - centre_rc[1]) * pixel_m
    return on_core & (d <= radius_m)


def clms_flag_invalid(flags: np.ndarray, meanings: list[str], masks: list[int]) -> np.ndarray:
    """True where any invalidating flag is set. Bits come from the file's own flag_meanings and flag_masks, never
    from an assumed order. floating_cyanobacteria does not invalidate: it is the bloom. A file without one of the
    named flags stops the run."""
    m = dict(zip(meanings, masks, strict=True))
    missing = [f for f in CLMS_INVALID_FLAGS if f not in m]
    if missing:
        raise StopRule(f"CLMS quality_flags lacks {missing}")
    bits = 0
    for f in CLMS_INVALID_FLAGS:
        bits |= int(m[f])
    return (np.asarray(flags).astype(np.int64) & bits) != 0


def clms_dekad_reading(chla: np.ndarray, invalid: np.ndarray, counted: np.ndarray) -> tuple[int, float]:
    """(valid pixels, log10 of the median chlorophyll-a over them; NaN unless at least CLMS_MIN_PIXELS are valid)."""
    v = np.asarray(chla, dtype=float)[counted & ~invalid]
    v = v[np.isfinite(v) & (v > 0)]
    return len(v), float(np.log10(np.median(v))) if len(v) >= CLMS_MIN_PIXELS else float("nan")


def dekad_end(start) -> pd.Timestamp:
    s = pd.Timestamp(start)
    return (s + pd.offsets.MonthEnd(0)) if s.day == 21 else s + pd.Timedelta(days=9)


def clms_pair(checks: pd.DataFrame, dekads: pd.DataFrame, lag_days: int = CLMS_LAG_DAYS) -> pd.DataFrame:
    """A check on local date d takes the latest dekad at its site whose end plus lag_days is on or before d: what a
    page could have shown that day. dekads: bw_id, start (first day), reading."""
    k = dekads.dropna(subset=["reading"]).copy()
    k["ready"] = [(dekad_end(s) + pd.Timedelta(days=lag_days)).date() for s in k["start"]]
    k = k.rename(columns={"start": "scene_date"}).assign(item_id=k["start"].astype(str))
    out = []
    by_site = {b: g.sort_values("ready") for b, g in k.groupby("bw_id")}
    for r in checks.itertuples(index=False):
        g = by_site.get(r.bw_id)
        m = g[g["ready"] <= r.date] if g is not None else None
        hit = m.iloc[-1] if m is not None and len(m) else None
        out.append((hit["reading"] if hit is not None else np.nan, hit["item_id"] if hit is not None else None,
                    (r.date - hit["ready"]).days if hit is not None else np.nan))
    p = checks.copy()
    p[["reading", "dekad", "days_since_ready"]] = pd.DataFrame(out, index=p.index)
    p["reading"] = p["reading"].astype(float)
    return p


def clms_covers(site_dekads: pd.DataFrame) -> dict:
    """The decision rule. site_dekads: bw_id, water_body, start, n_pixels (counted at the site), reading (NaN when
    not usable). A water body is covered when one of its sites has at least CLMS_MIN_PIXELS counted pixels and a
    usable reading in at least CLMS_MIN_DEKADS of the 15 dekads of May to September 2025. CLMS is the primary
    reading when at least CLMS_MIN_WATER_BODIES water bodies are covered."""
    d = site_dekads.copy()
    d["start"] = pd.to_datetime(d["start"])
    d = d[(d["start"].dt.year == 2025) & d["start"].dt.month.isin(SEASON_MONTHS)]
    per_site = d.groupby(["water_body", "bw_id"]).agg(px=("n_pixels", "max"), usable=("reading", lambda s: int(s.notna().sum())))
    ok = per_site[(per_site["px"] >= CLMS_MIN_PIXELS) & (per_site["usable"] >= CLMS_MIN_DEKADS)]
    wbs = sorted(ok.index.get_level_values(0).unique())
    return {"covered_water_bodies": wbs, "covered_sites": sorted(ok.index.get_level_values(1)),
            "primary": len(wbs) >= CLMS_MIN_WATER_BODIES}


def clms_gate(rows: pd.DataFrame, outcome: str) -> dict:
    """The gate for the CLMS reading: 30 events at 4 or more water bodies, as for NDCI, and at least 5 in each of
    2025 and 2026 (its record starts in September 2024, so three seasons with 5 cannot be asked)."""
    g = gate(rows, outcome)
    ok = (g["events"] >= GATE_EVENTS and g["water_bodies_with_events"] >= GATE_WATER_BODIES
          and all(g["by_season"].get(y, 0) >= GATE_PER_SEASON for y in (2025, 2026)))
    return {**g, "judged": bool(ok)}
