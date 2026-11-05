"""docs/SONDE-SIGNAL-TEST-2026-10.md: the scoring run. NOT RUN until Ethan approves the test.

    score.py <soil dir> <matched.csv> <readings dir> <out dir>

Run by run.sh in the soil-moisture rivers test's frozen root (DIPCAST_ROOT etc.), offline, after fetch.py. Steps:
1. The rows: train_ecoli_sm.py's (soil_moisture_eval/diagnostics.rows_q1 plus `sm` at lead 0). Face check: the
   reference fitted on all rows equals data/processed/ecoli_model_sm.json in the root, to 1e-9, or the run stops.
2. The feature for each river row (feature.py), from the sondes matched to its bathing water (sondes.py, relate.py)
   whose deployment covers the sample's day, tried in sondes.order. Lakes and rows without a reading: 0.0.
3. The gate (GATE_*). If it fails, the run writes counts only and stops: no comparison is computed.
4. Leave-one-site-out predictions for the reference (the live river model's inputs) and the candidate (the same plus
   the feature), fitted on all rows, rivers and lakes, as the live model is.
5. The primary comparison on covered river rows, its label, the placebo, then what the statement reports.
No sample row or E. coli value is written: scores, counts and labels only.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _paths() -> None:
    """scripts/ (train_ecoli) and soil_moisture_eval (rows_q1, CAND), added only when needed, at the end."""
    for p in (HERE.parent, HERE.parent / "soil_moisture_eval"):
        if str(p) not in sys.path:
            sys.path.append(str(p))

import feature as ft  # noqa: E402
import labels as lb  # noqa: E402
import placebo as pl  # noqa: E402
from sondes import Sonde, order  # noqa: E402

GATE_N = 150          # covered river rows
GATE_SITES = 4        # bathing waters with at least one covered row
GATE_EVENTS = 15      # covered river rows over 900
BOOT, BOOT_SEED = 2000, 0
WARN = 0.25           # the E. coli High risk line
PROPS = ("turbidity", "ammonium")


def load_matched(path: str) -> dict[tuple[str, str], list[tuple[Sonde, tuple[str, float]]]]:
    """(bw_id, property) -> [(sonde, (direction, km along the river))] for rows that pass rule 3."""
    out: dict[tuple[str, str], list] = {}
    for r in csv.DictReader(open(path)):
        if r.get("network_ok") != "True":
            continue
        s = Sonde(r["station_id"], r["label"], r["sonde_river"] or None, float(r["sonde_lat"]), float(r["sonde_lon"]),
                  date.fromisoformat(r["opened"]) if r["opened"] else None,
                  date.fromisoformat(r["closed"]) if r["closed"] else None, {r["property"]: ""})
        out.setdefault((r["bw_id"], r["property"]), []).append((s, (r["direction"], float(r["river_km"]))))
    return out


def load_series(readings_dir: str) -> dict[tuple[str, str], pd.Series]:
    """(station id, property) -> clean series, all fetched years together."""
    frames: dict[tuple[str, str], list] = {}
    for f in sorted(Path(readings_dir).glob("*-i-subdaily-*_*.json")):
        mid = f.stem.rsplit("_", 1)[0]
        sid, code = mid.split("-")[0], mid.split("-")[1]
        prop = {"turb": "turbidity", "amm": "ammonium"}[code]
        items = json.loads(f.read_text()).get("items", [])
        frames.setdefault((sid, prop), []).append(pd.DataFrame(items, columns=["dateTime", "value", "quality"]))
    return {k: ft.clean(pd.concat(v, ignore_index=True), k[1]) for k, v in frames.items()}


def build_feature(bw_ids, sample_times, is_river, matched, series, prop, lag_h=ft.LAG_H, at=None):
    """The feature (NaN where none) and the station used, per row. `at` gives placebo lookup times."""
    vals, used = np.full(len(bw_ids), np.nan), [None] * len(bw_ids)
    for i, (bw, t, riv) in enumerate(zip(bw_ids, sample_times, is_river, strict=True)):
        if not riv:
            continue
        if at is not None and at[i] is None:
            continue
        day = pd.Timestamp(t).tz_convert("Europe/London").date() if pd.Timestamp(t).tzinfo else pd.Timestamp(t).date()
        cands = [(s, rel) for s, rel in matched.get((bw, prop), []) if s.covers(day)]
        ids = [s.station_id for s in order(cands)]
        ser = {sid: series.get((sid, prop)) for sid in ids}
        vals[i], used[i] = ft.sample_feature(t, ids, ser, prop, lag_h, None if at is None else at[i])
    return vals, used


def compare(y, p_ref, p_new, clusters, mask, b, h, secondary_harm=False) -> dict:
    """Gain (reference Brier minus candidate Brier) with its cluster-bootstrap interval, and its label."""
    _paths()
    import train_ecoli as te
    r = te.cluster_bootstrap(np.asarray(y), np.asarray(p_ref), np.asarray(p_new), np.asarray(clusters),
                             mask=np.asarray(mask, dtype=bool).copy(), n_boot=BOOT, seed=BOOT_SEED)
    lo, hi = r["brier_gain_ci"]
    r["label"] = lb.label(r["brier_gain"], lo, hi, b, h, secondary_harm)
    return r


def warn_rates(y, p, line=WARN) -> dict:
    y, p = np.asarray(y), np.asarray(p)
    hit = p >= line
    return {"miss_rate": float((~hit & (y == 1)).sum() / max((y == 1).sum(), 1)),
            "false_alarm_rate": float((hit & (y == 0)).sum() / max(hit.sum(), 1)),
            "mean_forecast": float(p.mean()), "observed_rate": float(y.mean())}


def main(soil_dir: str, matched_csv: str, readings_dir: str, out_dir: str) -> None:
    _paths()
    import train_ecoli as te
    from diagnostics import rows_q1
    from leads import CAND, soil_at_issue

    from dipcast.model.ecoli import SM_MODEL_PATH, THRESHOLD, EcoliModel, features, fit
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows, fc = rows_q1()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    X = features(fc[0][0], fc[0][1], rows["risk_lead0"], rows.lake, rows.sample_time)
    X["sm"] = soil_at_issue(rows, Path(soil_dir), 0)
    lo_sm, hi_sm = float(X["sm"].min()), float(X["sm"].max())
    prod = EcoliModel.from_json(SM_MODEL_PATH)
    ref_all = fit(X, y, CAND)
    face = max(abs(ref_all.coef[c] - prod.coef[c]) for c in CAND)
    res = {"face_check": {"largest_coef_difference": face, "passes": face < 1e-9}}
    if face >= 1e-9:
        (out / "score.json").write_text(json.dumps(res, indent=1)); raise SystemExit("face check fails")
    lake = rows["lake"].to_numpy()
    river = lake == 0.0
    site = rows["bw_id"].to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    clusters = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    matched, series = load_matched(matched_csv), load_series(readings_dir)
    st = list(rows["sample_time"])
    feats = {}
    for prop in PROPS:
        for lag in (ft.LAG_H, ft.ALT_LAG_H):
            v, used = build_feature(site, st, river, matched, series, prop, lag)
            feats[(prop, lag)] = (v, used)
    cov = {f"{p}|lag{int(lag)}": {"rows": int(np.isfinite(v).sum()), "sites": int(len(set(site[np.isfinite(v)]))),
                                  "share_of_river_rows": float(np.isfinite(v)[river].mean()),
                                  "stations_used": sorted({u for u in used if u})}
           for (p, lag), (v, used) in feats.items()}
    res["coverage"] = cov
    v0 = feats[("turbidity", ft.LAG_H)][0]
    covered = np.isfinite(v0) & river
    gate = {"rows": int(covered.sum()), "sites": int(len(set(site[covered]))), "events": int(y[covered].sum()),
            "need": {"rows": GATE_N, "sites": GATE_SITES, "events": GATE_EVENTS}}
    gate["passes"] = gate["rows"] >= GATE_N and gate["sites"] >= GATE_SITES and gate["events"] >= GATE_EVENTS
    res["gate"] = gate
    if not gate["passes"]:
        (out / "score.json").write_text(json.dumps(res, indent=1, default=str))
        print("gate fails: no comparison computed"); return

    def loso(cols, Xc):
        return te.leave_one_out(Xc, y, site, lake, cols)

    def with_feat(v):
        return X.assign(sonde=ft.with_fallback(v)[0])

    p_ref = loso(CAND, X)
    Xp = X.assign(sm=np.clip(X["sm"], lo_sm, hi_sm))
    margins = lb.margin_b(prod.predict(Xp)[covered])           # predictions of the frozen production model only
    B, H = margins["B"], margins["H"]
    res["margins"] = margins
    p_new = loso(CAND + ["sonde"], with_feat(v0))
    secondary = {"all_river_rows": compare(y, p_ref, p_new, clusters, river, B, H)}
    harm = secondary["all_river_rows"]["label"] in lb.HARMFUL
    primary = compare(y, p_ref, p_new, clusters, covered, B, H, secondary_harm=harm)
    res["primary"] = primary
    # placebo
    gains = []
    for d in range(pl.DRAWS):
        at = pl.shifted_times(st, np.random.default_rng(pl.SEED + d))
        vp, _ = build_feature(site, st, river, matched, series, "turbidity", ft.LAG_H, at=at)
        pp = loso(CAND + ["sonde"], with_feat(vp))
        m = covered
        gains.append(float(np.mean((p_ref[m] - y[m]) ** 2) - np.mean((pp[m] - y[m]) ** 2)))
    res["placebo"] = {"draws": pl.DRAWS, "gains_quantiles": np.quantile(gains, [0.05, 0.5, 0.95]).tolist(),
                      "rank_p": pl.rank_p(primary["brier_gain"], np.array(gains))}
    # reported, deciding nothing (except the all-rivers harm check above)
    va = feats[("ammonium", ft.LAG_H)][0]
    cov_a = np.isfinite(va) & river
    if cov_a.sum() >= GATE_N and len(set(site[cov_a])) >= GATE_SITES and y[cov_a].sum() >= GATE_EVENTS:
        ma = lb.margin_b(prod.predict(Xp)[cov_a])
        secondary["ammonium"] = compare(y, p_ref, loso(CAND + ["sonde"], with_feat(va)), clusters, cov_a,
                                        ma["B"], ma["H"])
        secondary["ammonium"]["margins"] = ma
    else:
        secondary["ammonium"] = {"gate": "fails", "rows": int(cov_a.sum())}
    v24 = feats[("turbidity", ft.ALT_LAG_H)][0]
    cov24 = np.isfinite(v24) & river
    secondary["lag_24h"] = compare(y, p_ref, loso(CAND + ["sonde"], with_feat(v24)), clusters, cov24, B, H)
    p_ref_y = te.leave_one_out(X, y, years, lake, CAND)
    p_new_y = te.leave_one_out(with_feat(v0), y, years, lake, CAND + ["sonde"])
    secondary["loyo"] = compare(y, p_ref_y, p_new_y, clusters, covered, B, H)
    secondary["by_site"] = {s: {"n": int((covered & (site == s)).sum()),
                                "brier_ref": float(np.mean((p_ref[covered & (site == s)] - y[covered & (site == s)]) ** 2)),
                                "brier_new": float(np.mean((p_new[covered & (site == s)] - y[covered & (site == s)]) ** 2))}
                            for s in sorted(set(site[covered]))}
    secondary["warning_line"] = {"reference": warn_rates(y[covered], p_ref[covered]),
                                 "candidate": warn_rates(y[covered], p_new[covered])}
    res["secondary"] = secondary
    passes = primary["label"] == "Better" and res["placebo"]["rank_p"] <= 0.05 and not harm
    res["verdict"] = {"passes": passes, "primary_label": primary["label"], "placebo_rank_p": res["placebo"]["rank_p"],
                      "all_rivers_label": secondary["all_river_rows"]["label"]}
    (out / "score.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["verdict"], indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
