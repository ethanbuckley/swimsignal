"""docs/FARM-PRESSURE-TEST-2026-10.md: the water body's farm-pollution flag as an E. coli model input.

    score.py <out.json> [<rnags.json>]   (default: data/raw/rnags.json under DIPCAST_ROOT)
    score.py --selftest

train_ecoli.py's rows, filters and evaluations (its own functions), run on the reference (its seven inputs) and the
candidate (those plus `farm`), with leave-one-site-out deciding and its interval over whole sites. Then 1,000 placebo
flags, the same number of sites flagged at random within rivers and within lakes, each scored by LOSO and LOYO. Then
the record-only arms.

`farm` is 1 where data/raw/rnags.json lists FARM_PRESSURE on the bathing water's water body, confirmed or probable,
with build_site.attach_water_body's rule. A site the file places nowhere gets 0 and is counted.

Face check: this script's reference LOYO, LOSO and forward Brier scores equal those train_ecoli.py wrote to
ecoli_model_eval.json in the same root. If the file is missing or unreadable, or any score or the row count differs,
the run stops (the test's "Data" section): out.json then holds only the diagnostic and the face-check figures, no
conditions, reading or verdict, and the script exits 2, so run.sh reports the step as failed.

--selftest runs the scoring on synthetic rows with a planted site-level effect and with none, and checks the planted
one passes conditions 1 and 2 and the null one does not. It reads no data.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import train_ecoli as te

from dipcast import config
from dipcast.model.ecoli import FEATURES, THRESHOLD, features, fit
from dipcast.model.forecast import MAX_MISSING_SHARE
from dipcast.model.verify import scores

FARM_PRESSURE = ("Agriculture and rural land management", "Pollution from rural areas")
CANDIDATE = [*FEATURES, "farm"]
RECORD_ARMS = {"farm_confirmed": [*FEATURES, "farm_confirmed"], "farm_x_rain": [*FEATURES, "farm", "farm_x_lrain48"]}
MARGIN = 0.0005
N_PLACEBO = 1000
PLACEBO_SEED = 1
PLACEBO_SHARE = 0.05


def site_flags(path: Path) -> dict[str, dict]:
    """bw_id -> farm (confirmed or probable), farm_confirmed, and whether the file places the site at all."""
    doc = json.loads(path.read_text())
    out = {}
    for key, at in doc["spots"].items():
        if not key.startswith("bw-"):
            continue
        body = doc["water_bodies"].get(at["id"]) if at else None
        hit = [p["certainty"] for p in (body or {}).get("pressures", []) if (p["sector"], p["issue"]) == FARM_PRESSURE]
        out[key.removeprefix("bw-")] = {"farm": float(bool(hit)), "farm_confirmed": float("confirmed" in hit),
                                        "placed": at is not None, "water_body": at["id"] if at else None}
    return out


def load_rows():
    """train_ecoli.main's rows and filters, unchanged: rows, lead-0 rain (48 h, 24 h)."""
    rows = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet")
    rows = rows[rows.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "ecoli"]).reset_index(drop=True)
    rows["lake"] = (rows["kind"] == "lake").astype(float)
    rows["day"] = rows["sample_time"].dt.floor("D")
    sites = pd.read_parquet(config.RAW / "bwq_samples.parquet").drop_duplicates("bw_id").set_index("bw_id")
    rows["lat"], rows["lon"] = sites.loc[rows.bw_id, "lat"].to_numpy(), sites.loc[rows.bw_id, "lon"].to_numpy()
    ex = pd.read_parquet(te.EXPOSURE_FILE)
    ex["day"] = pd.to_datetime(ex["day"])
    if ex["day"].dt.tz is None and rows["day"].dt.tz is not None:
        ex["day"] = ex["day"].dt.tz_localize(rows["day"].dt.tz)
    if "missing_share" not in ex:
        ex["missing_share"] = np.where(ex["risk_prod"].isna(), 1.0, 0.0)
    for k in te.LEADS:
        e = ex[ex.lead == k][["bw_id", "day", "risk_prod", "risk_holdout", "missing_share"]].rename(
            columns={"risk_prod": f"risk_lead{k}", "risk_holdout": f"risk_hold_lead{k}", "missing_share": f"miss_lead{k}"})
        rows = rows.merge(e, on=["bw_id", "day"], how="left")
    fc = te.forecast_rain_at_samples(rows)
    ok_rain = np.all([~np.isnan(fc[k][0]) for k in te.LEADS], axis=0)
    shown = {k: (rows[f"miss_lead{k}"].fillna(1.0).to_numpy() <= MAX_MISSING_SHARE) & rows[f"risk_lead{k}"].notna().to_numpy()
             for k in te.LEADS}
    ok = ok_rain & np.all([shown[k] for k in te.LEADS], axis=0)
    return rows[ok].reset_index(drop=True), (fc[0][0][ok], fc[0][1][ok])


def brier(y, p, m=None) -> float:
    m = np.ones(len(y), dtype=bool) if m is None else m
    m = m & ~np.isnan(p)
    return float(np.mean((p[m] - y[m]) ** 2))


def split_scores(y, p, rivers, m=None) -> dict:
    m = np.ones(len(y), dtype=bool) if m is None else m
    ok = m & ~np.isnan(p)
    s = scores(y[ok], p[ok])
    return {"all": brier(y, p, m), "rivers": brier(y, p, m & rivers), "lakes": brier(y, p, m & ~rivers),
            "auc": s.get("auc"), "n": int(ok.sum())}


def arm_preds(X, Xh, y, years, site, lake, cols, tr, tt) -> dict:
    p_fwd = np.full(len(y), np.nan)
    p_fwd[tt] = te._fit_predict(Xh, y, tr, tt, cols, lake)
    return {"loso": te.leave_one_out(X, y, site, lake, cols), "loyo": te.leave_one_out(X, y, years, lake, cols),
            "forward": p_fwd}


def placebo_flags(site, lake, farm, n=N_PLACEBO, seed=PLACEBO_SEED) -> list[np.ndarray]:
    """Row-level placebo flags: within rivers and within lakes, as many sites flagged at random as the real flag
    flags among the scored sites."""
    rng = np.random.default_rng(seed)
    per_site = pd.DataFrame({"site": site, "lake": lake, "farm": farm}).drop_duplicates("site").sort_values("site")
    groups = [(g["site"].to_numpy(), int(g["farm"].sum())) for _, g in per_site.groupby("lake")]
    out = []
    for _ in range(n):
        flagged = set()
        for ids, k in groups:
            flagged.update(rng.choice(ids, size=k, replace=False).tolist())
        out.append(np.isin(site, list(flagged)).astype(float))
    return out


def evaluate(X, Xh, y, years, site, lake, week, n_placebo=N_PLACEBO) -> dict:
    """Reference against candidate, the six conditions, the placebo distributions and the reading. X and Xh carry
    `farm` (and the record-only columns where present)."""
    rivers = lake == 0.0
    tr, tt = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    P = {"reference": arm_preds(X, Xh, y, years, site, lake, FEATURES, tr, tt),
         "candidate": arm_preds(X, Xh, y, years, site, lake, CANDIDATE, tr, tt)}
    for a, cols in RECORD_ARMS.items():
        if all(c in X for c in cols):
            P[a] = arm_preds(X, Xh, y, years, site, lake, cols, tr, tt)
    res = {name: {a: split_scores(y, P[a][name], rivers, tt if name == "forward" else None) for a in P}
           for name in ("loso", "loyo", "forward")}
    ref, cand = P["reference"], P["candidate"]
    gain = {name: res[name]["reference"]["all"] - res[name]["candidate"]["all"] for name in res}
    res["gain"] = gain
    res["bootstrap_loso_sites"] = te.cluster_bootstrap(y, ref["loso"], cand["loso"], site)
    res["bootstrap_loso_sites_rivers"] = te.cluster_bootstrap(y, ref["loso"], cand["loso"], site, mask=rivers)
    res["bootstrap_loso_site_weeks"] = te.cluster_bootstrap(y, ref["loso"], cand["loso"], week)
    res["bootstrap_loyo_sites"] = te.cluster_bootstrap(y, ref["loyo"], cand["loyo"], site)

    # Placebo flags, each through the same LOSO and LOYO against the same reference.
    b_ref = {name: brier(y, ref[name]) for name in ("loso", "loyo")}
    pl = {"loso": [], "loyo": []}
    for f in placebo_flags(site, lake, X["farm"].to_numpy(), n=n_placebo):
        Xp = X.assign(farm=f)
        pl["loso"].append(b_ref["loso"] - brier(y, te.leave_one_out(Xp, y, site, lake, CANDIDATE)))
        pl["loyo"].append(b_ref["loyo"] - brier(y, te.leave_one_out(Xp, y, years, lake, CANDIDATE)))
    res["placebo"] = {name: {"n": len(v), "share_ge_real": float(np.mean(np.array(v) >= gain[name])),
                             "pct": {str(q): float(np.percentile(v, q)) for q in (2.5, 5, 25, 50, 75, 95, 97.5)},
                             "mean": float(np.mean(v))} for name, v in pl.items()}

    final = fit(X, y, CANDIDATE)
    res["coef_per_sd"] = {"reference": fit(X, y, FEATURES).coef, "candidate": final.coef}
    for a, cols in RECORD_ARMS.items():
        if a in P:
            res["coef_per_sd"][a] = fit(X, y, cols).coef
    L = res["loso"]
    B = res["bootstrap_loso_sites"]
    c = {
        "1_loso_gain": bool(gain["loso"] >= MARGIN and B["brier_gain_ci"][0] > 0),
        "2_placebo_loso": bool(res["placebo"]["loso"]["share_ge_real"] < PLACEBO_SHARE),
        "3_loyo_not_worse": bool(-gain["loyo"] <= MARGIN),
        "4_forward_not_worse": bool(-gain["forward"] <= MARGIN),
        "5_rivers_lakes_not_worse": bool(L["candidate"]["rivers"] - L["reference"]["rivers"] <= MARGIN
                                         and L["candidate"]["lakes"] - L["reference"]["lakes"] <= MARGIN),
        "6_sign_positive": bool(final.coef["farm"] > 0),
    }
    c["passes"] = all(c.values())
    res["conditions"] = c
    if gain["loyo"] >= MARGIN and gain["loso"] < MARGIN:
        reading = "re-describes sites"
    elif c["1_loso_gain"] and c["2_placebo_loso"]:
        reading = "predicts new sites"
    elif gain["loyo"] < MARGIN and gain["loso"] < MARGIN:
        reading = "neither"
    else:
        reading = "none of the three: a LOSO gain of at least the margin that fails its interval or the placebo"
    res["reading"] = reading
    return res


def add_flags(X: pd.DataFrame, rows: pd.DataFrame, flags: dict) -> pd.DataFrame:
    f = rows["bw_id"].map(lambda b: flags.get(b, {}))
    X["farm"] = f.map(lambda d: d.get("farm", 0.0)).to_numpy(dtype=float)
    X["farm_confirmed"] = f.map(lambda d: d.get("farm_confirmed", 0.0)).to_numpy(dtype=float)
    X["farm_x_lrain48"] = X["farm"] * X["lrain48"]
    return X


def main(out_path: str, rnags: str | None = None) -> None:
    path = Path(rnags) if rnags else config.RAW / "rnags.json"
    flags = site_flags(path)
    rows, (r48, r24) = load_rows()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    years = rows["sample_time"].dt.year.to_numpy()
    lake = rows["lake"].to_numpy()
    site = rows["bw_id"].to_numpy()
    X = add_flags(features(r48, r24, rows["risk_lead0"], rows.lake, rows.sample_time), rows, flags)
    Xh = add_flags(features(r48, r24, rows["risk_hold_lead0"], rows.lake, rows.sample_time), rows, flags)
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()

    per_site = rows.groupby("bw_id").agg(name=("name", "first"), kind=("kind", "first"), n=("bw_id", "size"),
                                         over_900=("ecoli", lambda v: int((v > THRESHOLD).sum())))
    per_site["placed"] = [flags.get(b, {}).get("placed", False) for b in per_site.index]
    per_site["water_body"] = [flags.get(b, {}).get("water_body") for b in per_site.index]
    per_site["farm"] = [flags.get(b, {}).get("farm", 0.0) for b in per_site.index]
    per_site["farm_confirmed"] = [flags.get(b, {}).get("farm_confirmed", 0.0) for b in per_site.index]
    split = {kind: {"sites_flag1": int((g.farm == 1).sum()), "sites_confirmed": int((g.farm_confirmed == 1).sum()),
                    "sites_flag0_placed": int(((g.farm == 0) & g.placed).sum()), "sites_not_placed": int((~g.placed).sum()),
                    "rows_flag1": int(g.n[g.farm == 1].sum()), "rows_flag0": int(g.n[g.farm == 0].sum())}
             for kind, g in per_site.groupby("kind")}

    res = {"rnags_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows), "sites": int(rows.bw_id.nunique()), "over_900": int(y.sum()), "split": split,
           "sites_table": per_site.reset_index().to_dict(orient="records")}
    res.update(evaluate(X, Xh, y, years, site, lake, week))

    # Record only: reference and candidate without the sites the file places nowhere.
    keep = per_site.index[per_site.placed].to_numpy()
    m = np.isin(site, keep)
    if not m.all():
        Xm, Xhm = X[m].reset_index(drop=True), Xh[m].reset_index(drop=True)
        rivers_m = lake[m] == 0.0
        tr, tt = years[m] <= te.FORWARD_TRAIN_UNTIL, years[m] > te.FORWARD_TRAIN_UNTIL
        Pm = {a: arm_preds(Xm, Xhm, y[m], years[m], site[m], lake[m], cols, tr, tt)
              for a, cols in (("reference", FEATURES), ("candidate", CANDIDATE))}
        res["record_placed_only"] = {
            "sites_left_out": sorted(set(site[~m])), "rows": int(m.sum()),
            **{name: {a: split_scores(y[m], Pm[a][name], rivers_m, tt if name == "forward" else None) for a in Pm}
               for name in ("loso", "loyo", "forward")},
            "bootstrap_loso_sites": te.cluster_bootstrap(y[m], Pm["reference"]["loso"], Pm["candidate"]["loso"], site[m])}

    finish(res, len(rows), out_path, config.PROCESSED / "ecoli_model_eval.json")


FACE_KEYS = ("loyo", "loso", "forward")
STOP_EXIT = 2


def face_check(res: dict, n_rows: int, ev: Path) -> dict:
    """The stated face check: the reference arm's LOYO, LOSO and forward Brier (4 decimals) and the row count against
    train_ecoli.py's ecoli_model_eval.json. `holds` is True only when the file is read and all four agree; `why` says
    what failed."""
    here = {**{k: round(res[k]["reference"]["all"], 4) for k in FACE_KEYS}, "n": n_rows}
    if not ev.exists():
        return {"holds": False, "why": f"{ev} not found: train_ecoli.py must write it in the same root first",
                "here_reference": here}
    try:
        e = json.loads(ev.read_text())
        full = te.FULL
        pub = {"loyo": next(r["brier"] for r in e["loyo"] if r["model"] == full),
               "loso": next(r["brier"] for r in e["loso"] if r["model"] == full),
               "forward": next(r["brier"] for r in e["forward"]["table"] if r["model"] == full) if e.get("forward") else None,
               "n": e["n_samples"]}
        # Every score a real number, so the comparison below cannot raise: a string, bool, None or NaN is malformed.
        for k in FACE_KEYS:
            v = pub[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{k} Brier is {v!r}, not a finite number")
            pub[k] = round(float(v), 4)
        if isinstance(pub["n"], bool) or not isinstance(pub["n"], int):
            raise ValueError(f"n_samples is {pub['n']!r}, not a whole number")
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as err:
        return {"holds": False, "why": f"{ev} unreadable as train_ecoli output ({type(err).__name__}: {err})",
                "here_reference": here}
    differ = [k for k in FACE_KEYS if pub[k] != here[k]]
    if pub["n"] != here["n"]:
        differ.append("n")
    return {"holds": not differ, "why": "" if not differ else "reference differs from train_ecoli on " + ", ".join(differ),
            "train_ecoli": pub, "here_reference": here}


def finish(res: dict, n_rows: int, out_path: str, ev: Path) -> None:
    """Write the result only if the face check holds. Otherwise the run stops: the file gets the diagnostic and the
    face-check figures, and none of conditions, reading, gain or the arms' scores, so no verdict can be read from a
    run whose reference does not match."""
    fc = face_check(res, n_rows, ev)
    if not fc["holds"]:
        stop = {"stopped": "face check failed: " + fc["why"], "face_check": fc,
                **{k: res[k] for k in ("rnags_sha256", "rows", "sites") if k in res}}
        Path(out_path).write_text(json.dumps(stop, indent=1, default=float))
        print(json.dumps(stop, indent=1, default=float), file=sys.stderr)
        raise SystemExit(STOP_EXIT)
    res["face_check"] = fc
    Path(out_path).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("rows", "sites", "split", "gain", "conditions", "reading", "face_check")
                      if k in res}, indent=1, default=float))


def selftest() -> None:
    """Synthetic rows: 30 sites (20 rivers, 10 lakes), half flagged. Planted: the flag adds 1.2 to the log-odds of
    every sample at a flagged site. Null: no flag effect, but each site has its own random offset. The planted case
    must pass conditions 1 and 2; the null case must fail condition 2 or 1."""
    def synth(effect: float, seed: int):
        rng = np.random.default_rng(seed)
        n_sites, per = 30, 50
        lake = np.repeat((np.arange(n_sites) >= 20).astype(float), per)
        site = np.repeat([f"s{i:02d}" for i in range(n_sites)], per)
        farm_site = np.zeros(n_sites)
        farm_site[rng.choice(20, 10, replace=False)] = 1
        farm_site[20 + rng.choice(10, 5, replace=False)] = 1
        offset = rng.normal(0, 0.6, n_sites)
        farm = np.repeat(farm_site, per)
        when = pd.to_datetime("2023-05-01") + pd.to_timedelta(rng.integers(0, 4 * 365, len(site)), unit="D")
        when = pd.Series(when).where(lambda w: w.dt.month.between(5, 9), pd.to_datetime("2024-07-01")).to_numpy()
        r48 = rng.gamma(0.6, 8, len(site)); r24 = r48 * rng.uniform(0.3, 0.7, len(site))
        risk = rng.uniform(0.01, 0.4, len(site))
        X = features(r48, r24, risk, lake, when)
        z = -2.0 + 0.9 * X["lrain48"] + 0.5 * X["logit_risk"] - 1.0 * lake + effect * farm + np.repeat(offset, per)
        y = (rng.uniform(size=len(site)) < 1 / (1 + np.exp(-z))).astype(int)
        X["farm"] = farm; X["farm_confirmed"] = farm; X["farm_x_lrain48"] = farm * X["lrain48"]
        years = pd.DatetimeIndex(when).year.to_numpy()
        week = np.array([f"{s}|{w}" for s, w in zip(site, pd.DatetimeIndex(when).strftime("%G-%V"), strict=True)])
        return X, X.copy(), y, years, site, lake, week

    planted = evaluate(*synth(1.2, 3), n_placebo=200)
    null = evaluate(*synth(0.0, 4), n_placebo=200)
    print("planted:", planted["gain"], planted["conditions"], planted["reading"], planted["placebo"]["loso"]["share_ge_real"])
    print("null:", null["gain"], null["conditions"], null["reading"], null["placebo"]["loso"]["share_ge_real"])
    assert planted["conditions"]["1_loso_gain"] and planted["conditions"]["2_placebo_loso"], "planted effect not found"
    assert not (null["conditions"]["1_loso_gain"] and null["conditions"]["2_placebo_loso"]), "null passed"
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        main(*sys.argv[1:])
