"""Low-signal readings against lab chlorophyll: does contract 1.4's low-signal rule change the NDCI-to-chlorophyll
relationship in the lab chlorophyll test's pairs? (docs/SATELLITE-LOW-SIGNAL-CHLOROPHYLL-2026-11.md). Exploratory, on
seen pairs; the lab chlorophyll test's caches (PR #386) are read only.

    python scripts/satellite_low_signal_chl.py prepare --out DIR    # offline: the test's pairs, their scenes, the order
    python scripts/satellite_low_signal_chl.py read --out DIR       # one capped fetch of B4 and B5 for those scenes
    python scripts/satellite_low_signal_chl.py resume --out DIR     # amendment 1: the scenes the first run never reached
    python scripts/satellite_low_signal_chl.py report --out DIR [--partial JSON]   # offline: signal, flag, measures, words

Pixels stay in DIR (scratch). The report writes data/research/satellite_low_signal_chl_2026_11.json (values, no pixels).
The rule, its thresholds and the inner-core reading are the exporter's and refresher's (contract 1.4), imported, so this
check cannot drift from what the site shows. Nothing here says anything about algae, toxins, whether water is safe, or
whether the test passed: its verdict is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for d in (HERE / "lake_algae_sat_eval", HERE / "lake_chlorophyll_eval", HERE):
    sys.path.insert(0, str(d))
import chl_protocol as cp  # noqa: E402  (#386's rules: samples, pairing, Spearman, intervals, conditions)
import protocol as pr  # noqa: E402  (#377's pixel rules and cluster draws)
from export_lake_observations import LOW_SIGNAL, low_signal  # noqa: E402  (contract 1.4's display rule)
from refresh_lake_observations import CHL, signal_quality  # noqa: E402  (contract 1.4's measurements)

SEED = 20261105
MAX_REQUESTS = 1000
MAX_BYTES = 600 * 1024**2
# The committed hashes of the lab chlorophyll test's inputs (docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10.md, run log).
FEATURES_SHA = "58bce46681d7b9dd8e1cb2851528dd38f2d28bee0b5ed4d9095f367464af9f44"
VALUES_SHA = "8327417da5c5e512fd81cdbf4f2e71239560573b57e257240a46549b9f2648fa"
LAKES = ROOT / "docs/LAKE-CHLOROPHYLL-NDCI-TEST-2026-10-lakes.json"
OUTPUT = ROOT / "data/research/satellite_low_signal_chl_2026_11.json"
# Descriptive sizes, fixed before the fetch (the record, section 3). Not significance thresholds.
SMALL, LARGE = 0.03, 0.10          # a change in Spearman below SMALL is "no change"; at or above LARGE "large"
RARE, FREQUENT = 0.10, 0.30        # the flagged share of pairs: below RARE "rare"; above FREQUENT "frequent"
VARIANTS = {"A": ("reading", False), "B": ("reading", True), "C": ("inner_ndci", False), "D": ("inner_ndci", True)}
VARIANT_WORDS = {"A": "core reading, every pair (the test's rows)", "B": "core reading, unflagged pairs",
                 "C": "inner-core reading, every pair with one", "D": "inner-core reading, unflagged pairs with one"}
PAIR_COLUMNS = ["wqa_point", "wb_id", "lake_name", "lake_type", "season", "date", "chl", "how", "log_chl", "reading",
                "scene_date", "lag_days", "item_id", "tile", "clear_core", "n_core", "lon", "lat"]


# ------------------------------------------------------------------ the caches, read only
def input_files() -> list[Path]:
    return [CHL / "features.parquet", CHL / "features.sha256", CHL / "values.parquet", CHL / "values.sha256",
            CHL / "score.json", CHL / "sizes.json", *CHL.glob("cores/*.npz"), *CHL.glob("items/*.json"),
            *CHL.glob("scl/*/*.npz")]


def digest(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(CHL)).encode())
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
    return h.hexdigest()


def test_pairs() -> pd.DataFrame:
    """The lab chlorophyll test's paired rows, made again by its own functions from its cached inputs: one sample per
    point and date with a usable scene within a day (chl_protocol.prepare_samples, protocol.one_per_date,
    chl_protocol.pair), with the scene that gave each reading. Checked against the test's score.json."""
    cp.check_hash(CHL / "features.parquet", FEATURES_SHA)
    cp.check_hash(CHL / "values.parquet", VALUES_SHA)
    features = pd.read_parquet(CHL / "features.parquet")
    values = pd.read_parquet(CHL / "values.parquet")
    sizes = json.loads((CHL / "sizes.json").read_text())
    points = json.loads(LAKES.read_text())["points"]
    in_test = {k for k, v in sizes.items() if v["in_test"]}
    samples, _ = cp.prepare_samples(values, points)
    s_in = samples[samples["wqa_point"].isin(in_test)].reset_index(drop=True)
    scenes = pr.one_per_date(features[features["bw_id"].isin(in_test)])
    paired = cp.pair(s_in, scenes, cp.PAIR_DAYS)
    rows = paired[paired["reading"].notna()].reset_index(drop=True)
    sc = scenes.assign(scene_date=pd.to_datetime(scenes["scene_date"]).dt.date)
    rows = rows.merge(sc[["bw_id", "scene_date", "item_id", "tile", "clear_core", "n_core"]],
                      left_on=["wqa_point", "scene_date"], right_on=["bw_id", "scene_date"], how="left")
    if rows["item_id"].isna().any():
        raise ValueError("a paired reading has no scene")
    pos = {p["wqa_point"]: (p["lon"], p["lat"]) for p in points}
    rows["lon"] = rows["wqa_point"].map(lambda p: pos[p][0])
    rows["lat"] = rows["wqa_point"].map(lambda p: pos[p][1])
    rows["lag_days"] = rows["lag_days"].astype(int)
    rows = rows[PAIR_COLUMNS].sort_values(["wqa_point", "date"]).reset_index(drop=True)
    score = json.loads((CHL / "score.json").read_text())["result"]
    if len(rows) != score["gate"]["pairs"]:
        raise ValueError(f"{len(rows)} pairs, the test had {score['gate']['pairs']}")
    rho = cp.spearman(rows["reading"], rows["log_chl"])
    if abs(rho - score["conditions"]["1"]["rho"]) > 1e-9:
        raise ValueError(f"pooled Spearman {rho}, the test had {score['conditions']['1']['rho']}")
    return rows


def read_order(scenes: list[dict], seed: int = SEED) -> list[dict]:
    """Points in a seeded order, each point's scenes in a seeded order, one per point in turn: a run the cap stops
    early still holds scenes from every point. `scenes` rows need `point` and `item_id`; duplicates are dropped."""
    rng = np.random.default_rng(seed)
    by_point: dict[str, list[dict]] = {}
    seen = set()
    for s in sorted(scenes, key=lambda s: (s["point"], s["item_id"])):
        if (s["point"], s["item_id"]) in seen:
            continue
        seen.add((s["point"], s["item_id"]))
        by_point.setdefault(s["point"], []).append(s)
    points = [sorted(by_point)[i] for i in rng.permutation(len(by_point))]
    queues = {p: [by_point[p][i] for i in rng.permutation(len(by_point[p]))] for p in points}
    out = []
    while any(queues.values()):
        for p in points:
            if queues[p]:
                out.append(queues[p].pop(0))
    return out


def prepare(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(input_files())
    rows = test_pairs()
    scenes = read_order([{"point": r.wqa_point, "item_id": r.item_id, "tile": r.tile, "lon": r.lon, "lat": r.lat,
                          "cached": float(r.reading)} for r in rows.itertuples(index=False)])
    if fingerprint != digest(input_files()):
        raise ValueError("Inputs changed during selection")
    pairs = rows.assign(date=rows["date"].astype(str), scene_date=rows["scene_date"].astype(str))
    result = {"fingerprint_sha256": fingerprint, "input_file_count": len(input_files()), "seed": SEED,
              "caps": {"requests": MAX_REQUESTS, "bytes": MAX_BYTES}, "pairs": pairs.to_dict("records"),
              "scenes": scenes}
    (out / "selection.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"{len(rows)} pairs at {rows['wb_id'].nunique()} lakes, {len(scenes)} scenes at "
          f"{len({s['point'] for s in scenes})} points; inputs unchanged; frozen at {out / 'selection.json'}")


# ------------------------------------------------------------------ the one capped fetch
def failed(ledger: Path) -> set[str]:
    """Item ids of band reads the ledger holds with no status (a dropped connection): never requested again."""
    ids = set()
    for line in ledger.read_text().splitlines():
        if line.strip() and json.loads(line)["status"] is None:
            ids.add(json.loads(line)["url"].split("/")[-2])
    return ids


def read(out: Path, resume: bool = False) -> None:
    """`read`: the one capped fetch. `resume` (amendment 1 of the record): a second run over the scenes the first run
    never attempted, on the same ledger so the request and byte caps hold over both runs together; the scene whose read
    failed is left out, so no request is retried. Refuses a third run."""
    import stac
    from net import Capped
    selection = json.loads((out / "selection.json").read_text())
    before = digest(input_files())
    if before != selection["fingerprint_sha256"]:
        raise ValueError("Inputs changed since selection")
    ledger = out / "network.jsonl"
    if ledger.exists() != resume:
        raise ValueError("A network run already exists; no retry under this protocol" if ledger.exists()
                         else "Nothing to resume: no first run")
    if resume and (out / "run-resume.json").exists():
        raise ValueError("A resumed run already exists; the amendment allows one")
    (out / "bands").mkdir(exist_ok=True)
    skip = failed(ledger) if resume else set()
    scenes = [s for s in selection["scenes"] if s["item_id"] not in skip
              and not (out / "bands" / f"{s['point']}__{s['item_id']}.npz").exists()] if resume else selection["scenes"]
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
            print(f"{len(done)}/{len(scenes)} {s['point']} {s['item_id']} "
                  f"{net.requests} req {net.bytes / 1024**2:.1f} MiB", flush=True)
    finally:
        after = digest(input_files())
        (out / ("run-resume.json" if resume else "run.json")).write_text(json.dumps(
            {"network": net.summary(), "before": before, "after": after, "completed": len(done),
             "scenes_in_run": len(scenes), "skipped_failed": sorted(skip)}, indent=1) + "\n")
        if after != before:
            raise ValueError("Inputs changed during network run")


# ------------------------------------------------------------------ per pair: the reading's signal and the flag
def scene_signal(point: str, item_id: str, tile: str, npz: Path) -> dict:
    """The reading made again from the fetched bands and the cached scene classification and core (it must equal the
    cached one), with contract 1.4's measurements (refresh_lake_observations.signal_quality) and display rule
    (export_lake_observations.low_signal)."""
    items = {it["id"]: it for it in json.loads((CHL / "items" / f"{point}.json").read_text())}
    it = items[item_id]
    with np.load(CHL / "scl" / point / f"{item_id}.npz") as z:
        scl = z["scl"]
    with np.load(CHL / "cores" / f"{point}.npz") as z:
        core = z[tile.replace("-", "_")]
    with np.load(npz) as z:
        b4 = pr.b4_to_20m(pr.reflectance(z["b4"], it["assets"]["red"]["raster:bands"][0]))
        b5 = pr.reflectance(z["b5"], it["assets"]["rededge1"]["raster:bands"][0])
    _, usable, value = pr.scene_reading(scl, core, pr.ndci(b4, b5))
    signal = signal_quality(scl, core, b4, b5)
    return {"reading_recomputed": None if not usable or not np.isfinite(value) else round(float(value), 6),
            "processing_baseline": it["properties"].get("s2:processing_baseline"), **signal,
            "dark": signal["core_brightness"] is not None and signal["core_brightness"] < LOW_SIGNAL["brightness_below"],
            "spread": signal["index_iqr"] is not None and signal["index_iqr"] >= LOW_SIGNAL["iqr_at_least"],
            "low_signal": low_signal(signal["core_brightness"], signal["index_iqr"])}


# ------------------------------------------------------------------ the measures (pure)
def demeaned(rows: pd.DataFrame, reading: str) -> tuple[np.ndarray, np.ndarray]:
    """Reading and log10 chlorophyll with each lake's mean taken off, at lakes with at least two pairs; NaN elsewhere.
    Rank agreement between these is the within-lake Spearman: it cannot come from one lake being greener than another."""
    g = rows.groupby("wb_id")
    keep = (g[reading].transform("size") >= 2) & rows[reading].notna()
    x = (rows[reading] - g[reading].transform("mean")).where(keep)
    y = (rows["log_chl"] - g["log_chl"].transform("mean")).where(keep)
    return x.to_numpy(dtype=float), y.to_numpy(dtype=float)


def within_lake_rho(rows: pd.DataFrame, reading: str = "reading") -> float:
    return cp.spearman(*demeaned(rows, reading))


def _rho_block(x, y, draws) -> dict:
    lo, hi, bad = cp.interval([cp.spearman(x[i], y[i]) for i in draws])
    return {"rho": cp.spearman(x, y), "L": lo, "U": hi, "draws_without_value": bad,
            "pairs": int((np.isfinite(x) & np.isfinite(y)).sum())}


def measures(rows: pd.DataFrame, reading: str = "reading") -> dict:
    """On the pairs with a value of `reading`: the pooled Spearman with the test's cluster-bootstrap interval (its
    primary statistic, condition 1), the within-lake Spearman with the same draws, the per-lake Spearmans, and the
    test's four conditions recomputed on these rows as description (its verdict is not re-decided here)."""
    rows = rows[rows[reading].notna()].reset_index(drop=True)
    out = {"reading": reading, "pairs": int(len(rows)), "lakes": int(rows["wb_id"].nunique())}
    if len(rows) < 3 or rows["wb_id"].nunique() < 2:
        return out
    draws = pr.cluster_draws(rows["wb_id"].to_numpy())
    x, y = rows[reading].to_numpy(dtype=float), rows["log_chl"].to_numpy(dtype=float)
    out["pooled"] = _rho_block(x, y, draws)
    out["within_lake"] = _rho_block(*demeaned(rows, reading), draws)
    per = {k: cp.spearman(g[reading], g["log_chl"]) for k, g in rows.groupby("wb_id") if len(g) >= 3}
    vals = [v for v in per.values() if np.isfinite(v)]
    out["per_lake"] = {"lakes_with_3": len(per), "median_rho": float(np.median(vals)) if vals else None,
                       "positive": int(sum(v > 0 for v in vals)), "with_value": len(vals)}
    s = cp.score(rows.assign(reading=rows[reading])[["wb_id", "season", "lake_type", "reading", "log_chl"]])
    out["test_conditions"] = {k: s[k] for k in ("gate", "conditions", "groups") if k in s}
    return out


def paired_difference(rows: pd.DataFrame, keep, reading_a: str, reading_b: str) -> dict:
    """B minus A, paired: every cluster-bootstrap draw over the lakes of the A rows (those with `reading_a`) scores A
    on the drawn pairs with `reading_a` and B on the drawn pairs where `keep` holds with `reading_b`, so the interval
    is of the difference itself, not of two overlapping intervals."""
    rows = rows.reset_index(drop=True)
    a_ok = rows[reading_a].notna().to_numpy()
    b_ok = np.asarray(keep, dtype=bool) & rows[reading_b].notna().to_numpy()
    a = rows[a_ok].reset_index(drop=True)
    draws = pr.cluster_draws(a["wb_id"].to_numpy())
    y = a["log_chl"].to_numpy(dtype=float)
    xa = a[reading_a].to_numpy(dtype=float)
    xb = np.where(b_ok[a_ok], a[reading_b].to_numpy(dtype=float), np.nan)
    wxa, wya = demeaned(a, reading_a)
    b = a[b_ok[a_ok]].reset_index(drop=True)
    wxb_b, wyb_b = demeaned(b, reading_b)
    wxb, wyb = np.full(len(a), np.nan), np.full(len(a), np.nan)
    wxb[b_ok[a_ok]], wyb[b_ok[a_ok]] = wxb_b, wyb_b
    out = {"pairs_a": int(a_ok.sum()), "pairs_b": int(b_ok.sum())}
    for name, (x1, y1, x2, y2) in {"pooled": (xa, y, xb, y), "within_lake": (wxa, wya, wxb, wyb)}.items():
        d = [cp.spearman(x2[i], y2[i]) - cp.spearman(x1[i], y1[i]) for i in draws]
        lo, hi, bad = cp.interval(d)
        out[name] = {"d": cp.spearman(x2, y2) - cp.spearman(x1, y1), "L": lo, "U": hi, "draws_without_value": bad}
    return out


def flag_share(rows: pd.DataFrame) -> dict:
    f = rows["low_signal"].fillna(False).astype(bool)
    dark, spread = rows["dark"].astype(bool), rows["spread"].astype(bool)
    by_type = {}
    for t in ("shallow", "deeper", None):
        m = rows["lake_type"].isna() if t is None else rows["lake_type"] == t
        by_type[t or "no_depth"] = {"pairs": int(m.sum()), "flagged": int((f & m).sum())}
    per_lake = rows.groupby("wb_id").apply(lambda g: (len(g), int((~g["low_signal"].fillna(False).astype(bool)).sum())),
                                           include_groups=False)
    return {"pairs": int(len(rows)), "flagged": int(f.sum()), "share": round(float(f.mean()), 4) if len(rows) else None,
            "dark_only": int((dark & ~spread).sum()), "spread_only": int((spread & ~dark).sum()),
            "both": int((dark & spread).sum()), "unmeasured": int(rows["low_signal"].isna().sum()),
            "by_lake_type": by_type,
            "by_season": {int(k): {"pairs": int(len(g)), "flagged": int(g["low_signal"].fillna(False).astype(bool).sum())}
                          for k, g in rows.groupby("season")},
            "lakes": int(rows["wb_id"].nunique()),
            "lakes_every_pair_flagged": int(sum(n_un == 0 for _, n_un in per_lake)),
            "lakes_with_3_unflagged": int(sum(n_un >= 3 for _, n_un in per_lake))}


def size_word(d: float) -> str:
    return "no change" if abs(d) < SMALL else "a small change" if abs(d) < LARGE else "a large change"


def reading_in_words(share: float, flag_core: dict, inner_vs_core: dict, flag_inner: dict | None = None) -> list[str]:
    """The pre-stated reading (record, section 3), as sentences, from the flagged share and the paired differences."""
    out = []
    if share > FREQUENT:
        out.append(f"Flagged share {share:.0%}, over {FREQUENT:.0%}: the rule as fixed marks a large part of these pairs, "
                   "so it is too broad to serve as an exclusion at these points, whatever the correlations do.")
    elif share < RARE:
        out.append(f"Flagged share {share:.0%}, under {RARE:.0%}: the flag is rare at these points, so its effect on the "
                   "relationship is bounded whatever its sign.")
    else:
        out.append(f"Flagged share {share:.0%}: common, not frequent.")
    dp, dw = flag_core["pooled"], flag_core["within_lake"]
    both_up = dp["d"] >= SMALL and dw["d"] >= SMALL
    excludes_zero = dp["L"] > 0 or dw["L"] > 0
    if both_up and excludes_zero:
        out.append(f"Removing flagged pairs raises the pooled Spearman by {dp['d']:+.3f} and the within-lake Spearman by "
                   f"{dw['d']:+.3f} (both at least {SMALL}), and at least one paired interval excludes zero: on these pairs "
                   "the flagged readings are noise relative to lab chlorophyll. Next: write the exclusion into the 2027 "
                   "shallow-lake protocol as a pre-registered rule, to be judged on 2027 pairs; nothing is adopted now.")
    elif abs(dp["d"]) < SMALL and abs(dw["d"]) < SMALL:
        out.append(f"Removing flagged pairs changes the pooled Spearman by {dp['d']:+.3f} and the within-lake Spearman by "
                   f"{dw['d']:+.3f} (both under {SMALL}): no change. The flag does not change the relationship on these "
                   "pairs; it stays a display note, and the 2027 review needs no exclusion rule from it.")
    elif dp["d"] <= -SMALL or dw["d"] <= -SMALL:
        out.append(f"Removing flagged pairs lowers a Spearman by {SMALL} or more (pooled {dp['d']:+.3f}, within-lake "
                   f"{dw['d']:+.3f}): the flag removes pairs that carry information about lab chlorophyll. The thresholds "
                   "need review before the 2027 protocol, and the note's wording should not call a flagged reading "
                   "unreliable in general.")
    else:
        out.append(f"Mixed: pooled {dp['d']:+.3f}, within-lake {dw['d']:+.3f} ({size_word(dp['d'])} and "
                   f"{size_word(dw['d'])}, with no paired interval excluding zero" if not excludes_zero else
                   f"Mixed: pooled {dp['d']:+.3f}, within-lake {dw['d']:+.3f} ({size_word(dp['d'])} and "
                   f"{size_word(dw['d'])}, one paired interval excluding zero")
        out[-1] += "): inconclusive on these pairs; no next step beyond the 2027 review."
    di = inner_vs_core["pooled"]
    if abs(di["d"]) < SMALL:
        out.append(f"Inner-core against core reading, same pairs: pooled Spearman differs by {di['d']:+.3f}, under "
                   f"{SMALL}: the margin makes no difference to the relationship on these pairs.")
    else:
        out.append(f"Inner-core against core reading, same pairs: pooled Spearman differs by {di['d']:+.3f} "
                   f"({size_word(di['d'])}, {'inner higher' if di['d'] > 0 else 'core higher'}); noted for the 2027 "
                   "margin review, nothing adopted.")
    if flag_inner is not None:
        out.append(f"With the inner-core reading the flag's effect is pooled {flag_inner['pooled']['d']:+.3f}, "
                   f"within-lake {flag_inner['within_lake']['d']:+.3f} ({size_word(flag_inner['pooled']['d'])}, "
                   f"{size_word(flag_inner['within_lake']['d'])}).")
    out.append("Nothing here is a claim about algae, toxins or whether water is safe, and the lab chlorophyll test's "
               "verdict is unchanged.")
    return out


# ------------------------------------------------------------------ report
def runs(out: Path) -> dict:
    """The fetch runs' ledgers as one: the first run and, under amendment 1, the resumed one."""
    first = json.loads((out / "run.json").read_text())
    rs = [first]
    if (out / "run-resume.json").exists():
        rs.append(json.loads((out / "run-resume.json").read_text()))
    last = rs[-1]["network"]
    return {"runs": rs, "completed": sum(r["completed"] for r in rs),
            "network": {"requests": last["requests_all_runs"], "bytes": last["bytes_all_runs"]},
            "fingerprints": [v for r in rs for v in (r["before"], r["after"])]}


def report(out: Path, partial: Path | None = None) -> None:
    selection = json.loads((out / "selection.json").read_text())
    run = runs(out)
    now = digest(input_files())
    rows = pd.DataFrame(selection["pairs"])
    signal = []
    for r in rows.itertuples(index=False):
        npz = out / "bands" / f"{r.wqa_point}__{r.item_id}.npz"
        if not npz.exists():
            signal.append({"read": False})
            continue
        s = scene_signal(r.wqa_point, r.item_id, r.tile, npz)
        if s["reading_recomputed"] is None or abs(s["reading_recomputed"] - r.reading) > 1e-6:
            raise ValueError(f"recomputed reading differs from the cache: {r.wqa_point} {r.item_id}")
        signal.append({"read": True, **s})
    rows = pd.concat([rows, pd.DataFrame(signal)], axis=1)
    read_rows = rows[rows["read"]].reset_index(drop=True)
    for c in ("dark", "spread"):
        read_rows[c] = read_rows[c].astype(bool)
    flagged = read_rows["low_signal"].fillna(False).astype(bool).to_numpy()
    variants = {}
    for k, (reading, unflagged) in VARIANTS.items():
        sub = read_rows[~flagged] if unflagged else read_rows
        variants[k] = {"what": VARIANT_WORDS[k], **measures(sub, reading)}
    has_inner = read_rows["inner_ndci"].notna().to_numpy()
    differences = {
        "flag_core": {"what": "B minus A: the flag's effect on the core reading",
                      **paired_difference(read_rows, ~flagged, "reading", "reading")},
        "flag_inner": {"what": "D minus C: the flag's effect on the inner-core reading",
                       **paired_difference(read_rows[has_inner], ~flagged[has_inner], "inner_ndci", "inner_ndci")},
        "inner_vs_core": {"what": "C minus A: the inner-core reading in place of the core reading, same pairs",
                          **paired_difference(read_rows, has_inner, "reading", "inner_ndci")},
    }
    share = flag_share(read_rows)
    words = reading_in_words(share["share"], differences["flag_core"], differences["inner_vs_core"],
                             differences["flag_inner"])
    result = {
        "description": "Exploratory check, on the lab chlorophyll test's own pairs (seen data), of whether contract "
                       "1.4's low-signal rule changes the NDCI-to-lab-chlorophyll relationship; not an algae, toxin, "
                       "safety or accuracy estimate, and not a rerun of the test, whose verdict is unchanged.",
        "source": "Contains modified Copernicus Sentinel data 2021-2026. Sentinel-2 L2A via Earth Search; the lab "
                  "chlorophyll test's scene-classification cache and cores; EA Water Quality Archive chlorophyll "
                  "(determinand 7887, acetone extract, spectrophotometric, phaeopigment correction not stated), "
                  "Open Government Licence v3.0.",
        "protocol": "docs/SATELLITE-LOW-SIGNAL-CHLOROPHYLL-2026-11.md",
        "thresholds": {"low_signal": LOW_SIGNAL, "small": SMALL, "large": LARGE, "rare": RARE, "frequent": FREQUENT},
        "seed": SEED, "input_fingerprint_sha256": selection["fingerprint_sha256"],
        "fingerprint_unchanged": all(v == selection["fingerprint_sha256"] for v in run["fingerprints"] + [now]),
        "network": run["network"], "runs": run["runs"], "caps": selection["caps"], "completed": run["completed"],
        "selected": len(selection["scenes"]), "pairs": int(len(rows)), "pairs_read": int(len(read_rows)),
        "flag_share": share, "variants": variants, "differences": differences, "reading_in_words": words,
        "rows": json.loads(rows.to_json(orient="records")),
    }
    if partial is not None:   # amendment 1: the first run's own figures, kept as they were before the resume
        p = json.loads(partial.read_text())
        result["run1_partial"] = {k: p[k] for k in ("network", "completed", "pairs_read", "flag_share", "differences",
                                                    "reading_in_words")}
        result["run1_partial"]["variants"] = {k: {kk: v.get(kk) for kk in ("pairs", "lakes", "pooled", "within_lake")}
                                              for k, v in p["variants"].items()}
    OUTPUT.write_text(json.dumps(result, indent=1, default=_json_default) + "\n")
    brief = {k: result[k] for k in ("network", "completed", "pairs_read", "fingerprint_unchanged", "flag_share",
                                    "differences", "reading_in_words")}
    brief["variants"] = {k: {kk: v.get(kk) for kk in ("pairs", "lakes", "pooled", "within_lake", "per_lake")}
                         for k, v in variants.items()}
    print(json.dumps(brief, indent=1, default=_json_default))


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("step", choices=("prepare", "read", "resume", "report"))
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--partial", type=Path)
    o = a.parse_args()
    {"prepare": lambda: prepare(o.out), "read": lambda: read(o.out), "resume": lambda: read(o.out, resume=True),
     "report": lambda: report(o.out, o.partial)}[o.step]()


if __name__ == "__main__":
    main()
