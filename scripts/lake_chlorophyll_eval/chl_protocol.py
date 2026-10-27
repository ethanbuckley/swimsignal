"""docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md: the stated rules as functions of frames, no network.

The pixel rules (water mask, connected piece, core pixels, size rule, 80% clear rule, median NDCI) are
scripts/lake_algae_sat_eval/protocol.py's, unchanged and imported, so the reading is #377's reading. What is new here:
the lake selection (from metadata and sample dates only), the chlorophyll-a values and their "<" rule, the pairing
window, the Spearman correlation with its cluster bootstrap and placebo, the leave-one-lake-out calibration with its
labels, the gate and the stop rules. tests/test_lake_chlorophyll_eval.py checks each on synthetic data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lake_algae_sat_eval"))
import protocol as sat  # noqa: E402  (#377's protocol.py: pixel rules, bootstrap draws, labels)

StopRule = sat.StopRule
sha256 = sat.sha256
check_hash = sat.check_hash
label = sat.label

# --- the outcome ------------------------------------------------------------------------------------------------
DETERMINAND = "7887"                      # "Chlorophyll : Acetone Extract" (WQA codelist), the only one at lakes
UNIT = "MICROGRAM PER LITRE"
YEARS = tuple(range(2020, 2027))
SEASON_MONTHS = (5, 6, 7, 8, 9)
NO_IMAGERY_YEARS = (2022,)                # sentinel-2-c1-l2a holds no May-September 2022 item (#377, revision 3)

# --- which lakes (metadata and dates only) ---------------------------------------------------------------------
SHORE_M = 50.0              # a point inside a WFD lake outline, or within this of one (a shore or jetty sample)
INSET_M = 30.0              # the outline moved this far inward: about one 20 m pixel and a half off the shore
DISC_M = sat.SITE_RADIUS_M  # 300 m, #377's site radius
MIN_INSET_AREA_M2 = 10_000  # inset water within 300 m of the point: 25 pixels' worth, about 3 x the size rule's 9
MIN_DATES = 5               # sample dates in May-September of seasons with imagery
MAX_LAKES = 40
LAKE_POINT_TYPES = ("FRESHWATER - LAKES/PONDS/RESERVOIRS", "FRESHWATER - BATHING WATER")   # WQA types FA, FL
SHALLOW_M = 3.0             # lake type: HydroLAKES mean depth below this is "shallow", else "deeper"

# --- pairing and scoring ---------------------------------------------------------------------------------------
PAIR_DAYS = 1                             # a scene within 1 day either side of the sample date
DESCRIPTION_PAIR_DAYS = (0, 3)
N_BOOT, N_PLACEBO, SEED = sat.N_BOOT, sat.N_PLACEBO, sat.SEED
LO, HI = 2.5, 97.5                        # 95% intervals
RHO_MIN, RHO_LOWER = 0.5, 0.3
# The calibration margins, in skill units (1 - MSE_fit / MSE_reference), set from the reference's own error: B is a
# tenth of it. Working in the statement: a linear fit's skill over a constant is about r squared, and r = 0.3 (the
# Spearman bar's lower end) gives 0.09, rounded to 0.10. H is half of B.
B_SKILL, H_SKILL = 0.10, 0.05
GATE_PAIRS, GATE_LAKES, GATE_PAIRS_PER_LAKE = 60, 10, 3
GATE_SEASONS, GATE_PAIRS_PER_SEASON = 3, 10
GROUP_MIN_LAKES, GROUP_MIN_PAIRS = 4, 20


# --- selection -------------------------------------------------------------------------------------------------
def season_dates(dates: pd.DataFrame) -> pd.DataFrame:
    """Kept listing rows (wqa_meta.KEPT) -> one row per point and local sample date, May-September 2020-2026, with
    the point's position (its most common easting and northing) and its WQA point types. Only determinand 7887 in
    micrograms per litre."""
    d = dates[(dates["determinand"].astype(str).str.zfill(4) == DETERMINAND) & (dates["unit"] == UNIT)].copy()
    d["date"] = pd.to_datetime(d["sample_time"].str[:10], errors="coerce")
    d = d.dropna(subset=["date"])
    d = d[d["date"].dt.month.isin(SEASON_MONTHS) & d["date"].dt.year.isin(YEARS)]
    d["easting"] = pd.to_numeric(d["easting"], errors="coerce")
    d["northing"] = pd.to_numeric(d["northing"], errors="coerce")
    pos = (d.dropna(subset=["easting", "northing"]).groupby(["wqa_point", "easting", "northing"]).size()
           .reset_index(name="n").sort_values(["wqa_point", "n", "easting", "northing"],
                                              ascending=[True, False, True, True])
           .drop_duplicates("wqa_point")[["wqa_point", "easting", "northing"]])
    labels = d.groupby("wqa_point")["point_label"].first()
    types = d.groupby("wqa_point")["point_type"].agg(lambda t: "|".join(sorted(set(t.dropna()))))
    out = d[["wqa_point", "date"]].drop_duplicates().merge(pos, on="wqa_point", how="inner")
    out["point_label"] = out["wqa_point"].map(labels)
    out["point_type"] = out["wqa_point"].map(types)
    return out.sort_values(["wqa_point", "date"]).reset_index(drop=True)


def select(dates: pd.DataFrame, lakes, depth: dict[str, float] | None = None) -> tuple[list[dict], dict]:
    """The stated rule. `lakes`: WFD Cycle 3 lake outlines (GeoDataFrame in EPSG:27700 with WB_ID, WB_NAME,
    hydromorph). `depth`: WFD id -> HydroLAKES mean depth in metres (data/raw/lake_residence.csv), for the lake type
    only. Returns (chosen points, counts at each step). No result value is an input."""
    from shapely.geometry import Point
    depth = depth or {}
    counts = {}
    sd = season_dates(dates)
    counts["points_with_7887_may_sep"] = int(sd["wqa_point"].nunique())
    counts["point_dates_may_sep"] = int(len(sd))
    pts = sd.drop_duplicates("wqa_point")[["wqa_point", "point_label", "point_type", "easting", "northing"]]
    pts = pts.reset_index(drop=True)
    pts = pts[pts["point_type"].isin(LAKE_POINT_TYPES)]
    counts["points_typed_lake_or_bathing_water"] = int(len(pts))
    lk = lakes.rename(columns=str.lower)[["wb_id", "wb_name", "hydromorph", "geometry"]].reset_index(drop=True)
    sindex = lk.sindex
    rows = []
    for p in pts.itertuples(index=False):
        pt = Point(p.easting, p.northing)
        near = list(sindex.query(pt.buffer(SHORE_M)))
        if not near:
            continue
        dist = {i: lk.geometry[i].distance(pt) for i in near}
        i = min(dist, key=lambda k: (dist[k], lk.wb_id[k]))
        if dist[i] > SHORE_M:
            continue
        geom = lk.geometry[i]
        inset = geom.buffer(-INSET_M)
        area = float(inset.intersection(pt.buffer(DISC_M, quad_segs=64)).area) if not inset.is_empty else 0.0
        rows.append({"wqa_point": p.wqa_point, "point_label": p.point_label, "point_type": p.point_type,
                     "easting": float(p.easting),
                     "northing": float(p.northing), "wb_id": lk.wb_id[i], "lake_name": lk.wb_name[i],
                     "hydromorph": lk.hydromorph[i], "lake_area_km2": float(geom.area) / 1e6,
                     "inside_outline": bool(geom.contains(pt)), "distance_to_outline_m": float(geom.boundary.distance(pt)),
                     "inset_area_m2": area})
    cand = pd.DataFrame(rows)
    counts["points_on_or_within_50m_of_a_wfd_lake"] = int(len(cand))
    counts["lakes_on_or_within_50m"] = int(cand["wb_id"].nunique()) if len(cand) else 0
    if not len(cand):
        return [], counts
    cand = cand[cand["inset_area_m2"] >= MIN_INSET_AREA_M2]
    counts["points_past_the_inset_area_rule"] = int(len(cand))
    img = sd[~sd["date"].dt.year.isin(NO_IMAGERY_YEARS)]
    n_img = img.groupby("wqa_point").size()
    cand = cand.assign(n_dates_imagery=cand["wqa_point"].map(n_img).fillna(0).astype(int))
    cand = cand[cand["n_dates_imagery"] >= MIN_DATES]
    counts["points_with_5_or_more_dates_in_seasons_with_imagery"] = int(len(cand))
    counts["lakes_past_every_rule"] = int(cand["wb_id"].nunique())
    # One point per lake: the most dates; on a tie, the first point notation.
    cand = cand.sort_values(["wb_id", "n_dates_imagery", "wqa_point"], ascending=[True, False, True])
    one = cand.drop_duplicates("wb_id")
    # The cap: the most dates first; on a tie, the larger lake, then the WFD id.
    one = one.sort_values(["n_dates_imagery", "lake_area_km2", "wb_id"], ascending=[False, False, True])
    chosen = one.head(MAX_LAKES).reset_index(drop=True)
    counts["lakes_chosen"] = int(len(chosen))
    counts["lakes_left_out_by_the_cap"] = int(len(one) - len(chosen))
    from pyproj import Transformer
    tr = Transformer.from_crs(27700, 4326, always_xy=True)
    out = []
    for r in chosen.itertuples(index=False):
        lon, lat = tr.transform(r.easting, r.northing)
        dd = sd[sd["wqa_point"] == r.wqa_point]["date"]
        dep = depth.get(r.wb_id)
        dep = None if dep is None or not np.isfinite(dep) else float(dep)
        out.append({**{k: getattr(r, k) for k in chosen.columns}, "depth_m": dep,
                    "lake_type": None if dep is None else "shallow" if dep < SHALLOW_M else "deeper",
                    "lon": round(lon, 6), "lat": round(lat, 6),
                    "dates": [x.strftime("%Y-%m-%d") for x in sorted(dd)]})
    counts["sample_dates_at_chosen_points"] = int(sum(len(p["dates"]) for p in out))
    counts["sample_dates_at_chosen_points_in_seasons_with_imagery"] = int(sum(p["n_dates_imagery"] for p in out))
    counts["chosen_by_lake_type"] = {str(t): sum(p["lake_type"] == t for p in out) for t in ("shallow", "deeper", None)}
    return out, counts


def near_dates(item_date: str, sample_dates: set[str], window: int) -> bool:
    d = pd.Timestamp(item_date)
    return any(abs((d - pd.Timestamp(s)).days) <= window for s in sample_dates)


# --- the outcome values (stage 2 only) ---------------------------------------------------------------------------
def chl_value(s) -> tuple[float, str]:
    """A WQA result string -> (micrograms per litre, how). '<x' (below the reporting limit) -> x / 2, 'censored';
    '>x' -> x, 'above'; a number -> itself, 'measured'. Anything else, or a value of 0 or less, -> NaN, 'dropped'."""
    t = str(s if s is not None else "").strip()
    how = "censored" if t.startswith("<") else "above" if t.startswith(">") else "measured"
    try:
        v = float(t.lstrip("<>= "))
    except ValueError:
        return float("nan"), "dropped"
    if how == "censored":
        v = v / 2
    if not np.isfinite(v) or v <= 0:
        return float("nan"), "dropped"
    return v, how


def prepare_samples(values: pd.DataFrame, points: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Fetched values at the chosen points -> one sample per point and local date (the first by time), May-September
    2020-2026, with log10 chlorophyll-a, the lake, its type and the season. Stops on another unit or determinand."""
    if len(values) and (set(values["unit"].dropna()) - {UNIT}):
        raise StopRule(f"unit other than {UNIT}: {sorted(set(values['unit'].dropna()) - {UNIT})}")
    if len(values) and (set(values["determinand"].astype(str).str.zfill(4)) - {DETERMINAND}):
        raise StopRule("determinand other than 7887")
    meta = pd.DataFrame([{k: p[k] for k in ("wqa_point", "wb_id", "lake_name", "lake_type")} for p in points])
    v = values.merge(meta, on="wqa_point", how="inner").copy()
    v["date"] = pd.to_datetime(v["sample_time"].astype(str).str[:10], errors="coerce")
    v = v.dropna(subset=["date"])
    v = v[v["date"].dt.month.isin(SEASON_MONTHS) & v["date"].dt.year.isin(YEARS)]
    v = v.sort_values(["wqa_point", "sample_time"]).drop_duplicates(["wqa_point", "date"], keep="first")
    parsed = v["result"].map(chl_value)
    v["chl"] = [p[0] for p in parsed]
    v["how"] = [p[1] for p in parsed]
    counts = {k: int((v["how"] == k).sum()) for k in ("measured", "censored", "above", "dropped")}
    v = v[v["how"] != "dropped"].copy()
    v["log_chl"] = np.log10(v["chl"])
    v["season"] = v["date"].dt.year
    v["date"] = v["date"].dt.date
    return v.reset_index(drop=True), counts


def pair(samples: pd.DataFrame, scenes: pd.DataFrame, window: int = PAIR_DAYS) -> pd.DataFrame:
    """Each sample on local date d takes the usable scene at its point (one per UTC date, sat.one_per_date) nearest
    to d within `window` days either side; on a tie, the earlier scene. Adds reading, scene_date, lag_days (scene
    minus sample); NaN reading where there is none."""
    s = scenes[["bw_id", "scene_date", "reading"]].copy()
    s["scene_date"] = pd.to_datetime(s["scene_date"]).dt.date
    by = {k: g for k, g in s.groupby("bw_id")}
    out = []
    for r in samples.itertuples(index=False):
        g = by.get(r.wqa_point)
        hit = None
        if g is not None:
            lag = np.array([(x - r.date).days for x in g["scene_date"]])
            ok = np.abs(lag) <= window
            if ok.any():
                cand = sorted(zip(np.abs(lag[ok]), lag[ok], np.flatnonzero(ok)))
                hit = (g.iloc[cand[0][2]], int(cand[0][1]))
        out.append((hit[0]["reading"], hit[0]["scene_date"], hit[1]) if hit else (np.nan, None, np.nan))
    p = samples.copy()
    p[["reading", "scene_date", "lag_days"]] = pd.DataFrame(out, index=p.index)
    p["reading"] = p["reading"].astype(float)
    return p


# --- scoring ---------------------------------------------------------------------------------------------------
def spearman(x, y) -> float:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return float("nan")
    from scipy.stats import spearmanr
    return float(spearmanr(x[ok], y[ok]).statistic)


def interval(values, levels=(LO, HI)) -> tuple[float, float, int]:
    return sat.boot_interval(np.asarray(values, dtype=float), levels)


def rho_with_interval(rows: pd.DataFrame, draws) -> dict:
    x, y = rows["reading"].to_numpy(), rows["log_chl"].to_numpy()
    r = spearman(x, y)
    lo, hi, bad = interval([spearman(x[i], y[i]) for i in draws])
    return {"rho": r, "L": lo, "U": hi, "draws_without_value": bad,
            "holds": bool(np.isfinite(r) and r >= RHO_MIN and lo > RHO_LOWER)}


def placebo(rows: pd.DataFrame, n: int = N_PLACEBO, seed: int = SEED) -> np.ndarray:
    """Pooled Spearman with readings shuffled within each lake and season (sorted group order)."""
    rng = np.random.default_rng(seed)
    y = rows["log_chl"].to_numpy()
    r = rows["reading"].to_numpy(dtype=float)
    idx = rows.reset_index(drop=True).groupby(["wb_id", "season"], sort=True).indices
    groups = [np.asarray(idx[k]) for k in sorted(idx)]
    out = np.empty(n)
    for i in range(n):
        s = r.copy()
        for g in groups:
            s[g] = r[rng.permutation(g)]
        out[i] = spearman(s, y)
    return out


def placebo_check(real: float, pl: np.ndarray) -> dict:
    p = sat.placebo_passes(real, pl)
    return {**p, "lowest": float(np.nanmin(pl)), "median": float(np.nanmedian(pl)), "highest": float(np.nanmax(pl)),
            "holds": p["passes"]}


def lolo(rows: pd.DataFrame) -> pd.DataFrame:
    """Leave one lake out. For each held-out lake: the fit (ordinary least squares of log10 chlorophyll-a on NDCI)
    and the reference (the mean over the other lakes of each lake's mean log10 chlorophyll-a: every lake counts
    once), both from the other lakes' pairs only. A fold whose training rows hold fewer than 2 distinct readings
    predicts the reference."""
    fit = pd.Series(np.nan, index=rows.index)
    ref = pd.Series(np.nan, index=rows.index)
    for lake in sorted(rows["wb_id"].unique()):
        te = rows["wb_id"] == lake
        tr = rows[~te]
        if not len(tr):
            continue
        r = float(tr.groupby("wb_id")["log_chl"].mean().mean())
        ref[te] = r
        if tr["reading"].nunique() < 2:
            fit[te] = r
            continue
        b, a = np.polyfit(tr["reading"].to_numpy(dtype=float), tr["log_chl"].to_numpy(dtype=float), 1)
        fit[te] = a + b * rows.loc[te, "reading"].to_numpy(dtype=float)
    return pd.DataFrame({"fit": fit, "ref": ref})


def skill(y, fit, ref) -> float:
    y, fit, ref = (np.asarray(a, dtype=float) for a in (y, fit, ref))
    ok = np.isfinite(y) & np.isfinite(fit) & np.isfinite(ref)
    if not ok.any():
        return float("nan")
    m_ref = float(np.mean((ref[ok] - y[ok]) ** 2))
    return float("nan") if m_ref == 0 else 1.0 - float(np.mean((fit[ok] - y[ok]) ** 2)) / m_ref


def skill_with_label(y, fit, ref, clusters, draws=None) -> dict:
    y, fit, ref = (np.asarray(a, dtype=float) for a in (y, fit, ref))
    draws = draws if draws is not None else sat.cluster_draws(np.asarray(clusters))
    d = skill(y, fit, ref)
    lo, hi, bad = interval([skill(y[i], fit[i], ref[i]) for i in draws])
    ok = np.isfinite(y) & np.isfinite(ref)
    return {"skill": d, "L": lo, "U": hi, "draws_without_value": bad, "B": B_SKILL, "H": H_SKILL,
            "mse_fit": float(np.mean((fit[ok] - y[ok]) ** 2)), "mse_ref": float(np.mean((ref[ok] - y[ok]) ** 2)),
            "label": label(d, lo, hi, B_SKILL, H_SKILL)}


def gate(rows: pd.DataFrame) -> dict:
    per_lake = rows.groupby("wb_id").size()
    per_season = rows.groupby("season").size()
    lakes3 = int((per_lake >= GATE_PAIRS_PER_LAKE).sum())
    seasons10 = int((per_season >= GATE_PAIRS_PER_SEASON).sum())
    ok = len(rows) >= GATE_PAIRS and lakes3 >= GATE_LAKES and seasons10 >= GATE_SEASONS
    return {"pairs": int(len(rows)), "lakes": int(per_lake.size), "lakes_with_3": lakes3,
            "seasons_with_10": seasons10, "by_season": {int(k): int(v) for k, v in per_season.items()},
            "judged": bool(ok)}


def by_lake_type(rows: pd.DataFrame, pred: pd.DataFrame) -> dict:
    out = {}
    for t in ("shallow", "deeper"):
        m = (rows["lake_type"] == t).to_numpy()
        n_lakes = int(rows.loc[m, "wb_id"].nunique())
        if n_lakes < GROUP_MIN_LAKES or m.sum() < GROUP_MIN_PAIRS:
            out[t] = {"lakes": n_lakes, "pairs": int(m.sum()), "label": "Too few to judge"}
            continue
        g = skill_with_label(rows["log_chl"].to_numpy()[m], pred["fit"].to_numpy()[m], pred["ref"].to_numpy()[m],
                             rows["wb_id"].to_numpy()[m])
        out[t] = {"lakes": n_lakes, "pairs": int(m.sum()), **g}
    return out


def score(rows: pd.DataFrame) -> dict:
    """Every stated figure. `rows`: paired samples with a reading (columns wb_id, season, lake_type, reading,
    log_chl)."""
    rows = rows.reset_index(drop=True)
    out = {"gate": gate(rows)}
    if len(rows) < 3 or rows["wb_id"].nunique() < 2:
        out["verdict"] = "Too few to judge"
        return out
    clusters = rows["wb_id"].to_numpy()
    draws = sat.cluster_draws(clusters)
    c1 = rho_with_interval(rows, draws)
    c2 = placebo_check(c1["rho"], placebo(rows))
    pred = lolo(rows)
    c3 = skill_with_label(rows["log_chl"], pred["fit"], pred["ref"], clusters, draws)
    c3["holds"] = c3["label"] == "Better"
    groups = by_lake_type(rows, pred)
    harm = [t for t, g in groups.items() if g["label"] in ("Possible harm", "Harm")]
    c4 = {"labels": {t: g["label"] for t, g in groups.items()}, "holds": not harm}
    out.update({"conditions": {"1": c1, "2": c2, "3": c3, "4": c4}, "groups": groups})
    if not out["gate"]["judged"]:
        verdict = "Too few to judge"
    elif all(c["holds"] for c in out["conditions"].values()):
        verdict = "Passes"
    elif c1["holds"] and c2["holds"] and c4["holds"] and c3["label"] == "Promising, not shown":
        verdict = "Fails: near miss (calibration promising, not shown)"
    else:
        verdict = "Fails"
    out["verdict"] = verdict
    return out

