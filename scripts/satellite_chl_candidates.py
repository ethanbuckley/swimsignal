"""Quality-aware satellite chlorophyll candidates against the lab chlorophyll test's baseline, on held-out lakes, seasons
and years (docs/SATELLITE-CHL-CANDIDATES-2026-11.md). Development on seen data: the 2021-2026 pairs were scored in #386
and their signal examined in #626; the fresh check is pairs made after contract 1.4.

    python scripts/satellite_chl_candidates.py prepare --out DIR   # offline: scenes within 3 days of a lab sample, order
    python scripts/satellite_chl_candidates.py read --out DIR      # one capped fetch of B4 and B5 for those scenes
    python scripts/satellite_chl_candidates.py resume --out DIR    # once, after a dropped connection (section 3)
    python scripts/satellite_chl_candidates.py report --out DIR    # offline: readings, candidates, holdouts, words
    python scripts/satellite_chl_candidates.py freeze --out DIR    # offline: the shadow model, only if one is supported

Pixels stay in DIR (scratch). The report writes data/research/satellite_chl_candidates_2026_11.json (values, no pixels);
freeze writes data/research/satellite/chl_shadow_model.v1.json. The lab chlorophyll test's caches are read only. No
estimate here is shown on the site, and nothing says anything about algae, toxins or whether water is safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for d in (HERE / "lake_algae_sat_eval", HERE / "lake_chlorophyll_eval", HERE):
    sys.path.insert(0, str(d))
import chl_protocol as cp  # noqa: E402
import protocol as pr  # noqa: E402
from export_lake_observations import LOW_SIGNAL, low_signal  # noqa: E402
from refresh_lake_observations import CHL, signal_quality  # noqa: E402
from satellite_low_signal_chl import (FEATURES_SHA, LAKES, VALUES_SHA, demeaned, digest,  # noqa: E402
                                      input_files, read_order, test_pairs)

SEED = 20261106
MAX_REQUESTS = 4500
MAX_BYTES = int(2.5 * 1024**3)
WINDOW = 3                                  # composite: scenes within this many days of the sample (E)
PIXEL_GRID = (0.005, 0.010, 0.015, 0.020)   # D: per-pixel B4 + B5 floors, one chosen inside each training fold
MIN_PIXELS = pr.MIN_CORE                    # a pixel-filtered or composite reading needs this many pixels (9)
BRIGHT_FLOOR, IQR_FLOOR = 0.002, 0.005      # floors before logs (brightness can be 0 or below; IQR 0)
FORWARD_TRAIN, FORWARD_TEST = (2021, 2023, 2024), (2025, 2026)
MIN_FIT = {"C": 10}                         # training rows a covariate fit needs; others need 3 with 2 distinct readings
# Support for a shadow log (record, section 3): fixed before any score.
GAIN, HARM = 0.03, -0.05
CANDIDATES = ("B0", "A", "B", "C", "D", "E")
WORDS = {"B0": "baseline: nearest usable scene within a day, core median NDCI, the test's linear calibration",
         "A": "the same, low-signal readings excluded (contract 1.4's rule)",
         "B": "every reading kept, weighted by its measured signal (fitted variance model, inverse-variance blend)",
         "C": "brightness and pixel spread as covariates, with a reading-by-brightness interaction",
         "D": "dark pixels dropped before the median (floor chosen inside each training fold)",
         "E": "composite: median of quality-passing scenes within 3 days"}
HOLDOUTS = ("lake", "season", "forward")
OUTPUT = ROOT / "data/research/satellite_chl_candidates_2026_11.json"
MODEL = ROOT / "data/research/satellite/chl_shadow_model.v1.json"


# ------------------------------------------------------------------ selection (offline)
def population() -> pd.DataFrame:
    """Every lab sample at the test's 38 points in a season with imagery (2021, 2023-2026), one per point and date, with
    the scene the test would pair it with (the nearest usable scene within a day, protocol.one_per_date), or none."""
    cp.check_hash(CHL / "features.parquet", FEATURES_SHA)
    cp.check_hash(CHL / "values.parquet", VALUES_SHA)
    features = pd.read_parquet(CHL / "features.parquet")
    values = pd.read_parquet(CHL / "values.parquet")
    sizes = json.loads((CHL / "sizes.json").read_text())
    points = json.loads(LAKES.read_text())["points"]
    in_test = {k for k, v in sizes.items() if v["in_test"]}
    samples, _ = cp.prepare_samples(values, points)
    s = samples[samples["wqa_point"].isin(in_test) & (samples["season"] != 2022)].reset_index(drop=True)
    scenes = pr.one_per_date(features[features["bw_id"].isin(in_test)])
    paired = cp.pair(s, scenes, cp.PAIR_DAYS)
    sc = scenes.assign(scene_date=pd.to_datetime(scenes["scene_date"]).dt.date)
    rows = paired.merge(sc[["bw_id", "scene_date", "item_id", "tile"]], left_on=["wqa_point", "scene_date"],
                        right_on=["bw_id", "scene_date"], how="left").drop(columns="bw_id")
    rows["cached_reading"] = rows["reading"]
    return rows.drop(columns="reading").sort_values(["wqa_point", "date"]).reset_index(drop=True)


def nearby_scenes(dates_by_point: dict[str, list], window: int = WINDOW) -> list[dict]:
    """Usable scenes (protocol.scene_clear on the cached classification and core) at each point within `window` days
    of one of its sample dates."""
    out = []
    for p in sorted(dates_by_point):
        items = json.loads((CHL / "items" / f"{p}.json").read_text())
        with np.load(CHL / "cores" / f"{p}.npz") as z:
            cores = {k: z[k] for k in z.files}
        dates = [pd.Timestamp(d) for d in dates_by_point[p]]
        for it in items:
            t = it["properties"]["grid:code"]
            core = cores.get(t.replace("-", "_"))
            if core is None or not pr.passes_size_rule(core):
                continue
            d = pd.Timestamp(it["properties"]["datetime"][:10])
            lag = min((abs((d - x).days) for x in dates), default=None)
            f = CHL / "scl" / p / f"{it['id']}.npz"
            if lag is None or lag > window or not f.exists():
                continue
            with np.load(f) as z:
                if not pr.scene_clear(z["scl"], core)[1]:
                    continue
            out.append({"point": p, "item_id": it["id"], "tile": t, "scene_date": str(d.date()), "min_lag": lag})
    return out


def prepare(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(input_files())
    pop = population()
    p1 = test_pairs()
    if set(zip(p1["wqa_point"], p1["item_id"])) != set(zip(*[pop.dropna(subset=["item_id"])[c] for c in ("wqa_point", "item_id")])):
        raise ValueError("the population's paired scenes are not the test's")
    pos = {p["wqa_point"]: (p["lon"], p["lat"]) for p in json.loads(LAKES.read_text())["points"]}
    scenes = nearby_scenes({p: list(g["date"]) for p, g in pop.groupby("wqa_point")})
    for s in scenes:
        s["lon"], s["lat"] = pos[s["point"]]
    paired = set(zip(p1["wqa_point"], p1["item_id"]))
    first = read_order([s for s in scenes if (s["point"], s["item_id"]) in paired], SEED)
    rest = read_order([s for s in scenes if (s["point"], s["item_id"]) not in paired], SEED)
    if len(first) != len(paired):
        raise ValueError("a paired scene is not among the usable scenes within 3 days")
    if fingerprint != digest(input_files()):
        raise ValueError("Inputs changed during selection")
    result = {"fingerprint_sha256": fingerprint, "input_file_count": len(input_files()), "seed": SEED,
              "caps": {"requests": MAX_REQUESTS, "bytes": MAX_BYTES}, "samples": len(pop),
              "paired_samples": int(pop["item_id"].notna().sum()), "scenes": first + rest, "paired_scenes": len(first)}
    (out / "selection.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"{len(pop)} samples ({result['paired_samples']} paired); {len(first) + len(rest)} scenes "
          f"({len(first)} paired first); inputs unchanged; frozen at {out / 'selection.json'}")


# ------------------------------------------------------------------ the capped fetch
def failed(ledger: Path) -> set[str]:
    ids = set()
    for line in ledger.read_text().splitlines():
        if line.strip() and json.loads(line)["status"] is None:
            ids.add(json.loads(line)["url"].split("/")[-2])
    return ids


def read(out: Path, resume: bool = False) -> None:
    """The fetch. `resume`, allowed once and only after a run ended on a dropped connection (no HTTP status): the scenes
    not yet read, the failed one left out, on the same ledger so the caps hold over both runs."""
    import stac
    from net import Capped
    selection = json.loads((out / "selection.json").read_text())
    before = digest(input_files())
    if before != selection["fingerprint_sha256"]:
        raise ValueError("Inputs changed since selection")
    ledger = out / "network.jsonl"
    if ledger.exists() != resume:
        raise ValueError("A network run already exists" if ledger.exists() else "Nothing to resume")
    if resume:
        if (out / "run-resume.json").exists():
            raise ValueError("One resume only")
        if not failed(ledger):
            raise ValueError("The first run did not end on a dropped connection; no resume")
    (out / "bands").mkdir(exist_ok=True)
    skip = failed(ledger) if resume else set()
    scenes = [s for s in selection["scenes"] if s["item_id"] not in skip
              and not (out / "bands" / f"{s['point']}__{s['item_id']}.npz").exists()]
    net = Capped(ledger=ledger, max_requests=MAX_REQUESTS, max_requests_total=MAX_REQUESTS,
                 max_bytes=MAX_BYTES, max_bytes_total=MAX_BYTES)
    items: dict[str, dict] = {}
    done = []
    try:
        for s in scenes:
            if s["point"] not in items:
                items[s["point"]] = {it["id"]: it for it in json.loads((CHL / "items" / f"{s['point']}.json").read_text())}
            it = items[s["point"]][s["item_id"]]
            for asset in ("red", "rededge1"):
                b = it["assets"][asset]["raster:bands"][0]
                if "scale" not in b or "offset" not in b:
                    raise ValueError(f"Missing scale or offset: {s['item_id']} {asset}")
            b4, b5 = stac.site_bands(net, it, s["lon"], s["lat"])
            np.savez_compressed(out / "bands" / f"{s['point']}__{s['item_id']}.npz", b4=b4, b5=b5)
            done.append(s["item_id"])
            if len(done) % 25 == 0 or len(done) == len(scenes):
                print(f"{len(done)}/{len(scenes)} {net.requests} req {net.bytes / 1024**2:.1f} MiB", flush=True)
    finally:
        after = digest(input_files())
        (out / ("run-resume.json" if resume else "run.json")).write_text(json.dumps(
            {"network": net.summary(), "before": before, "after": after, "completed": len(done),
             "scenes_in_run": len(scenes), "skipped_failed": sorted(skip)}, indent=1) + "\n")
        if after != before:
            raise ValueError("Inputs changed during network run")


# ------------------------------------------------------------------ per scene (pure)
def pixel_filtered(scl: np.ndarray, core: np.ndarray, b4: np.ndarray, b5: np.ndarray, floor: float) -> float | None:
    """Median NDCI over clear core pixels whose own B4 + B5 reflectance is at least `floor`; None when the scene is not
    usable (protocol.scene_clear) or fewer than MIN_PIXELS such pixels have a valid index."""
    if not pr.scene_clear(scl, core)[1]:
        return None
    idx = pr.ndci(b4, b5)
    keep = np.isin(scl, pr.CLEAR) & core & np.isfinite(idx) & ((b4 + b5) >= floor)
    return float(np.median(idx[keep])) if keep.sum() >= MIN_PIXELS else None


def scene_values(scl: np.ndarray, core: np.ndarray, b4: np.ndarray, b5: np.ndarray) -> dict:
    """Everything a candidate needs from one scene: the protocol's core reading, contract 1.4's signal measurements and
    mark, and the pixel-filtered readings at each floor of the grid."""
    _, usable, value = pr.scene_reading(scl, core, pr.ndci(b4, b5))
    s = signal_quality(scl, core, b4, b5)
    return {"reading": None if not usable or not np.isfinite(value) else float(value),
            "core_brightness": s["core_brightness"], "index_iqr": s["index_iqr"],
            "low_signal": low_signal(s["core_brightness"], s["index_iqr"]),
            **{f"px_{f:.3f}": pixel_filtered(scl, core, b4, b5, f) for f in PIXEL_GRID}}


def noise_score(brightness, iqr):
    """Higher for a noisier scene: log pixel spread minus log brightness (both floored)."""
    b = np.maximum(np.asarray(brightness, dtype=float), BRIGHT_FLOOR)
    q = np.maximum(np.asarray(iqr, dtype=float), 0) + IQR_FLOOR
    return np.log(q) - np.log(b)


# ------------------------------------------------------------------ the candidates (pure)
def reference(train: pd.DataFrame) -> float:
    """The test's reference: the mean over training lakes of each lake's mean log10 chlorophyll (every lake once)."""
    return float(train.groupby("wb_id")["log_chl"].mean().mean())


def _ols(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 3 or np.unique(x).size < 2:
        return None
    b, a = np.polyfit(x, y, 1)
    return a, b


def _linear(train, test, col, R, keep_train=None, keep_test=None):
    m = train[col].notna() & (keep_train if keep_train is not None else True)
    fit = _ols(train.loc[m, col], train.loc[m, "log_chl"])
    has = test[col].notna() & (keep_test if keep_test is not None else True)
    if fit is None:
        return np.full(len(test), R), np.zeros(len(test), bool)
    pred = np.where(has, fit[0] + fit[1] * test[col].astype(float).fillna(0), R)
    return pred, has.to_numpy()


def fgls(x, y, q, iterations: int = 2):
    """Linear fit with error variance exp(c + g q): ordinary least squares, then log squared residuals regressed on q,
    then weighted least squares with weights 1 / variance; `iterations` rounds. Returns (a, b, c, g)."""
    x, y, q = (np.asarray(v, dtype=float) for v in (x, y, q))
    w = np.ones_like(x)
    X = np.column_stack([np.ones_like(x), x])
    c, g = 0.0, 0.0
    for _ in range(iterations + 1):
        sw = np.sqrt(w)
        beta = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        e2 = (y - X @ beta) ** 2
        g, c = np.polyfit(q, np.log(e2 + 1e-4), 1)
        c += 1.27   # E[log chi-squared(1)] is -1.27: back to a variance
        w = np.exp(-(c + g * q))
    return float(beta[0]), float(beta[1]), float(c), float(g)


def _weighted(train, test, R):
    m = train["x0"].notna() & train["q0"].notna()
    if m.sum() < 3 or train.loc[m, "x0"].nunique() < 2:
        return np.full(len(test), R), np.zeros(len(test), bool)
    a, b, c, g = fgls(train.loc[m, "x0"], train.loc[m, "log_chl"], train.loc[m, "q0"])
    v_ref = float(np.mean((train["log_chl"] - R) ** 2))
    has = (test["x0"].notna() & test["q0"].notna()).to_numpy()
    f = a + b * test["x0"].astype(float).fillna(0).to_numpy()
    v = np.exp(c + g * test["q0"].astype(float).fillna(0).to_numpy())
    blend = (f / v + R / v_ref) / (1 / v + 1 / v_ref)
    return np.where(has, blend, R), has


def _design(d: pd.DataFrame) -> np.ndarray:
    x = d["x0"].astype(float).to_numpy()
    lb = np.log10(np.maximum(d["b0"].astype(float).to_numpy(), BRIGHT_FLOOR))
    return np.column_stack([np.ones_like(x), x, lb, d["q_iqr"].astype(float).to_numpy(), x * lb])


def _covariates(train, test, R):
    m = (train["x0"].notna() & train["b0"].notna() & train["q_iqr"].notna()).to_numpy()
    has = (test["x0"].notna() & test["b0"].notna() & test["q_iqr"].notna()).to_numpy()
    if m.sum() < MIN_FIT["C"]:
        return np.full(len(test), R), np.zeros(len(test), bool)
    beta = np.linalg.lstsq(_design(train[m]), train.loc[m, "log_chl"].to_numpy(dtype=float), rcond=None)[0]
    pred = np.full(len(test), R)
    if has.any():
        pred[has] = _design(test[has]) @ beta
    return pred, has


def groups_for(holdout: str, d: pd.DataFrame) -> np.ndarray:
    return (d["wb_id"] if holdout == "lake" else d["season"]).to_numpy()


def choose_floor(train: pd.DataFrame, holdout: str) -> float:
    """D's floor, chosen inside the training rows only: an inner hold-out by the same grouping as the outer one (lakes
    for the lake holdout, seasons otherwise), the floor with the least mean squared error on log chlorophyll, readings
    missing at that floor predicted by the inner reference; ties go to the earlier floor in the grid."""
    g = groups_for(holdout, train)
    best = None
    for f in PIXEL_GRID:
        col = f"px_{f:.3f}"
        err = []
        for k in np.unique(g):
            tr, te = train[g != k], train[g == k]
            if not len(tr):
                continue
            p, _ = _linear(tr, te, col, reference(tr))
            err.append((p - te["log_chl"].to_numpy()) ** 2)
        mse = float(np.mean(np.concatenate(err))) if err else np.inf
        if best is None or mse < best[1] - 1e-12:
            best = (f, mse)
    return best[0]


def predict(cand: str, train: pd.DataFrame, test: pd.DataFrame, holdout: str) -> tuple[np.ndarray, np.ndarray, dict]:
    """(predictions, has a reading, fold notes) for the test rows, fitted on the training rows only. A row without a
    reading gets the training reference: a candidate that drops readings pays for each one."""
    R = reference(train)
    if cand == "B0":
        p, h = _linear(train, test, "x0", R)
        return p, h, {}
    if cand == "A":
        p, h = _linear(train, test, "x0", R, ~train["flag0"].astype(bool), ~test["flag0"].astype(bool))
        return p, h, {}
    if cand == "B":
        p, h = _weighted(train, test, R)
        return p, h, {}
    if cand == "C":
        p, h = _covariates(train, test, R)
        return p, h, {}
    if cand == "D":
        f = choose_floor(train, holdout)
        p, h = _linear(train, test, f"px_{f:.3f}", R)
        return p, h, {"floor": f}
    if cand == "E":
        p, h = _linear(train, test, "xe", R)
        return p, h, {}
    raise ValueError(cand)


def folds(holdout: str, d: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    if holdout == "forward":
        tr = d["season"].isin(FORWARD_TRAIN).to_numpy()
        return [(tr, d["season"].isin(FORWARD_TEST).to_numpy())]
    g = groups_for(holdout, d)
    return [(g != k, g == k) for k in np.unique(g)]


def run_holdout(d: pd.DataFrame, holdout: str) -> dict:
    """Out-of-fold predictions of every candidate and of the reference (and, for seasons and years, the lake's own
    training mean, for context), over the rows the holdout tests."""
    d = d.reset_index(drop=True)
    n = len(d)
    preds = {c: np.full(n, np.nan) for c in CANDIDATES}
    has = {c: np.zeros(n, bool) for c in CANDIDATES}
    ref, lake_ref = np.full(n, np.nan), np.full(n, np.nan)
    notes: dict[str, list] = {c: [] for c in CANDIDATES}
    for tr, te in folds(holdout, d):
        train, test = d[tr], d[te]
        R = reference(train)
        ref[te] = R
        lm = train.groupby("wb_id")["log_chl"].mean()
        lake_ref[te] = test["wb_id"].map(lm).fillna(R).to_numpy()
        for c in CANDIDATES:
            p, h, note = predict(c, train, test, holdout)
            preds[c][te], has[c][te] = p, h
            if note:
                notes[c].append(note)
    tested = ~np.isnan(ref)
    return {"rows": tested, "pred": preds, "has": has, "ref": ref, "lake_ref": lake_ref, "notes": notes}


# ------------------------------------------------------------------ measures (pure)
def _skill(y, p, r):
    m = float(np.mean((r - y) ** 2))
    return float("nan") if m == 0 else 1 - float(np.mean((p - y) ** 2)) / m


def _within(wb, y, p):
    f = pd.DataFrame({"wb_id": wb, "log_chl": y, "pred": p})
    return cp.spearman(*demeaned(f, "pred"))


def figures(wb, y, p, r) -> dict:
    return {"skill": _skill(y, p, r), "rmse": float(np.sqrt(np.mean((p - y) ** 2))),
            "spearman": cp.spearman(p, y), "within_lake": _within(wb, y, p)}


def measures(d: pd.DataFrame, res: dict) -> dict:
    """For each candidate: skill against the reference, root mean squared error on log10 chlorophyll, pooled and
    within-lake Spearman of prediction with chlorophyll, coverage; cluster-bootstrap intervals by lake (the test's 2,000
    draws), and the same four as paired differences from the baseline."""
    m = res["rows"]
    wb, y, r = d["wb_id"].to_numpy()[m], d["log_chl"].to_numpy(dtype=float)[m], res["ref"][m]
    draws = pr.cluster_draws(wb)
    base = res["pred"]["B0"][m]
    out = {"rows": int(m.sum()), "lakes": int(len(set(wb))),
           "reference_rmse": float(np.sqrt(np.mean((r - y) ** 2))),
           "lake_mean_skill": _skill(y, res["lake_ref"][m], r)}
    boot_base = [figures(wb[i], y[i], base[i], r[i]) for i in draws]
    for c in CANDIDATES:
        p = res["pred"][c][m]
        f = figures(wb, y, p, r)
        boot = [figures(wb[i], y[i], p[i], r[i]) for i in draws] if c != "B0" else boot_base
        block = {"coverage": round(float(res["has"][c][m].mean()), 4), "readings": int(res["has"][c][m].sum())}
        for k in f:
            lo, hi, bad = cp.interval([b[k] for b in boot])
            block[k] = {"value": f[k], "L": lo, "U": hi, "draws_without_value": bad}
        if c != "B0":
            fb = figures(wb, y, base, r)
            block["vs_B0"] = {}
            for k in f:
                lo, hi, bad = cp.interval([b[k] - bb[k] for b, bb in zip(boot, boot_base)])
                block["vs_B0"][k] = {"d": f[k] - fb[k], "L": lo, "U": hi, "draws_without_value": bad}
        if res["notes"][c]:
            floors = [n["floor"] for n in res["notes"][c]]
            block["floors_chosen"] = {f"{k:.3f}": floors.count(k) for k in PIXEL_GRID}
        out[c] = block
    return out


def support(results: dict) -> dict:
    """The pre-stated conditions, per candidate and population: (1) on held-out lakes the skill gain over the baseline
    is at least GAIN and its paired interval's lower end above HARM; (2) on held-out seasons and on the forward years the
    gain is at least 0. Supported if all hold on the paired population, or (E, whose reason is coverage) on every sample."""
    out = {}
    for c in CANDIDATES[1:]:
        per = {}
        for pop in ("paired", "all"):
            lk = results[pop]["lake"][c]["vs_B0"]["skill"]
            ok1 = lk["d"] >= GAIN and lk["L"] > HARM
            ok2 = all(results[pop][h][c]["vs_B0"]["skill"]["d"] >= 0 for h in ("season", "forward"))
            per[pop] = {"lake_gain": lk["d"], "lake_gain_L": lk["L"], "condition_1": bool(ok1),
                        "season_gain": results[pop]["season"][c]["vs_B0"]["skill"]["d"],
                        "forward_gain": results[pop]["forward"][c]["vs_B0"]["skill"]["d"], "condition_2": bool(ok2)}
        sup = (per["paired"]["condition_1"] and per["paired"]["condition_2"]) or \
              (c == "E" and per["all"]["condition_1"] and per["all"]["condition_2"])
        out[c] = {**per, "supported": bool(sup)}
    return out


def words(results: dict, sup: dict) -> list[str]:
    out = []
    for c in CANDIDATES[1:]:
        s, lk = sup[c], results["paired"]["lake"][c]
        line = (f"{c} ({WORDS[c]}): held-out lakes, paired samples, skill {lk['skill']['value']:+.3f} against the "
                f"baseline's {results['paired']['lake']['B0']['skill']['value']:+.3f}, gain {lk['vs_B0']['skill']['d']:+.3f} "
                f"[{lk['vs_B0']['skill']['L']:+.3f}, {lk['vs_B0']['skill']['U']:+.3f}], coverage {lk['coverage']:.0%}; ")
        if s["supported"]:
            where = "every sample" if not (s["paired"]["condition_1"] and s["paired"]["condition_2"]) else "the paired samples"
            line += f"supported for a shadow log (conditions met on {where})."
        else:
            why = []
            p = s["paired"]
            if not p["condition_1"]:
                why.append(f"condition 1 (gain {p['lake_gain']:+.3f}, lower end {p['lake_gain_L']:+.3f}; needs "
                           f"{GAIN:+.2f} and above {HARM:+.2f})")
            if not p["condition_2"]:
                why.append(f"condition 2 (seasons {p['season_gain']:+.3f}, forward {p['forward_gain']:+.3f}; needs 0 or more)")
            line += "not supported: fails " + " and ".join(why) + "."
        out.append(line)
    chosen = [c for c in CANDIDATES[1:] if sup[c]["supported"]]
    out.append(("Shadow log: the baseline and " + ", ".join(chosen) + ", from frozen coefficients, beside each new reading.")
               if chosen else "No candidate is supported: the code stays runnable, and no shadow model is written.")
    out.append("All of this is development on seen 2021-2026 pairs; the fresh check is pairs made after contract 1.4. "
               "Nothing here is a claim about algae, toxins or whether water is safe, or a chlorophyll measurement.")
    return out


# ------------------------------------------------------------------ report
def _arrays(point: str, item_id: str, tile: str, npz: Path, items: dict):
    it = items[item_id]
    with np.load(CHL / "scl" / point / f"{item_id}.npz") as z:
        scl = z["scl"]
    with np.load(CHL / "cores" / f"{point}.npz") as z:
        core = z[tile.replace("-", "_")]
    with np.load(npz) as z:
        b4 = pr.b4_to_20m(pr.reflectance(z["b4"], it["assets"]["red"]["raster:bands"][0]))
        b5 = pr.reflectance(z["b5"], it["assets"]["rededge1"]["raster:bands"][0])
    return scl, core, b4, b5


def scene_table(out: Path, selection: dict) -> pd.DataFrame:
    features = pd.read_parquet(CHL / "features.parquet")
    cached = {(r.bw_id, r.item_id): r.reading for r in features.itertuples() if r.usable and np.isfinite(r.reading)}
    rows, items = [], {}
    for s in selection["scenes"]:
        npz = out / "bands" / f"{s['point']}__{s['item_id']}.npz"
        if not npz.exists():
            rows.append({**s, "read": False})
            continue
        if s["point"] not in items:
            items[s["point"]] = {it["id"]: it for it in json.loads((CHL / "items" / f"{s['point']}.json").read_text())}
        v = scene_values(*_arrays(s["point"], s["item_id"], s["tile"], npz, items[s["point"]]))
        c = cached.get((s["point"], s["item_id"]))
        if c is not None and (v["reading"] is None or abs(v["reading"] - c) > 1e-6):
            raise ValueError(f"recomputed reading differs from the cache: {s['point']} {s['item_id']}")
        rows.append({**s, "read": True, "cached": c, **v})
    return pd.DataFrame(rows)


def sample_rows(pop: pd.DataFrame, scenes: pd.DataFrame) -> pd.DataFrame:
    """One row per lab sample with every candidate's inputs: the paired scene's values (x0, flag0, b0, q_iqr, q0 and the
    pixel-filtered readings) and the composite of quality-passing scenes within WINDOW days (xe, n_e)."""
    read = scenes[scenes["read"]].set_index(["point", "item_id"])
    d = pop.copy()
    cols = ["reading", "low_signal", "core_brightness", "index_iqr", *[f"px_{f:.3f}" for f in PIXEL_GRID]]
    vals = [read.loc[(p, i), cols] if isinstance(i, str) and (p, i) in read.index else pd.Series({k: None for k in cols})
            for p, i in zip(d["wqa_point"], d["item_id"])]
    v = pd.DataFrame(vals).reset_index(drop=True)
    d["paired_scene_read"] = [isinstance(i, str) and (p, i) in read.index for p, i in zip(d["wqa_point"], d["item_id"])]
    d["x0"] = pd.to_numeric(v["reading"], errors="coerce")
    d["flag0"] = v["low_signal"].fillna(False).astype(bool)
    d["b0"] = pd.to_numeric(v["core_brightness"], errors="coerce")
    d["q_iqr"] = pd.to_numeric(v["index_iqr"], errors="coerce")
    d["q0"] = noise_score(d["b0"].fillna(np.nan), d["q_iqr"].fillna(np.nan))
    d.loc[d["b0"].isna() | d["q_iqr"].isna(), "q0"] = np.nan
    for f in PIXEL_GRID:
        d[f"px_{f:.3f}"] = pd.to_numeric(v[f"px_{f:.3f}"], errors="coerce")
    ok = read[(read["low_signal"] == False) & read["reading"].notna()].reset_index()  # noqa: E712
    ok["scene_date"] = pd.to_datetime(ok["scene_date"])
    by_point = {p: g for p, g in ok.groupby("point")}
    xe, ne = [], []
    for p, day in zip(d["wqa_point"], pd.to_datetime(d["date"])):
        g = by_point.get(p)
        near = g[(g["scene_date"] - day).abs().dt.days <= WINDOW]["reading"] if g is not None else []
        xe.append(float(np.median(near)) if len(near) else np.nan)
        ne.append(int(len(near)))
    d["xe"], d["n_e"] = xe, ne
    return d


def report(out: Path) -> None:
    selection = json.loads((out / "selection.json").read_text())
    runs = [json.loads((out / f).read_text()) for f in ("run.json", "run-resume.json") if (out / f).exists()]
    now = digest(input_files())
    scenes = scene_table(out, selection)
    pop = population()
    d = sample_rows(pop, scenes)
    paired = d[d["item_id"].notna() & d["paired_scene_read"]].reset_index(drop=True)
    results = {"paired": {}, "all": {}}
    for name, frame in (("paired", paired), ("all", d)):
        for h in HOLDOUTS:
            results[name][h] = measures(frame, run_holdout(frame, h))
    sup = support(results)
    read_scenes = scenes[scenes["read"]]
    doc = {
        "description": "Development on seen data: quality-aware candidates for relating Sentinel-2 NDCI to EA lab "
                       "chlorophyll, against the lab chlorophyll test's baseline, on held-out lakes, seasons and years. "
                       "Not a chlorophyll measurement, not shown on the site, and not an algae, toxin or safety estimate.",
        "source": "Contains modified Copernicus Sentinel data 2021-2026. Sentinel-2 L2A via Earth Search; the lab "
                  "chlorophyll test's scene-classification cache and cores; EA Water Quality Archive chlorophyll "
                  "(determinand 7887, acetone extract, spectrophotometric, phaeopigment correction not stated), "
                  "Open Government Licence v3.0.",
        "protocol": "docs/SATELLITE-CHL-CANDIDATES-2026-11.md",
        "settings": {"window_days": WINDOW, "pixel_grid": list(PIXEL_GRID), "min_pixels": MIN_PIXELS,
                     "low_signal": LOW_SIGNAL, "forward": {"train": list(FORWARD_TRAIN), "test": list(FORWARD_TEST)},
                     "gain": GAIN, "harm": HARM, "seed": SEED},
        "candidates": WORDS,
        "input_fingerprint_sha256": selection["fingerprint_sha256"],
        "fingerprint_unchanged": all(v == selection["fingerprint_sha256"] for r in runs for v in (r["before"], r["after"]))
                                 and now == selection["fingerprint_sha256"],
        "runs": runs, "caps": selection["caps"],
        "network": {"requests": runs[-1]["network"]["requests_all_runs"], "bytes": runs[-1]["network"]["bytes_all_runs"]},
        "scenes": {"selected": len(scenes), "read": int(scenes["read"].sum()),
                   "matched_cache": int(read_scenes["cached"].notna().sum()),
                   "low_signal": int(read_scenes["low_signal"].fillna(False).astype(bool).sum())},
        "samples": {"all": len(d), "paired": len(paired), "paired_scene_unread": int((d["item_id"].notna() & ~d["paired_scene_read"]).sum()),
                    "with_composite": int(d["xe"].notna().sum())},
        "results": results, "support": sup, "words": words(results, sup),
        "sample_rows": json.loads(d.drop(columns=["tile"], errors="ignore").to_json(orient="records", date_format="iso")),
    }
    OUTPUT.write_text(json.dumps(doc, indent=1, default=_json_default) + "\n")
    print("\n".join(doc["words"]))


# ------------------------------------------------------------------ freeze (only after a supported result)
def freeze(out: Path) -> None:
    doc = json.loads(OUTPUT.read_text())
    chosen = [c for c in CANDIDATES[1:] if doc["support"][c]["supported"]]
    if not chosen:
        raise SystemExit("No candidate is supported; no shadow model is written.")
    selection = json.loads((out / "selection.json").read_text())
    d = sample_rows(population(), scene_table(out, selection))
    paired = d[d["item_id"].notna() & d["paired_scene_read"]].reset_index(drop=True)
    models = {"B0": dict(zip(("a", "b"), _ols(paired["x0"].dropna(), paired.loc[paired["x0"].notna(), "log_chl"])))}
    ref = reference(paired)
    for c in chosen:
        if c == "A":
            m = paired["x0"].notna() & ~paired["flag0"]
            models[c] = dict(zip(("a", "b"), _ols(paired.loc[m, "x0"], paired.loc[m, "log_chl"])))
        elif c == "B":
            m = paired["x0"].notna() & paired["q0"].notna()
            a, b, cc, g = fgls(paired.loc[m, "x0"], paired.loc[m, "log_chl"], paired.loc[m, "q0"])
            models[c] = {"a": a, "b": b, "c": cc, "g": g, "reference": ref,
                         "reference_variance": float(np.mean((paired["log_chl"] - ref) ** 2))}
        elif c == "C":
            m = (paired["x0"].notna() & paired["b0"].notna() & paired["q_iqr"].notna()).to_numpy()
            beta = np.linalg.lstsq(_design(paired[m]), paired.loc[m, "log_chl"].to_numpy(dtype=float), rcond=None)[0]
            models[c] = {"beta": [float(v) for v in beta], "terms": ["1", "x", "log10_brightness", "iqr", "x*log10_brightness"]}
        elif c == "D":
            f = choose_floor(paired, "lake")
            col = f"px_{f:.3f}"
            m = paired[col].notna()
            models[c] = {"floor": f, **dict(zip(("a", "b"), _ols(paired.loc[m, col], paired.loc[m, "log_chl"])))}
        elif c == "E":
            m = d["xe"].notna()
            models[c] = {"window_days": WINDOW, **dict(zip(("a", "b"), _ols(d.loc[m, "xe"], d.loc[m, "log_chl"])))}
    model = {"schema": "swimsignal.lake-chl-shadow-model", "version": "1.0.0",
             "description": "Frozen research shadow model: coefficients relating a reading to log10 of the EA's "
                            "acetone-extract chlorophyll result (determinand 7887), fitted on seen 2021-2026 pairs, "
                            "for prospective comparison only. Not a measurement, not shown on the site, not validated.",
             "protocol": "docs/SATELLITE-CHL-CANDIDATES-2026-11.md", "fitted_on": {"paired": len(paired), "all": len(d)},
             "low_signal": LOW_SIGNAL, "bright_floor": BRIGHT_FLOOR, "iqr_floor": IQR_FLOOR, "min_pixels": MIN_PIXELS,
             "models": models}
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_text(json.dumps(model, indent=1) + "\n")
    print(json.dumps(model, indent=1))


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("step", choices=("prepare", "read", "resume", "report", "freeze"))
    a.add_argument("--out", type=Path, required=True)
    o = a.parse_args()
    {"prepare": lambda: prepare(o.out), "read": lambda: read(o.out), "resume": lambda: read(o.out, resume=True),
     "report": lambda: report(o.out), "freeze": lambda: freeze(o.out)}[o.step]()


if __name__ == "__main__":
    main()
