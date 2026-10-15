"""H3a and H3b of docs/URBAN-DILUTION-DIAGNOSIS-2026-10.md. Reads trace.pkl and the chain rows of roots/flow and
roots/urban. Run from the worktree with uv (imports dipcast.model.transport for the dilution formulas)."""
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from dipcast.model import transport as T

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
tr = pickle.loads((HERE / "trace.pkl").read_bytes())["sites"]


def rows(v):
    r = pd.read_parquet(HERE / "roots" / v / "data/processed/ecoli_validation_rows.parquet")
    return r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"]).copy()


rf, ru = rows("flow"), rows("urban")
assert rf[["bw_id", "sample_time"]].reset_index(drop=True).equals(ru[["bw_id", "sample_time"]].reset_index(drop=True))
out = {}


def weights(s, mode, A=None):
    if mode == "flow":
        return s["base"] * float(T.flow_dilution(s["spot_up_m"]))
    return s["base"] * np.asarray(T.urban_dilution(s["A"] if A is None else A, s["spot_up_m"]), float)


def effects(s, mode):
    return np.clip(s["E"] * weights(s, mode)[:, None], 0, 1)          # (n_overflows, n_sample_days)


# identity: the replay must give the chain's risk_model on every row, for both modes
worst = {}
for mode, r in (("flow", rf), ("urban", ru)):
    err = []
    for bw, g in r.groupby("bw_id"):
        s = tr[bw]
        risk = 1 - np.prod(1 - effects(s, mode), axis=0)
        pos = s["sample_days"].get_indexer(g["sample_time"].dt.floor("D"))
        assert (pos >= 0).all()
        err.append(np.abs(risk[pos] - g["risk_model"].to_numpy()).max())
    worst[mode] = float(max(err))
out["identity max abs error (replay vs chain risk_model)"] = worst
ok = all(v <= 1e-9 for v in worst.values())
out["identity passes (<= 1e-9)"] = ok

# H3a: per site
sm = pd.DataFrame({"flow": rf.groupby("bw_id").risk_model.mean(), "urban": ru.groupby("bw_id").risk_model.mean(),
                   "log_ecoli": ru.groupby("bw_id").log_ecoli.mean(), "n": ru.groupby("bw_id").size()})
sm["name"] = [tr[b]["name"] for b in sm.index]
sm["kind"] = [tr[b]["kind"] for b in sm.index]
sm["rank_flow"], sm["rank_urban"], sm["rank_ecoli"] = sm["flow"].rank(), sm["urban"].rank(), sm["log_ecoli"].rank()
sm["rank_change"] = sm["rank_urban"] - sm["rank_flow"]
sm["log10_ratio"] = np.log10(sm["urban"] / sm["flow"])
sm["err_flow"], sm["err_urban"] = sm["rank_flow"] - sm["rank_ecoli"], sm["rank_urban"] - sm["rank_ecoli"]
out["sites"] = len(sm)
out["cross-site rho flow, urban"] = [float(spearmanr(sm.flow, sm.log_ecoli).statistic), float(spearmanr(sm.urban, sm.log_ecoli).statistic)]
out["sum |rank error| flow, urban"] = [float(sm.err_flow.abs().sum()), float(sm.err_urban.abs().sum())]

# H3b: per overflow, hazard -ln(1 - e) summed over the site's rows
recs = []
if ok:
    for bw, g in ru.groupby("bw_id"):
        s = tr[bw]
        pos = s["sample_days"].get_indexer(g["sample_time"].dt.floor("D"))
        hf = -np.log1p(-np.clip(effects(s, "flow")[:, pos], 0, 1 - 1e-12)).sum(axis=1)
        hu = -np.log1p(-np.clip(effects(s, "urban")[:, pos], 0, 1 - 1e-12)).sum(axis=1)
        for i, sid in enumerate(s["site_ids"]):
            recs.append({"bw_id": bw, "site": s["name"], "overflow": sid, "A": float(np.clip(s["A"][i], 0.1, 6.0)),
                         "h_flow": hf[i], "h_urban": hu[i], "delta": hu[i] - hf[i], "rows": len(g)})
    d = pd.DataFrame(recs)
    d["group"] = np.select([d.A >= 6.0, d.A >= 2.0, d.A <= 0.1], ["cap", "large (2-6)", "floor"], "middle")
    d["group2"] = np.where(d.A >= 2.0, "large", np.where(d.A <= 0.1, "floor", "middle"))
    tot = d.delta.abs().sum()
    out["H3b overflow-site pairs"] = len(d)
    out["H3b distinct overflows"] = int(d.overflow.nunique())
    g2 = d.groupby("group2").agg(pairs=("overflow", "size"), share_abs_delta=("delta", lambda x: x.abs().sum() / tot),
                                 sum_delta=("delta", "sum"), share_h_urban=("h_urban", "sum"), share_h_flow=("h_flow", "sum"))
    g2["share_h_urban"] /= d.h_urban.sum(); g2["share_h_flow"] /= d.h_flow.sum()
    g2["share_pairs"] = g2.pairs / len(d)
    out["H3b by group (large = A>=2 incl. cap; floor = 0.1)"] = g2.round(4).reset_index().to_dict("records")
    out["H3b cap only (A=6)"] = {"pairs": int((d.group == "cap").sum()), "share_abs_delta": float(d[d.group == "cap"].delta.abs().sum() / tot)}
    top = d.reindex(d.delta.abs().sort_values(ascending=False).index)
    top["cum_share"] = top.delta.abs().cumsum() / tot
    out["H3b top 15 overflow-site pairs by |delta|"] = top.head(15)[["site", "overflow", "A", "h_flow", "h_urban", "delta", "cum_share"]].round(4).to_dict("records")
    out["H3b pairs making 50% / 90% of sum |delta|"] = [int((top.cum_share < 0.5).sum() + 1), int((top.cum_share < 0.9).sum() + 1)]
    # per site: the group making most of its change
    ps = d.groupby(["bw_id", "group2"]).delta.sum().unstack(fill_value=0.0)
    sm = sm.join(ps.add_prefix("delta_"))
    d.to_csv(HERE / "h3b_pairs.csv", index=False)
cols = ["name", "kind", "n", "flow", "urban", "log10_ratio", "rank_ecoli", "rank_flow", "rank_urban", "rank_change", "err_flow", "err_urban"] + \
    [c for c in sm.columns if c.startswith("delta_")]
sm = sm[cols].sort_values("rank_change", key=abs, ascending=False)
sm.to_csv(HERE / "h3a_sites.csv")
out["H3a sites (sorted by |rank change|)"] = sm.round(4).reset_index().to_dict("records")
print(json.dumps(out, indent=1, default=float))
(HERE / "h3.json").write_text(json.dumps(out, indent=1, default=float))
