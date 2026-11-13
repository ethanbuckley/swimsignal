"""Why spill-model candidates fail at United Utilities: the checks stated in docs/UU-DIAGNOSIS-2026-11.md.
A diagnosis on seen rows (January to August 2026, and the 2023-25 training years). Off CI, by hand, offline
(no Open-Meteo call, no download). It fits no pooled layer and saves no model.

    DIPCAST_ROOT=<scratch root with edm_events.parquet and annual_returns.parquet> DIPCAST_STATE=<scratch state> \\
    DIPCAST_CACHE=<a folder of links to United Utilities' rain cells> PYTHONPATH=src \\
        python scripts/uu_diagnosis.py --events2025 <dir> --events2026 <dir> --coverage <live_coverage.parquet> \\
        --zip2026 <2026 zip> --d2 <spill_model_nine_2024.pkl> --v2pooled <spill_model_v2_pooled.pkl> \\
        --radar <met_office_radar dir> --out <dir>

The 2026 rows, the status rebuild, the forecast-rain rows and the two-way bootstrap are PR #639's
(scripts/live_status_backtest_2026.py), restricted to United Utilities. combined-v1's formula is PR #666's.
Production's training rows are scripts/check_model_provenance.py's. v2's overflow-years are training.site_years'.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ARGV = sys.argv[1:]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_model_provenance as cmp  # noqa: E402  (production's rows; it puts a year in sys.argv for train.py)
import combined_candidate_backtest_2026 as ccb  # noqa: E402  (combined-v1's formula, unchanged)
import live_status_backtest_2026 as lsb  # noqa: E402  (#639's rows, status, rain, bootstrap)
import live_status_test as lst  # noqa: E402
import regional_routing as rr  # noqa: E402
import train as T  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.model.features import (  # noqa: E402
    ALL_FEATURES,
    RAIN_FEATURES,
    daily_rain_features,
    spill_days,
)
from dipcast.model.forecast import _apply  # noqa: E402
from dipcast.model.spill_model import PRIOR_STRENGTH, SpillModel  # noqa: E402
from dipcast.model.training import NINE, cells_of, ece, load_rain, site_years  # noqa: E402
from dipcast.model.verify import scores  # noqa: E402

UU = "United Utilities"
REPO = Path(__file__).resolve().parents[1]
HOLD = REPO / "data" / "processed" / "spill_model_holdout_2025.pkl"
HOLD_SHA = "882f9d4fb2c9314943fa861d8c6f4c62d8cd1eb57f1aa25059f4eb27d07068dc"
V2POOLED_SHA = "bd8faaaf31031fa3ca8ac763dc7047c9b591ffe37feddb220b7e52d73b1f2dc3"
COVERAGE_SHA = "a5bbf9506a1f0b211364d7eb3dcd7f020d1c6bf1bd57d0e08e62a64c3c1816be"
STREAM_SHA = "4ef2c254706f06ce619371a8e8061c1da2a8b5c6f2a39e9b4f5c791c18f31983"
EA2425_SHA = "c245fb7cd382d3f42c4603f7d8b7f98ce6cf119422f13b4ba6b09f56c5809d9c"
EA2026_SHA = "54aeb21abf61162fc12f911a302d4c6f36a7460f60267d8b972ddfd9f46d0ea1"
SEED = 20261113
# The committed figures the face checks must reproduce (United Utilities, ERA5-Land rows, #639 and #666).
FACE = {"production": 0.0379333, "D2": 0.0419537, "live status lead 1": 0.0388601, "combined-v1 lead 1": 0.0377208}
FACE_TOL, V_357, V_TOL = 0.00005, 0.039017, 0.0003
ROWS_639, SITES_639, LEAD_ROWS_639 = 539217, 2219, 12773
RADAR_MIN_COVERAGE = 0.9          # #343's rule for an hour
RADAR_MONTHS = ["2025-12", *[f"2026-{m:02d}" for m in range(1, 9)]]
POLL_FIRST, POLL_LAST = pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-17")
step = lsb.step
logit, sigmoid = ccb.logit, ccb.sigmoid


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def listing_sha(files) -> str:
    return hashlib.sha256("\n".join(sorted(f"{Path(f).resolve()} {Path(f).stat().st_size} {Path(f).stat().st_mtime_ns}"
                                           for f in files)).encode()).hexdigest()


def brier(p, y, m=None) -> float:
    d = (p - y) ** 2
    return float(d.mean() if m is None else d[m].mean())


# ---------------------------------------------------------------- offsets (SpillModel.fit_site_offsets' formula)
def offsets(pooled_p: np.ndarray, site: np.ndarray, y: np.ndarray, year: np.ndarray | None = None,
            recency: float = 1.0) -> pd.Series:
    w = np.power(recency, year.max() - year) if (recency < 1.0 and year is not None) else 1.0
    g = pd.DataFrame({"site_id": site, "n": y * w, "e": pooled_p * w}).groupby("site_id").sum()
    return np.log((g["n"] + PRIOR_STRENGTH) / (g["e"] + PRIOR_STRENGTH))


def with_offsets(z_pooled: np.ndarray, site: pd.Series, off: pd.Series | dict) -> np.ndarray:
    return sigmoid(z_pooled + site.map(off).fillna(0.0).to_numpy())


# ---------------------------------------------------------------- hindsight recalibration (C2)
def fit_logistic(X: np.ndarray, y: np.ndarray, offset: np.ndarray | None = None) -> np.ndarray:
    """Maximum-likelihood coefficients of y ~ sigmoid(X b + offset), by Newton's method."""
    b = np.zeros(X.shape[1])
    off = np.zeros(len(y)) if offset is None else offset
    for _ in range(100):
        p = sigmoid(X @ b + off)
        g = X.T @ (y - p)
        H = (X * (p * (1 - p))[:, None]).T @ X
        stepv = np.linalg.solve(H + 1e-9 * np.eye(len(b)), g)
        b = b + stepv
        if np.abs(stepv).max() < 1e-10:
            break
    return b


def recalibrate(z: np.ndarray, y: np.ndarray, month: np.ndarray) -> dict[str, tuple[np.ndarray, list]]:
    one = np.ones((len(z), 1))
    M = (month[:, None] == np.arange(1, 9)[None, :]).astype(float)
    a = fit_logistic(one, y, z)
    ab = fit_logistic(np.column_stack([one[:, 0], z]), y)
    am = fit_logistic(M, y, z)
    return {"(i) one constant": (sigmoid(z + a[0]), a.tolist()),
            "(ii) constant and slope": (sigmoid(ab[0] + ab[1] * z), ab.tolist()),
            "(iii) constant per month": (sigmoid(z + M @ am), am.tolist())}


# ---------------------------------------------------------------- short events (scripts/nine_v2_eval.py's rule)
def short_only_days(ev: pd.DataFrame) -> pd.DataFrame:
    """Spill-days touched only by events under 15 minutes."""
    lab_all = spill_days(ev).assign(any=1)
    lab_long = spill_days(ev[ev["duration_h"].isna() | (ev["duration_h"] >= 0.25)]).assign(long=1)
    m = lab_all.merge(lab_long, on=["site_id", "day"], how="left")
    return m[m["long"].isna()][["site_id", "day"]]


def thirds(v: pd.Series) -> pd.Series:
    """Lowest, middle and highest third of the index by value (ties broken by rank order)."""
    r = v.rank(method="first")
    return pd.cut(r, [0, len(v) / 3, 2 * len(v) / 3, len(v)], labels=["lowest third", "middle third", "highest third"]).astype(str)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("events2025", "events2026", "coverage", "zip2026", "d2", "v2pooled", "radar", "out"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    a = ap.parse_args(_ARGV)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {"seed": SEED, "draws": lsb.N_BOOT}

    # ------------------------------------------------------------ C0.1 inputs
    ea2425, ea2026 = a.events2025 / "ea_events_united_utilities.parquet", a.events2026 / "ea_events_united_utilities.parquet"
    stream = config.PROCESSED / "edm_events.parquet"
    got = {"coverage": sha(a.coverage), "stream_events": sha(stream), "ea_events_2024_25": sha(ea2425),
           "ea_events_2026": sha(ea2026), "holdout": sha(HOLD), "v2_pooled": sha(a.v2pooled)}
    want = {"coverage": COVERAGE_SHA, "stream_events": STREAM_SHA, "ea_events_2024_25": EA2425_SHA,
            "ea_events_2026": EA2026_SHA, "holdout": HOLD_SHA, "v2_pooled": V2POOLED_SHA}
    if got != want:
        raise SystemExit(f"an input is not the stated file: { {k: got[k][:12] for k in got if got[k] != want[k]} }")
    rr.check_v2(ccb.V2)
    cands, d2, prod, cal = lsb.load_models(a)      # checks the candidates', D2's, production's and the map's hashes
    v2, v2p, hold = SpillModel.load(ccb.V2), SpillModel.load(a.v2pooled), SpillModel.load(HOLD)
    rain_links = sorted(f for d in ("rain", "rain_nine") for f in (config.CACHE / d).glob("*.parquet"))
    R["inputs"] = got | {"rain_files": len(rain_links), "rain_listing_before": listing_sha(rain_links)}

    # ------------------------------------------------------------ the 2026 rows, United Utilities only
    lsb.NINE = [UU]
    b = lsb.build(a)
    test, status, leadrows, sites = b["test"], b["status"], b["leadrows"], b["sites"]
    y = test["y"].to_numpy().astype(float)
    site = test["site_id"]
    month = test["day"].dt.month.to_numpy()
    N = len(test)
    tw = lsb.TwoWay(site.to_numpy(), lsb.week_codes(test["day"]), np.random.default_rng(SEED))
    ALL = np.ones(N, bool)
    R["rows"] = {"rows": N, "overflows": int(site.nunique()), "weeks": int(len(tw.weeks)), "spill_days": int(y.sum()),
                 "base_rate": float(y.mean()), "window_e": b["site_info"], "inputs_639": b["inputs"]}

    diffs: list[dict] = []

    def diff(check: str, name: str, pa: np.ndarray, pb: np.ndarray, mask: np.ndarray = ALL, yy: np.ndarray = y, **extra) -> dict:
        d = (pa - yy) ** 2 - (pb - yy) ** 2
        lo, hi = tw.interval(d, mask)
        r = {"check": check, "comparison": name, "rows": int(mask.sum()), "brier_a": float(((pa - yy) ** 2)[mask].mean()),
             "brier_b": float(((pb - yy) ** 2)[mask].mean()), "difference": float(d[mask].mean()), "ci_low": lo, "ci_high": hi} | extra
        diffs.append(r)
        return r

    # ------------------------------------------------------------ stored models on the 2026 rows
    z = {"P": logit(prod.predict_pooled(test)), "V": logit(v2.predict_pooled(test)), "H": logit(hold.predict_pooled(test))}
    if np.abs(v2p.predict_pooled(test) - v2.predict_pooled(test)).max() > 1e-12:
        raise SystemExit("v2's pooled file and v2 arm (b) do not share one layer 1")
    arm = {"P": prod.predict(test), "P-none": sigmoid(z["P"]), "V": v2.predict(test), "V-none": sigmoid(z["V"]),
           "H": hold.predict(test), "H-none": sigmoid(z["H"]), "D2": d2.predict(test)}

    # status candidates and combined-v1 at every lead (ERA5-Land rows)
    cand, comb, unknown, stat = {}, {}, {}, {}
    for k in lsb.LEADS:
        st = status.features(site, test["day"], k)
        unknown[k] = st.isna().any(axis=1).to_numpy()
        x = pd.concat([test.drop(columns=[c for c in lsb.STATUS if c in test]), st], axis=1)
        pc = cands[k].predict(x)
        cand[k] = np.where(unknown[k], arm["P"], pc)            # #639's Q2 predictor: #262's fallback
        comb[k] = ccb.combine(arm["P"], pc, arm["D2"], unknown[k])
        stat[k] = (st, pc)
    step("forecasts on the 2026 rows")

    # ------------------------------------------------------------ C0.2 face checks
    face = {"production": brier(arm["P"], y), "D2": brier(arm["D2"], y), "live status lead 1": brier(cand[1], y),
            "combined-v1 lead 1": brier(comb[1], y)}
    R["face"] = {"reproduced": face, "committed": FACE, "v2 arm (b)": brier(arm["V"], y), "v2 in #357 (local days)": V_357,
                 "rows_match": N == ROWS_639 and site.nunique() == SITES_639,
                 "lead_rows": {k: len(leadrows[k][0]) for k in lsb.LEADS}}
    bad = [k for k in FACE if abs(face[k] - FACE[k]) > FACE_TOL]
    if bad or not R["face"]["rows_match"] or abs(brier(arm["V"], y) - V_357) > V_TOL or len(leadrows[1][0]) != LEAD_ROWS_639:
        (out / "results.json").write_text(json.dumps(R, indent=1, default=str))
        raise SystemExit(f"face check 2 failed: {bad or R['face']}")
    step(f"face check 2 passes: {face}, v2 {brier(arm['V'], y):.5f}")

    # ------------------------------------------------------------ training-year rows
    S = cmp.rows()                                               # production's own rows: Stream labels, 2023-25
    zS = prod.predict_pooled(S)
    stored = pd.Series(prod.site_offset)
    off_face = offsets(zS, S["site_id"].to_numpy(), S["y"].to_numpy(), S["year"].to_numpy(), 0.25).reindex(stored.index)
    R["face"]["offsets_reproduced"] = {"stored": len(stored), "exact": int(((off_face - stored).abs() < 1e-9).sum()),
                                       "stream_rows": len(S), "years": sorted(int(v) for v in S["year"].unique())}
    if R["face"]["offsets_reproduced"]["exact"] != len(stored):
        (out / "results.json").write_text(json.dumps(R, indent=1, default=str))
        raise SystemExit(f"face check 3 failed: {R['face']['offsets_reproduced']}")
    step(f"face check 3 passes: {len(stored)} stored offsets reproduced from {len(S)} Stream rows")

    ar = pd.read_parquet(lsb.AR)
    ev_ea = pd.read_parquet(ea2425).assign(company=UU)
    ev_ea = ev_ea[ev_ea["site_id"].notna()]
    ev_st = pd.read_parquet(stream)
    s24, _ = site_years(ar, ev_ea, [UU], 2024)
    s25, _ = site_years(ar, ev_ea, [UU], 2025)
    daily = daily_rain_features(load_rain(cells_of(pd.concat([s24, s25]))))
    lab_ea, lab_st = spill_days(ev_ea), spill_days(ev_st)
    E = pd.concat([T._frame(s24, 2024, daily, lab_ea), T._frame(s25, 2025, daily, lab_ea)], ignore_index=True)
    E = E.merge(lab_st.assign(y_stream=1), on=["site_id", "day"], how="left")
    E["y_stream"] = E["y_stream"].fillna(0).astype(np.int8)
    del daily
    yE, ySt, siteE = E["y"].to_numpy().astype(float), E["y_stream"].to_numpy().astype(float), E["site_id"].to_numpy()
    R["training_rows"] = {"ea_rule_rows": len(E), "ea_rule_overflows": int(E["site_id"].nunique()),
                          "spill_days_ea_labels": int(yE.sum()), "spill_days_stream_labels": int(ySt.sum()),
                          "both": int((yE * ySt).sum()), "ea_only": int((yE * (1 - ySt)).sum()), "stream_only": int(((1 - yE) * ySt).sum()),
                          "overflows_with_any_stream_event": int(E.loc[E["site_id"].isin(set(ev_st["site_id"])), "site_id"].nunique())}
    pE = {"P": prod.predict_pooled(E), "V": v2.predict_pooled(E), "H": hold.predict_pooled(E)}
    step(f"training-year rows: Stream {len(S)}, EA rule {len(E)}")

    # ------------------------------------------------------------ C1 the layer swap, and H2's ladder
    off = {"P-EA": offsets(pE["P"], siteE, yE), "P-Stream2": offsets(pE["P"], siteE, ySt),
           "P-Stream3": offsets(zS, S["site_id"].to_numpy(), S["y"].to_numpy()),
           "V-EA": offsets(pE["V"], siteE, yE), "H-EA": offsets(pE["H"], siteE, yE)}
    for name, o in off.items():
        arm[name] = with_offsets(z[name[0]], site, o)
    arms_rows = []
    tsites = pd.Index(site.unique())
    has = {"P": set(prod.site_offset), "V": set(v2.site_offset), "H": set(hold.site_offset), "D2": set(d2.site_offset)}
    has |= {name: set(o.index) for name, o in off.items()}
    for name, p in arm.items():
        s = scores(y, p)
        arms_rows.append({"arm": name, "brier": s["brier"], "auc": s["auc"], "log_loss": s["log_loss"], "ece": ece(y, p),
                          "mean_forecast": float(p.mean()), "observed": float(y.mean()),
                          "test_overflows_with_offset": int(tsites.isin(list(has.get(name, ()))).sum())})
    G1 = diff("G1", "V minus P (v2 arm (b) minus production)", arm["V"], arm["P"])
    diff("C1 layer 1", "V-EA minus P-EA (layer swap, same refitted offsets)", arm["V-EA"], arm["P-EA"])
    diff("C1 layer 1", "V-none minus P-none (pooled layers alone)", arm["V-none"], arm["P-none"])
    diff("C1 layer 1", "H-EA minus P-EA (what 2025 adds to a UU layer 1)", arm["H-EA"], arm["P-EA"])
    diff("C1 layer 1", "V-EA minus H-EA", arm["V-EA"], arm["H-EA"])
    diff("C1 offsets", "P-EA minus P (the offsets part of G1)", arm["P-EA"], arm["P"])
    diff("C1 offsets", "P-EA minus P-Stream2 (label source)", arm["P-EA"], arm["P-Stream2"])
    diff("C1 offsets", "P-Stream2 minus P-Stream3 (third year and production's rows)", arm["P-Stream2"], arm["P-Stream3"])
    diff("C1 offsets", "P-Stream3 minus P (recency 0.25)", arm["P-Stream3"], arm["P"])
    diff("C1 offsets", "V minus V-EA (v2's stored offsets against the refit)", arm["V"], arm["V-EA"])
    diff("C1 offsets", "P-none minus P (all of production's layer 2)", arm["P-none"], arm["P"])
    diff("C1 offsets", "V-none minus V (all of v2's layer 2)", arm["V-none"], arm["V"])
    diff("C1 reference", "H minus P (hold-out minus production)", arm["H"], arm["P"])
    hasP, hasV = site.isin(list(prod.site_offset)).to_numpy(), site.isin(list(v2.site_offset)).to_numpy()
    for label, m in (("offset in both", hasP & hasV), ("offset in P only", hasP & ~hasV), ("offset in V only", ~hasP & hasV),
                     ("offset in neither", ~hasP & ~hasV)):
        if m.any():
            diff("C1 offset coverage", f"V minus P, {label}", arm["V"], arm["P"], m, overflows=int(site[m].nunique()))
    step("C1 done")

    # ------------------------------------------------------------ C2 hindsight recalibration
    rc = {n: recalibrate(logit(arm[n]), y, month) for n in ("P", "V")}
    R["C2"] = {"coefficients": {n: {k: v[1] for k, v in rc[n].items()} for n in rc}}
    for k in rc["P"]:
        diff("C2 hindsight", f"V minus P after {k}", rc["V"][k][0], rc["P"][k][0])
    step("C2 done")

    # ------------------------------------------------------------ C3 short events
    ev26 = pd.read_parquet(ea2026)
    ev26 = ev26[ev26["site_id"].notna()]
    short26 = short_only_days(ev26).assign(short=1)
    sh = test[["site_id", "day"]].merge(short26, on=["site_id", "day"], how="left")["short"].notna().to_numpy()
    y_long = np.where(sh, 0.0, y)
    diff("C3 labels", "V minus P, short-only spill-days counted as dry", arm["V"], arm["P"], ALL, y_long,
         short_only_spill_days=int((sh & (y == 1)).sum()), spill_days=int(y.sum()))
    ev_all = pd.concat([ev_ea.drop(columns="company"), ev26], ignore_index=True)
    la = spill_days(ev_all).merge(short_only_days(ev_all).assign(short=1), on=["site_id", "day"], how="left")
    la["ym"] = la["day"].dt.strftime("%Y-%m")
    short_month = la.groupby("ym").agg(spill_days=("short", "size"), short_only=("short", "count")).reset_index()
    short_month["share"] = short_month["short_only"] / short_month["spill_days"]
    short_month.to_csv(out / "short_events_monthly.csv", index=False)
    step("C3 done")

    # ------------------------------------------------------------ C4 forecast against observed by month, 2024 to 2026
    mrows = []
    predE = {"P": prod.predict(E), "V": v2.predict(E), "P-none": pE["P"], "V-none": pE["V"]}
    for yr in (2024, 2025):
        for mo in range(1, 13):
            m = ((E["year"] == yr) & (E["day"].dt.month == mo)).to_numpy()
            mrows.append({"year": yr, "month": mo, "rows": int(m.sum()), "observed": float(yE[m].mean())}
                         | {f"mean_{n}": float(p[m].mean()) for n, p in predE.items()})
    for mo in range(1, 9):
        m = month == mo
        mrows.append({"year": 2026, "month": mo, "rows": int(m.sum()), "observed": float(y[m].mean())}
                     | {f"mean_{n}": float(arm[n][m].mean()) for n in predE}
                     | {"brier_P": brier(arm["P"], y, m), "brier_V": brier(arm["V"], y, m)})
    monthly = pd.DataFrame(mrows)
    monthly.to_csv(out / "monthly.csv", index=False)
    seas = {}
    for yr in (2024, 2025):
        for label, months in (("Jan-Feb", [1, 2]), ("Jan-Aug", list(range(1, 9))), ("Sep-Dec", [9, 10, 11, 12]), ("whole year", list(range(1, 13)))):
            m = ((E["year"] == yr) & E["day"].dt.month.isin(months)).to_numpy()
            seas[f"{yr} {label}"] = {"observed": float(yE[m].mean())} | {n: float(p[m].mean()) for n, p in predE.items()}
    for label, months in (("Jan-Feb", [1, 2]), ("Jan-Aug", list(range(1, 9)))):
        m = np.isin(month, months)
        seas[f"2026 {label}"] = {"observed": float(y[m].mean())} | {n: float(arm[n][m].mean()) for n in predE}
    R["C4"] = {"mean_forecast_by_season": seas}

    # ------------------------------------------------------------ C4b the mix of overflows
    lta = test.groupby("site_id")["log_lta_spills"].first()
    g = site.map(thirds(lta)).to_numpy()
    for label in ("lowest third", "middle third", "highest third"):
        diff("C4b long-term spill count", f"V minus P, {label}", arm["V"], arm["P"], g == label, base_rate=float(y[g == label].mean()))
    Ej = E[E["day"].dt.month <= 8]
    hist = Ej.groupby("site_id")["y"].mean()
    r26 = pd.Series(y).groupby(site.to_numpy()).mean()
    change = (r26 - hist.reindex(r26.index)).dropna()
    gc = site.map(thirds(change)).fillna("no 2024-25 rows").to_numpy()
    for label in ("lowest third", "middle third", "highest third", "no 2024-25 rows"):
        m = gc == label
        if m.any():
            diff("C4b change in spill-day rate, 2024-25 to 2026 (grouped on the outcome)", f"V minus P, {label}", arm["V"], arm["P"], m,
                 rate_2026=float(y[m].mean()), rate_2024_25=float(hist.reindex(pd.Index(site[m].unique())).mean()) if label != "no 2024-25 rows" else None,
                 mean_P=float(arm["P"][m].mean()), mean_V=float(arm["V"][m].mean()), overflows=int(site[m].nunique()))
    dG = (arm["V"] - y) ** 2 - (arm["P"] - y) ** 2
    per = pd.Series(dG).groupby(site.to_numpy()).sum().sort_values(ascending=False)
    top = per.index[: int(round(0.05 * len(per)))]
    mt = site.isin(top).to_numpy()
    R["C4b"] = {"overflows": len(per), "top_5pct_overflows": len(top), "share_of_G1_from_top_5pct": float(per.loc[top].sum() / per.sum()),
                "share_of_overflows_with_positive_contribution": float((per > 0).mean()),
                "top_5pct": {"rate_2026": float(y[mt].mean()), "rate_2024_25_jan_aug": float(hist.reindex(top).mean()),
                             "mean_P": float(arm["P"][mt].mean()), "mean_V": float(arm["V"][mt].mean())}}
    diff("C4b concentration", "V minus P without the 5% of overflows with the largest contributions (grouped on the outcome)",
         arm["V"], arm["P"], ~mt)
    per.rename("sum_brier_difference").to_csv(out / "per_overflow.csv")
    step("C3, C4, C4b done")

    # ------------------------------------------------------------ C5 radar
    cells = test[["cell_lat", "cell_lon"]].drop_duplicates()
    rfiles, missing = [], 0
    for cl, cn in cells.itertuples(index=False):
        for mth in RADAR_MONTHS:
            f = a.radar / f"radar_{cl:.3f}_{cn:.3f}_{mth}.parquet"
            if f.exists():
                rfiles.append(f)
            else:
                missing += 1
    R["C5"] = {"cells": len(cells), "radar_files": len(rfiles), "radar_files_missing": missing, "radar_listing_before": listing_sha(rfiles)}
    rad = pd.concat(map(pd.read_parquet, rfiles), ignore_index=True)
    rad = rad[(rad["time"] >= lst.T0) & (rad["time"] < lst.T_END)]
    rad["precip_mm"] = np.where(rad["coverage"] >= RADAR_MIN_COVERAGE, rad["radar_mm"], np.nan)
    dr = daily_rain_features(rad[["cell_lat", "cell_lon", "time", "precip_mm"]])
    dr["key"] = lst._key(dr["cell_lat"], dr["cell_lon"])
    dr = dr.sort_values(["key", "day"])
    ok_day = dr["rain_d"].notna().astype(float)
    dr["n30"] = ok_day.groupby(dr["key"]).transform(lambda s: s.rolling(30, min_periods=1).sum())
    tk = pd.DataFrame({"key": lst._key(test["cell_lat"], test["cell_lon"]), "day": test["day"].reset_index(drop=True)})
    j = tk.merge(dr[["key", "day", "n30", *RAIN_FEATURES]], on=["key", "day"], how="left")
    rad_ok = ((j["n30"] == 30) & j[RAIN_FEATURES].notna().all(axis=1)).to_numpy()
    xr = test.copy()
    for f in RAIN_FEATURES:
        xr[f] = j[f].to_numpy().astype(np.float32)
    xr = xr[rad_ok]
    pr = {"P": np.full(N, np.nan), "V": np.full(N, np.nan)}
    pr["P"][rad_ok], pr["V"][rad_ok] = prod.predict(xr), v2.predict(xr)
    e_gap = diff("C5 radar swap", "V minus P, ERA5-Land rain, rows the radar covers", arm["V"], arm["P"], rad_ok)
    r_gap = diff("C5 radar swap", "V minus P, radar rain, the same rows", np.nan_to_num(pr["V"]), np.nan_to_num(pr["P"]), rad_ok)
    d_e = (arm["V"] - y) ** 2 - (arm["P"] - y) ** 2
    d_r = np.where(rad_ok, (np.nan_to_num(pr["V"]) - y) ** 2 - (np.nan_to_num(pr["P"]) - y) ** 2, 0.0)
    lo, hi = tw.interval(d_r - d_e, rad_ok)
    diffs.append({"check": "C5 radar swap", "comparison": "change in (V minus P) from ERA5-Land to radar rain", "rows": int(rad_ok.sum()),
                  "difference": float((d_r - d_e)[rad_ok].mean()), "ci_low": lo, "ci_high": hi,
                  "brier_P_radar": brier(np.nan_to_num(pr["P"]), y, rad_ok), "brier_P_era5": brier(arm["P"], y, rad_ok),
                  "brier_V_radar": brier(np.nan_to_num(pr["V"]), y, rad_ok), "brier_V_era5": brier(arm["V"], y, rad_ok)})
    # per cell: ERA5-Land against radar daily totals, 1 Jan to 31 Aug 2026
    era = test[["cell_lat", "cell_lon", "day", "rain_d"]].drop_duplicates(["cell_lat", "cell_lon", "day"])
    era["key"] = lst._key(era["cell_lat"], era["cell_lon"])
    cd = era.merge(dr[["key", "day", "rain_d"]].rename(columns={"rain_d": "radar_d"}), on=["key", "day"], how="inner").dropna(subset=["radar_d", "rain_d"])
    cd["abs"] = (cd["rain_d"] - cd["radar_d"]).abs()
    cs = cd.groupby("key").agg(days=("abs", "size"), mad=("abs", "mean"), radar_mean=("radar_d", "mean"), era_mean=("rain_d", "mean"))
    cs = cs[cs["days"] >= 120]
    cs["disagreement"] = cs["mad"] / cs["radar_mean"]
    cs["ratio"] = cs["era_mean"] / cs["radar_mean"]
    wet = era.groupby("key")["rain_d"].mean()
    R["C5"] |= {"rows_radar_covers": int(rad_ok.sum()), "share_rows": float(rad_ok.mean()), "cells_with_120_radar_days": len(cs),
                "disagreement_thirds_cut": [float(v) for v in cs["disagreement"].quantile([1 / 3, 2 / 3])],
                "era5_over_radar_total_median": float(cs["ratio"].median()),
                "era5_over_radar_total_iqr": [float(v) for v in cs["ratio"].quantile([0.25, 0.75])],
                "daily_correlation_pooled": float(np.corrcoef(cd["rain_d"], cd["radar_d"])[0, 1]),
                "wetness_thirds_cut_mm_per_day": [float(v) for v in wet.quantile([1 / 3, 2 / 3])],
                "hourly_alignment": {}}
    # which hour offset lines the two hourly series up best (a check on the stamps, not a correction)
    eh = pd.DataFrame({"key": np.repeat(b["grid"].keys.to_numpy(), b["grid"].n_hours),
                       "h": np.tile(np.arange(b["grid"].n_hours), len(b["grid"].keys)), "era": b["grid"].mm.ravel()})
    rh = pd.DataFrame({"key": lst._key(rad["cell_lat"], rad["cell_lon"]),
                       "h": ((rad["time"] - lst.T0) // pd.Timedelta(hours=1)).to_numpy(), "radar": rad["precip_mm"].to_numpy()})
    for lag in (-2, -1, 0, 1, 2):
        mm = eh.merge(rh.assign(h=rh["h"] + lag), on=["key", "h"]).dropna()
        R["C5"]["hourly_alignment"][f"radar hour + {lag}"] = float(np.corrcoef(mm["era"], mm["radar"])[0, 1])
    del eh, rh, rad
    ck = pd.Series(lst._key(test["cell_lat"], test["cell_lon"]))
    for label, v in (("C5 thirds of cells by ERA5-Land against radar disagreement", cs["disagreement"]),
                     ("C5 thirds of cells by mean ERA5-Land rain", wet)):
        gg = ck.map(thirds(v)).fillna("no measure").to_numpy()
        for t in ("lowest third", "middle third", "highest third"):
            m = gg == t
            diff(label, f"V minus P, {t}", arm["V"], arm["P"], m, cells=int(ck[m].nunique()), overflows=int(site[m].nunique()),
                 base_rate=float(y[m].mean()))
    R["C5"]["radar_listing_after"] = listing_sha(rfiles)
    step("C5 done")

    # ------------------------------------------------------------ G2 on ERA5-Land rows, and C6 the lead map
    for k in lsb.LEADS:
        diff("G2 ERA5-Land", f"live status with fallback minus production, lead {k}", cand[k], arm["P"], lead=k)
        diff("G2 ERA5-Land", f"combined-v1 minus production, lead {k}", comb[k], arm["P"], lead=k)
    lead_rows = []
    for k in lsb.LEADS:
        pos, fr = leadrows[k]
        r = test.iloc[pos]
        fr = fr.copy()
        fr.index = r.index
        stk = stat[k][0].iloc[pos]
        xk = pd.concat([r[["site_id", *lst.STATIC]], fr, stk], axis=1)
        yk, unk = y[pos], unknown[k][pos]
        f_c, f_d2, f_raw = cands[k].predict(xk), d2.predict(xk), prod.predict(xk)
        cmap = cal[min(k, max(cal))]
        f_cal = _apply(cmap, f_raw)
        preds = {"live status (fallback to mapped production)": np.where(unk, f_cal, f_c),
                 "live status through production's lead map (diagnostic)": np.where(unk, f_cal, _apply(cmap, f_c)),
                 "combined-v1 (base raw production)": ccb.combine(f_raw, f_c, f_d2, unk),
                 "combined-v1 with the base mapped (diagnostic)": ccb.combine(f_cal, f_c, f_d2, unk),
                 "production raw": f_raw, "production mapped": f_cal}
        lm = np.zeros(N, bool)
        lm[pos] = True
        for name, p in preds.items():
            lead_rows.append({"lead": k, "predictor": name, "rows": len(pos), "cells": int(r[["cell_lat", "cell_lon"]].drop_duplicates().shape[0]),
                              "overflows": int(r["site_id"].nunique()), "observed": float(yk.mean()), "mean_forecast": float(p.mean()),
                              "brier": brier(p, yk), "ece": ece(yk, p)})
        for cname in list(preds)[:4]:
            for ref in ("production raw", "production mapped"):
                fa, fb = np.zeros(N), np.zeros(N)
                fa[pos], fb[pos] = preds[cname], preds[ref]
                diff("C6 forecast rain", f"{cname} minus {ref}, lead {k}", fa, fb, lm, lead=k)
    pd.DataFrame(lead_rows).to_csv(out / "forecast_rain.csv", index=False)
    step("C6 done")

    # ------------------------------------------------------------ C7 the fallback
    cov = pd.read_parquet(a.coverage)
    cov = cov[(cov["day"] >= POLL_FIRST) & (cov["day"] <= POLL_LAST)]
    comp_of = ar[ar["company"].isin(NINE) & (ar["year"] == 2025)].drop_duplicates("site_id", keep="last").set_index("site_id")["company"]
    cov = cov.assign(company=cov["site_id"].map(comp_of)).dropna(subset=["company"])
    pc = cov.groupby("company")[["n_known", "n_unknown", "n_stale"]].sum()
    pc["unknown_share"] = pc["n_unknown"] / (pc["n_known"] + pc["n_unknown"])
    pc["stale_share_of_known"] = pc["n_stale"] / pc["n_known"].clip(lower=1)
    R["C7"] = {"fallback_rows_by_lead": {k: int(unknown[k].sum()) for k in lsb.LEADS},
               "poll_counts_5_to_17_oct": pc.reset_index().to_dict(orient="records"), "poll_days": int(cov["day"].nunique())}

    # ------------------------------------------------------------ C8 what the status adds
    st1, pc1 = stat[1]
    kn = ~unknown[1]
    up = pd.Series((logit(pc1) - logit(arm["D2"]))[kn]).groupby(site.to_numpy()[kn]).mean()
    obs = pd.Series(y).groupby(site.to_numpy()).sum()

    def level_error(p):
        return np.log((obs + 0.5) / (pd.Series(p).groupby(site.to_numpy()).sum() + 0.5))

    lev = pd.DataFrame({"uplift": up, "D2": level_error(arm["D2"]), "P": level_error(arm["P"]), "V": level_error(arm["V"])}).dropna()
    rng = np.random.default_rng(SEED + 1)
    draws = rng.integers(0, len(lev), (lsb.N_BOOT, len(lev)))
    c8a = {}
    for mname in ("D2", "P", "V"):
        rho = float(lev["uplift"].corr(lev[mname], method="spearman"))
        bs = [float(pd.Series(lev["uplift"].to_numpy()[d]).corr(pd.Series(lev[mname].to_numpy()[d]), method="spearman")) for d in draws]
        c8a[mname] = {"spearman": rho, "ci": [float(v) for v in np.percentile(bs, [2.5, 97.5])],
                      "sd_of_level_error": float(lev[mname].std())}
    si = status.sites.get_indexer(sites["site_id"])
    d0 = lsb.DAYS_2025
    today, yest = status.sday[si, d0:d0 + 243], status.sday[si, d0 - 1:d0 + 242]
    p_after_spill, p_after_dry = float(today[yest == 1].mean()), float(today[yest == 0].mean())
    sc666 = pd.read_csv(REPO / "docs" / "COMBINED-CANDIDATE-BACKTEST-2026-11-scores.csv")
    pers = sc666[(sc666["rain"] == "ERA5-Land") & (sc666["predictor"] == "persistence P") & (sc666["rows"] == "common")
                 & sc666["lead"].isin([0, 1]) & (sc666["company"] != "all nine")].copy()
    pers["skill_over_flat_rate"] = 1 - pers["brier"] / (pers["base_rate"] * (1 - pers["base_rate"]))
    pers["rank_from_bottom"] = pers.groupby("lead")["skill_over_flat_rate"].rank()
    R["C8"] = {"a_uplift_against_level_error": c8a, "a_overflows": len(lev),
               "b_spill_day_after_spill_day": p_after_spill, "b_spill_day_after_dry_day": p_after_dry,
               "b_persistence_skill_by_company": pers[["lead", "company", "base_rate", "brier", "auc", "skill_over_flat_rate", "rank_from_bottom"]].to_dict(orient="records")}
    for k in (0, 1, 4):
        st = stat[k][0]
        now, c7 = st["spilling_at_issue"].to_numpy(), st["spill_days_7d"].to_numpy()
        for label, m in (("spilling at issue", now == 1), ("not spilling at issue, a spill-day in the last 7", (now == 0) & (c7 > 0)),
                         ("dry start", (now == 0) & (c7 == 0)), ("not spilling at issue", now == 0)):
            diff("C8c where the uplift lands", f"combined-v1 minus production, lead {k}, {label}", comb[k], arm["P"], m, lead=k,
                 base_rate=float(y[m].mean()), mean_combined=float(comb[k][m].mean()), mean_P=float(arm["P"][m].mean()))
            diff("C8c where the uplift lands", f"live status minus production, lead {k}, {label}", cand[k], arm["P"], m, lead=k)
    step("C7, C8 done")

    # ------------------------------------------------------------ write
    R["G1"] = G1
    R["inputs"]["rain_listing_after"] = listing_sha(rain_links)
    R["inputs"]["unchanged"] = R["inputs"]["rain_listing_after"] == R["inputs"]["rain_listing_before"] and \
        R["C5"]["radar_listing_after"] == R["C5"]["radar_listing_before"] and {k: sha(p) for k, p in (
            ("coverage", a.coverage), ("stream_events", stream), ("ea_events_2024_25", ea2425), ("ea_events_2026", ea2026))} == {
            k: want[k] for k in ("coverage", "stream_events", "ea_events_2024_25", "ea_events_2026")}
    pd.DataFrame(arms_rows).to_csv(out / "arms.csv", index=False)
    pd.DataFrame(diffs).to_csv(out / "differences.csv", index=False)
    (out / "results.json").write_text(json.dumps(R, indent=1, default=str))
    pd.set_option("display.width", 250, "display.max_colwidth", 90, "display.max_rows", 400)
    print(pd.DataFrame(arms_rows).to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(pd.DataFrame(diffs)[["check", "comparison", "rows", "difference", "ci_low", "ci_high"]].to_string(index=False, float_format=lambda v: f"{v:+.5f}"))
    step("written")


if __name__ == "__main__":
    main()
