"""docs/FLOW-DILUTION-TEST-2026-10.md: the run, in four steps. Not run before Ethan approves the statement.

    score.py map     <station cache> <out>              gauges for each river bathing water; writes gauges.csv
    (flow_fetch.py flows --cache <flow cache> --gauges <out>/gauges.csv --fetch)
    score.py prep    <station cache> <flow cache> <out> lead-0 exposures for every arm and placebo; the face check
    score.py predict <soil dir> <out>                   held-out predictions, the gate, B and H from predictions alone
    score.py score   <out>                              the scores, the conditions and the label

Run in a root where validate_ecoli.py and replay_ecoli_leads.py have run (DIPCAST_ROOT etc., as run.sh builds it),
offline except `flow_fetch.py flows`. `map` and `prep` read no E. coli value. `predict` reads them only to fit inside
training folds and to count the gate; it writes no score. `score` refuses to run unless run_statement.json names the
SHA-256 of the predictions file it reads.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "soil_moisture_eval"))
import flow_fetch as ff
import flow_protocol as fp

ARMS = {   # name: (gauge rule, k, lag rule); "reference" is production
    "reference": (None, None, None),
    "spot_k05": ("spot", fp.K_PRIMARY, "by_feed"),          # the candidate (primary)
    "spot_k1": ("spot", fp.K_SECONDARY, "by_feed"),         # secondary: plain dilution
    "overflow_k05": ("overflow", fp.K_PRIMARY, "by_feed"),  # secondary: the per-overflow gauge rule
    "spot_k05_lag1": ("spot", fp.K_PRIMARY, "all_1h"),      # sensitivity: every gauge as if on the real-time feed
}
PRIMARY = "spot_k05"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- map --------------------------------------------------------------------------------------------------------
def station_table(cache: Path) -> pd.DataFrame:
    c = ff.CappedClient(cache, fetch=False)
    hy, fm = ff.stations(c)
    rt = {str(v) for s in fm.get("items", []) for k in ("stationReference", "wiskiID", "RLOIid")
          for v in (s.get(k) if isinstance(s.get(k), list) else [s.get(k)]) if v not in (None, "")}
    rows = []
    for s in hy.get("items", []):
        m = ff.measure_ids(s)
        if not (m["daily"] and m["q15"]) or not isinstance(s.get("lat"), (int, float)):
            continue
        ids = {str(v) for k in ("stationReference", "wiskiID", "RLOIid")
               for v in (s.get(k) if isinstance(s.get(k), list) else [s.get(k)]) if v not in (None, "")}
        river = s.get("riverName")
        rows.append({"station": s.get("notation"), "label": str(s.get("label") or ""),
                     "river": " / ".join(river) if isinstance(river, list) else str(river or ""),
                     "lat": float(s["lat"]), "lon": float(s["long"]), "daily": m["daily"], "q15": m["q15"],
                     "realtime": bool(ids & rt)})
    return pd.DataFrame(rows)


def run_map(station_cache: str, out: str) -> None:
    import glofas_check as gc
    from eval_pins import bathing_water_pin
    from make_lake_spill_ratio import GAUGE_SNAP_M, RIVER_FORMS

    from dipcast import config
    from dipcast.model.transport import river_velocity, upstream_overflows
    from dipcast.network.names import same_river
    from dipcast.network.rivers import RiverNetwork, lonlat_to_bng
    from dipcast.overflows import load_overflows

    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    st = station_table(Path(station_cache))
    net = RiverNetwork.load(); ov = load_overflows(net)
    snaps = []
    for s in st.itertuples(index=False):
        x, y = lonlat_to_bng(s.lon, s.lat)
        sn = net.snap_xy(float(x), float(y), max_m=GAUGE_SNAP_M, forms=RIVER_FORMS)
        if sn is not None:
            snaps.append({**s._asdict(), "link_id": sn.link_id, "frac": sn.frac})
    snaps = pd.DataFrame(snaps)
    # The river bathing waters in the rows: bw_id and kind only, no outcome.
    vr = pd.read_parquet(config.PROCESSED / "ecoli_validation_rows.parquet", columns=["bw_id", "kind", "upstream"])
    pts = pd.read_parquet(config.RAW / "bwq_samples.parquet", columns=["bw_id", "lat", "lon"]).drop_duplicates("bw_id")
    pts = pts.set_index("bw_id")
    cap = config.MAX_UPSTREAM_KM * 1000.0
    mapping, used = {}, set()
    for bw in sorted(vr[(vr.kind == "river") & (vr.upstream > 0)].bw_id.unique()):
        pin = bathing_water_pin(net, bw, float(pts.at[bw, "lon"]), float(pts.at[bw, "lat"]))
        rec = {"pin_mode": pin.mode, "watercourse": pin.watercourse, "spot_gauge": None, "overflow_gauge": {}}
        if pin.mode != "river" or pin.snap is None:
            mapping[bw] = rec
            continue
        spot = (pin.snap.link_id, pin.snap.frac)
        a_spot = gc.catchment_at(net, *spot)
        cands = []
        lat0, lon0 = float(pts.at[bw, "lat"]), float(pts.at[bw, "lon"])
        for g in snaps.itertuples(index=False):
            if gc.km(lat0, lon0, g.lat, g.lon) > config.MAX_UPSTREAM_KM:
                continue
            pos = gc.along(net, spot, (g.link_id, g.frac), cap)
            if pos is None:
                continue
            a_g = gc.catchment_at(net, g.link_id, g.frac)
            cands.append({"station": g.station, "side": pos[0], "along_km": pos[1] / 1000.0,
                          "area_ratio": a_g / a_spot if a_spot > 0 else np.inf,
                          "part": gc.part_channel(g.label, g.river), "total": bool(gc.TOTAL_WORDS & gc.words(g.label)),
                          "same_river": same_river(g.river, pin.watercourse) is True,
                          "link_id": g.link_id, "frac": g.frac})
        best = fp.choose_spot_gauge(cands)
        if best is not None:
            rec["spot_gauge"] = best["station"]; used.add(best["station"])
        # Per-overflow rule: which overflows each upstream candidate gauge is below.
        up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))
        above = {}
        for c in cands:
            if c["side"] != "upstream":
                continue
            start = net.links.at[c["link_id"], "start_node"]
            links = set(net.upstream_edges(start, cap))
            same_link = (up["link_id"] == c["link_id"]) & (up["frac"] < c["frac"])
            above[c["station"]] = set(up.loc[up["link_id"].isin(links) | same_link, "site_id"])
        for sid in up["site_id"]:
            oc = [{**c, "below_overflow": sid in above.get(c["station"], set())} for c in cands]
            g = fp.choose_overflow_gauge(oc)
            if g is not None:
                rec["overflow_gauge"][str(sid)] = g["station"]; used.add(g["station"])
        rec["n_overflows"] = int(len(up))
        mapping[bw] = rec
    st[st.station.isin(used)].to_csv(out / "gauges.csv", index=False)
    (out / "mapping.json").write_text(json.dumps(mapping, indent=1))
    n_spot = sum(1 for r in mapping.values() if r["spot_gauge"])
    print(f"{len(mapping)} river bathing waters; {n_spot} with a spot gauge; {len(used)} gauges to fetch")


# ---- prep -------------------------------------------------------------------------------------------------------
def gauge_flows(flow_cache: Path, gauges: pd.DataFrame) -> tuple[dict, dict]:
    """station -> 15-minute series (clean) and station -> reference flow, from the cache only."""
    c = ff.CappedClient(flow_cache, fetch=False)
    q15, ref = {}, {}
    for g in gauges.itertuples(index=False):
        d = c.get_json(f"{ff.HY}/id/measures/{g.daily}/readings.json",
                       {"mineq-date": ff.REF_FROM, "maxeq-date": ff.REF_TO, "_limit": ff.READINGS_LIMIT})
        t = pd.DataFrame(d.get("items", []))
        if len(t) >= ff.READINGS_LIMIT:
            raise SystemExit(f"{g.daily}: hit the row limit")
        if t.empty:
            ref[g.station] = float("nan")
        else:
            t = t[~t.get("quality", pd.Series("", index=t.index)).fillna("").isin(fp.DROP_QUALITY)]
            ref[g.station] = fp.reference_flow(pd.Series(pd.to_numeric(t["value"], errors="coerce").to_numpy(),
                                                         index=pd.to_datetime(t["date"])))
        parts = []
        for y in ff.SEASONS:
            d = c.get_json(f"{ff.HY}/id/measures/{g.q15}/readings.json",
                           {"mineq-date": f"{y}-{ff.SEASON_FROM}", "maxeq-date": f"{y}-{ff.SEASON_TO}",
                            "_limit": ff.READINGS_LIMIT})
            items = d.get("items", [])
            if len(items) >= ff.READINGS_LIMIT:
                raise SystemExit(f"{g.q15} {y}: hit the row limit")
            if items:
                parts.append(fp.clean_readings(pd.DataFrame(items)))
        q15[g.station] = pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)
    return q15, ref


def run_prep(station_cache: str, flow_cache: str, out: str) -> None:
    """Lead-0 exposure on every sample day, for every arm and placebo, with the production and the 2023-24 spill
    models: replay_ecoli_leads.main at k = 0, with the weights of each arm."""
    from eval_pins import bathing_water_pin
    from replay_ecoli_leads import LEADS, lead_features, load_lead_rain

    from dipcast import config
    from dipcast.model.features import ALL_FEATURES, daily_rain_features
    from dipcast.model.forecast import calibrate_at_lead
    from dipcast.model.spill_model import SpillModel
    from dipcast.model.transport import history_days, river_velocity, upstream_overflows
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows

    out = Path(out)
    gauges = pd.read_csv(out / "gauges.csv")
    mapping = json.loads((out / "mapping.json").read_text())
    q15, ref = gauge_flows(Path(flow_cache), gauges)
    realtime = dict(zip(gauges.station, gauges.realtime, strict=True))
    shifts = fp.placebo_shifts(sorted(gauges.station))
    col = {g: i for i, g in enumerate(sorted(gauges.station))}

    def factor(station, issue, k, lag_rule, shift=None):
        if station is None or station not in q15:
            return float("nan")
        lag = 1.0 if lag_rule == "all_1h" else fp.lag_for(bool(realtime[station]))
        t = issue if shift is None else fp.shifted_day(issue, int(shift))
        return fp.flow_factor(fp.flow_at_issue(q15[station], t, lag), ref[station], k)

    samples = pd.read_parquet(config.RAW / "bwq_samples.parquet", columns=["bw_id", "lat", "lon", "sample_time"])
    samples = samples.dropna(subset=["sample_time"])
    samples["day"] = samples["sample_time"].dt.floor("D")
    net = RiverNetwork.load(); ov = load_overflows(net)
    prod = SpillModel.load(); hold = SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl")
    leads = load_lead_rain()
    daily = {k: daily_rain_features(leads[leads.lead == k].drop(columns="lead")) for k in LEADS}
    cols = ["site_id", "lat", "lon", "company", "lta_spills", "spill_hours", "edm_operational_pct"]
    recs = []
    for bw_id, g in samples.groupby("bw_id"):
        s = g.iloc[0]
        try:
            pin = bathing_water_pin(net, bw_id, float(s.lon), float(s.lat))
        except KeyError:
            continue
        up = upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))
        sdays = pd.DatetimeIndex(sorted(g["day"].unique()))
        if len(up) == 0:
            continue
        days = pd.date_range(sdays.min() - pd.Timedelta(days=history_days(up["travel_h"])), sdays.max(), freq="D")
        sd = lead_features(up[cols], daily, days, 0)
        avail = sd["rain_d"].notna().to_numpy()
        sd = sd.astype({f: np.float32 for f in ALL_FEATURES}).fillna({f: 0.0 for f in ALL_FEATURES})
        P = {}
        for name, model, cal in (("prod", prod, True), ("hold", hold, False)):
            sd["p"] = model.predict(sd)
            sd.loc[~avail, "p"] = np.nan
            pm = sd.pivot(index="site_id", columns="day", values="p").reindex(index=up["site_id"], columns=days)
            pm = pm.to_numpy(dtype=float)
            v = calibrate_at_lead(np.nan_to_num(pm, nan=0.0), lead=0) if cal else pm
            P[name] = np.where(np.isnan(pm), 0.0, v)   # missing probabilities contribute nothing, as in the replay
        w, dil, tr = (up[c].to_numpy(dtype=float) for c in ("weight", "dilution", "travel_h"))
        m = mapping.get(bw_id, {})
        river = bw_id in mapping
        di = {d: days.get_loc(d) for d in sdays}
        # The first sample time on each day sets that day's issue time (all samples at a site-day share the exposure).
        first = g.groupby("day")["sample_time"].min()

        def risk(arm, shift_row=None):
            rule, k, lag_rule = ARMS[arm] if arm in ARMS else ARMS[PRIMARY]
            F = np.full((len(up), len(days)), np.nan)
            if river and rule is not None:
                for d in sdays:
                    issue = fp.issue_time(first[d])
                    if rule == "spot":
                        st_ = m.get("spot_gauge")
                        sh = None if shift_row is None or st_ is None else shifts[shift_row, col[st_]]
                        F[:, di[d]] = factor(st_, issue, k, lag_rule, sh)
                    else:
                        og = m.get("overflow_gauge", {})
                        F[:, di[d]] = [factor(og.get(str(sid)), issue, k, lag_rule) for sid in up["site_id"]]
            W = fp.flow_weights(w, dil, F)
            return {name: pd.Series(fp.exposure_lead0(P[name], W, tr), index=days).reindex(sdays) for name in P}, F
        out_arm = {}
        for arm in ARMS:
            out_arm[arm] = risk(arm)
        plac = [risk("placebo", j)[0]["prod"] for j in range(fp.PLACEBO_N)] if river and m.get("spot_gauge") else []
        for d in sdays:
            r = {"bw_id": bw_id, "day": d, "river": river, "spot_gauge": m.get("spot_gauge"),
                 "realtime": bool(realtime.get(m.get("spot_gauge"), False))}
            for arm, (rk, F) in out_arm.items():
                r[f"risk_{arm}"] = float(rk["prod"][d]); r[f"hold_{arm}"] = float(rk["hold"][d])
                r[f"factor_{arm}"] = float(np.nanmean(F[:, di[d]])) if np.isfinite(F[:, di[d]]).any() else np.nan
            for j, pr in enumerate(plac):
                r[f"risk_placebo{j:03d}"] = float(pr[d])
            recs.append(r)
    t = pd.DataFrame(recs)
    # Face check: the reference arm reproduces the replay's lead-0 exposures.
    ex = pd.read_parquet(config.PROCESSED / "ecoli_exposure_leads.parquet")
    ex = ex[ex.lead == 0]
    ex["day"] = pd.to_datetime(ex["day"])
    j = t.merge(ex[["bw_id", "day", "risk_prod", "risk_holdout"]], on=["bw_id", "day"], how="inner")
    face = {"pairs": int(len(j)),
            "max_diff_prod": float(np.nanmax(np.abs(j.risk_reference - j.risk_prod))) if len(j) else None,
            "max_diff_hold": float(np.nanmax(np.abs(j.hold_reference - j.risk_holdout))) if len(j) else None}
    face["passes"] = bool(len(j) and face["max_diff_prod"] <= 1e-9 and face["max_diff_hold"] <= 1e-9)
    t.to_parquet(out / "exposures.parquet", index=False)
    (out / "face_exposure.json").write_text(json.dumps(face, indent=1))
    print("exposure face check:", json.dumps(face))
    if not face["passes"]:
        raise SystemExit("face check failed: stopping before any prediction")


# ---- predict ----------------------------------------------------------------------------------------------------
def run_predict(soil_dir: str, out: str) -> None:
    import train_ecoli as te
    from diagnostics import rows_q1
    from leads import CAND, soil_at_issue

    from dipcast import config
    from dipcast.model.ecoli import THRESHOLD, features, fit

    out = Path(out)
    rows, fc = rows_q1()
    t = pd.read_parquet(out / "exposures.parquet")
    t["day"] = pd.to_datetime(t["day"])
    if t["day"].dt.tz is None and rows["day"].dt.tz is not None:
        t["day"] = t["day"].dt.tz_localize(rows["day"].dt.tz)
    n0 = len(rows)
    rows = rows.merge(t, on=["bw_id", "day"], how="left")
    assert len(rows) == n0, "exposures are not one per (bw_id, day)"
    sm = soil_at_issue(rows, Path(soil_dir), 0)
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    lake = rows["lake"].to_numpy()
    rivers = lake == 0.0
    years = rows["sample_time"].dt.year.to_numpy()
    site = rows["bw_id"].to_numpy()
    lake_rows = ~rivers

    def X_for(col: str) -> pd.DataFrame:
        # Lake rows keep production exposure in every arm; river rows take the arm's.
        r = np.where(lake_rows, rows["risk_lead0"].to_numpy(dtype=float), rows[col].to_numpy(dtype=float))
        X = features(fc[0][0], fc[0][1], r, rows.lake, rows.sample_time)
        X["sm"] = sm
        return X

    # Face: the reference arm's river exposure equals production's, and its all-rows fit is ecoli_model_sm.json.
    ref_diff = float(np.nanmax(np.abs(rows.loc[rivers, "risk_reference"] - rows.loc[rivers, "risk_lead0"])))
    m = fit(X_for("risk_reference"), y, CAND)
    want = json.loads((config.PROCESSED / "ecoli_model_sm.json").read_text())["coef"]
    coef_diff = max(abs(m.coef[c] - want[c]) for c in CAND)
    face = {"river_exposure_max_diff": ref_diff, "coef_max_diff": coef_diff,
            "passes": bool(ref_diff <= 1e-9 and coef_diff <= 1e-9)}
    (out / "face_model.json").write_text(json.dumps(face, indent=1))
    print("model face check:", json.dumps(face))
    if not face["passes"]:
        raise SystemExit("face check failed: stopping before any prediction")

    P = pd.DataFrame({"bw_id": site, "sample_time": rows["sample_time"], "lake": lake, "year": years,
                      "river_factor": np.isfinite(rows[f"factor_{PRIMARY}"]) & rivers,
                      "realtime": rows["realtime"].fillna(False).astype(bool)})
    tr_fw, te_fw = years <= te.FORWARD_TRAIN_UNTIL, years > te.FORWARD_TRAIN_UNTIL
    for arm in ARMS:
        X = X_for(f"risk_{arm}")
        P[f"loso_{arm}"] = te.leave_one_out(X, y, site, lake, CAND)
        P[f"loyo_{arm}"] = te.leave_one_out(X, y, years, lake, CAND)
        Xh = X_for(f"hold_{arm}")
        Xh["logit_risk"] = np.where(lake_rows, features(fc[0][0], fc[0][1], rows["risk_hold_lead0"], rows.lake,
                                                        rows.sample_time)["logit_risk"], Xh["logit_risk"])
        pf = np.full(len(y), np.nan); pf[te_fw] = te._fit_predict(Xh, y, tr_fw, te_fw, CAND, lake)
        P[f"fwd_{arm}"] = pf
    for j in range(fp.PLACEBO_N):
        c = f"risk_placebo{j:03d}"
        if c not in rows:
            break
        rows[c] = rows[c].fillna(rows[f"risk_{PRIMARY}"])   # spots with no gauge: no placebo, as the candidate
        P[f"loso_placebo{j:03d}"] = te.leave_one_out(X_for(c), y, site, lake, CAND)
    pred = out / "predictions.parquet"
    P.to_parquet(pred, index=False)
    g = fp.gate(P.loc[rivers, "river_factor"].to_numpy(), site[rivers], y[rivers] == 1)
    mg = fp.margins(P.loc[rivers, "loso_reference"].to_numpy(), P.loc[rivers, f"loso_{PRIMARY}"].to_numpy())
    stmt = {"predictions_sha256": sha256(pred), "gate": g, "margins": mg,
            "note": "B and H from predictions alone (flow_protocol.margins); no score has been computed"}
    (out / "run_statement.json").write_text(json.dumps(stmt, indent=1))
    print(json.dumps(stmt, indent=1))


# ---- score ------------------------------------------------------------------------------------------------------
def run_score(out: str) -> None:
    import train_ecoli as te
    from diagnostics import rows_q1
    from sklearn.metrics import roc_auc_score

    from dipcast.model.ecoli import THRESHOLD

    out = Path(out)
    stmt = json.loads((out / "run_statement.json").read_text())
    pred = out / "predictions.parquet"
    if stmt.get("predictions_sha256") != sha256(pred):
        raise SystemExit("run_statement.json does not name these predictions")
    if not stmt["gate"]["passes"]:
        print("gate not met: too few to judge; scores follow as description only")
    B, H = stmt["margins"]["B"], stmt["margins"]["H"]
    rows, _ = rows_q1()
    P = pd.read_parquet(pred)
    assert len(P) == len(rows) and (P.bw_id.to_numpy() == rows.bw_id.to_numpy()).all()
    y = (rows["ecoli"] > THRESHOLD).astype(int).to_numpy()
    riv = P["lake"].to_numpy() == 0.0
    week = (rows["bw_id"] + "|" + rows["sample_time"].dt.strftime("%G-%V")).to_numpy()
    site = rows["bw_id"].to_numpy()

    def boot(ref, new, clusters, mask):
        b = te.cluster_bootstrap(y, P[ref].to_numpy(), P[new].to_numpy(), clusters, mask=mask.copy(),
                                 n_boot=fp.BOOT, seed=fp.BOOT_SEED)
        b["label"] = fp.label(b["brier_gain"], *b["brier_gain_ci"], B, H)
        return b

    res = {"B": B, "H": H, "gate": stmt["gate"]}
    sec = {"loso_site_clusters": boot("loso_reference", f"loso_{PRIMARY}", site, riv),
           "loyo_site_week": boot("loyo_reference", f"loyo_{PRIMARY}", week, riv),
           "realtime_gauge_rows": boot("loso_reference", f"loso_{PRIMARY}", week, riv & P["realtime"].to_numpy())}
    harm = any(v["label"] in fp.HARMFUL for v in sec.values())
    prim = te.cluster_bootstrap(y, P["loso_reference"].to_numpy(), P[f"loso_{PRIMARY}"].to_numpy(), week,
                                mask=riv.copy(), n_boot=fp.BOOT, seed=fp.BOOT_SEED)
    prim["label"] = fp.label(prim["brier_gain"], *prim["brier_gain_ci"], B, H, secondary_harm=harm)
    res["primary"], res["secondary"] = prim, sec
    br = lambda c, m: float(np.mean((P[c].to_numpy()[m] - y[m]) ** 2))
    years = P["year"].to_numpy()
    loyo_by_year = {int(v): br("loyo_reference", riv & (years == v)) - br(f"loyo_{PRIMARY}", riv & (years == v))
                    for v in np.unique(years[riv])}
    fw = riv & np.isfinite(P[f"fwd_{PRIMARY}"].to_numpy())
    plac = [br("loso_reference", riv) - br(c, riv) for c in P.columns if c.startswith("loso_placebo")]
    real = prim["brier_gain"]
    cond = {
        "1_primary_better": prim["label"] == "Better",
        "2_loyo_pooled_and_years": bool(br("loyo_reference", riv) - br(f"loyo_{PRIMARY}", riv) > 0
                                        and sum(g > 0 for g in loyo_by_year.values()) >= 2),
        "3_forward": bool(fw.any() and br("fwd_reference", fw) - br(f"fwd_{PRIMARY}", fw) > 0),
        "4_placebo": bool(len(plac) == fp.PLACEBO_N and fp.placebo_passes(real, plac)),
        "5_no_secondary_harm": not harm,
        "6_gate": bool(stmt["gate"]["passes"]),
    }
    res["conditions"], res["passes"] = cond, all(cond.values())
    res["loyo_gain_by_year"] = loyo_by_year
    res["forward_gain"] = br("fwd_reference", fw) - br(f"fwd_{PRIMARY}", fw) if fw.any() else None
    res["placebo"] = {"n": len(plac), "min": float(np.min(plac)) if plac else None,
                      "median": float(np.median(plac)) if plac else None,
                      "p95": float(np.sort(plac)[int(np.ceil(fp.LEVEL * len(plac))) - 1]) if plac else None,
                      "max": float(np.max(plac)) if plac else None}
    # Reported, deciding nothing: other arms, AUC, calibration, warnings at 0.25, by site.
    rep = {}
    for arm in ARMS:
        if arm == "reference":
            continue
        for h in ("loso", "loyo"):
            rep[f"{h}_{arm}"] = boot(f"{h}_reference", f"{h}_{arm}", week, riv)
    res["arms"] = rep
    pr = lambda c: P[c].to_numpy()[riv]
    yr = y[riv]
    res["adoption_checks"] = {
        arm: {"mean_forecast": float(pr(f"loso_{arm}").mean()), "observed": float(yr.mean()),
              "auc": float(roc_auc_score(yr, pr(f"loso_{arm}"))),
              "miss_rate_at_0.25": float(((pr(f"loso_{arm}") < fp.WARN) & (yr == 1)).sum() / max(1, (yr == 1).sum())),
              "false_alarm_rate_at_0.25": float(((pr(f"loso_{arm}") >= fp.WARN) & (yr == 0)).sum()
                                                / max(1, (yr == 0).sum()))}
        for arm in ("reference", PRIMARY)}
    rt = P["realtime"].to_numpy() & P["river_factor"].to_numpy()
    arch = ~P["realtime"].to_numpy() & P["river_factor"].to_numpy()
    groups = {"realtime_gauges": riv & rt, "archive_only_gauges": riv & arch}
    for u in sorted(set(rows.loc[riv, "undertaker"].astype(str))):
        groups[f"company: {u}"] = riv & (rows["undertaker"].astype(str).to_numpy() == u)
    res["groups"] = {k: boot("loso_reference", f"loso_{PRIMARY}", week, m) for k, m in groups.items() if m.sum() >= 30}
    res["groups_harm"] = sorted(k for k, v in res["groups"].items() if v["label"] in fp.HARMFUL)
    res["by_site"] = {s: br("loso_reference", riv & (site == s)) - br(f"loso_{PRIMARY}", riv & (site == s))
                      for s in sorted(set(site[riv]))}
    (out / "score.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("B", "H", "conditions", "passes")}, indent=1, default=float))
    print("primary:", prim["label"], prim["brier_gain"], prim["brier_gain_ci"])


if __name__ == "__main__":
    step, *args = sys.argv[1:]
    {"map": run_map, "prep": run_prep, "predict": run_predict, "score": run_score}[step](*args)
