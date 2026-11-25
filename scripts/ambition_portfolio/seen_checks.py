"""Development checks on the bench's SEEN rows only (2023-26). Reads seen.parquet read-only.
Never opens heldout.parquet. Output: printed tables. Seen data: development evidence."""
import sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
d = pd.read_parquet(sys.argv[1])
assert set(d.part) == {"seen"}
print("rows", len(d), "sites", d.bw_id.nunique())
print(d.groupby("kind").agg(rows=("over","size"), sites=("bw_id","nunique"), over900=("over","sum"), over500=("ecoli", lambda s:(s>500).sum())))
r = d[d.kind!="lake"].copy(); l = d[d.kind=="lake"].copy()
print("\nkinds:", d.kind.unique())
print("\nRiver sites:"); print(r.groupby("name").agg(n=("over","size"), over=("over","sum"), up=("upstream","first"), med=("ecoli","median")).sort_values("over", ascending=False).to_string())

# Q1: dry-weather exceedances at rivers
def q1(x, lab):
    o = x[x.over==1]
    print(f"\n[{lab}] results over 900: {len(o)} of {len(x)}")
    for thr in (1,2,5,10):
        print(f"  with rain_48h < {thr} mm: {(o.rain_48h<thr).sum()} ({(o.rain_48h<thr).mean():.0%}); all samples under that rain: {(x.rain_48h<thr).sum()}, rate over 900 there {x[x.rain_48h<thr].over.mean():.1%}")
    med = x.groupby("bw_id").risk_model.transform("median")
    print("  over-900 with rain_48h<2 AND exposure at or below the site's median:", ((o.rain_48h<2)&(o.risk_model<=med[o.index])).sum())
q1(r,"rivers"); q1(l,"lakes")
dry = r[r.rain_48h<2]
print("\nRiver dry-day (rain_48h<2mm) rate over 900 by site (n>=10):")
t = dry.groupby("name").agg(n=("over","size"), over=("over","sum"), med=("ecoli","median"), p90=("ecoli", lambda s: s.quantile(.9)))
print(t[t.n>=10].sort_values("over", ascending=False).to_string())

# Q2: triggered sampling yield
print("\nQ2 yield of an after-rain trigger (rivers):")
for thr in (5,10,15,20):
    w = r[r.rain_48h>thr]
    print(f"  rain_48h > {thr} mm: {len(w)} samples ({len(w)/len(r):.0%} of river samples), over 900: {w.over.sum()} ({w.over.mean():.0%}); rest: {r[r.rain_48h<=thr].over.mean():.1%}")
r["rq"] = r.groupby("bw_id").risk_model.rank(pct=True)
for q in (0.8,0.9):
    w = r[r.rq>q]; print(f"  exposure in the site's top {1-q:.0%}: n {len(w)}, over 900 {w.over.mean():.0%}")
print("  lakes: rain_48h>10:", len(l[l.rain_48h>10]), "over 900", l[l.rain_48h>10].over.mean().round(3), "; rest", l[l.rain_48h<=10].over.mean().round(3))

# Q3: within-site order from rain alone vs exposure, leave-one-site-group-out
d["grp"] = d.name.str.replace(r"\s+(at|\().*$","",regex=True).str.replace(r"^(River|Lake)\s+","",regex=True)
def loso(x, cols):
    pred = pd.Series(index=x.index, dtype=float)
    for g in x.grp.unique():
        tr, te = x[x.grp!=g], x[x.grp==g]
        A = np.c_[np.ones(len(tr)), tr[cols].values]; b = np.linalg.lstsq(A, tr.log_ecoli.values, rcond=None)[0]
        pred[te.index] = np.c_[np.ones(len(te)), te[cols].values] @ b
    return pred
def rho_site(x, s):
    out=[]
    for _, g in x.groupby("bw_id"):
        if len(g)>=15 and g[s].nunique()>1:
            out.append(spearmanr(g[s], g.log_ecoli)[0])
    return np.mean(out), len(out)
def boot(x, a, b, n=2000, seed=20261115):
    rng=np.random.default_rng(seed); gs=x.grp.unique(); per={g:x[x.grp==g] for g in gs}; ds=[]
    for _ in range(n):
        s=pd.concat([per[g] for g in rng.choice(gs,len(gs))], keys=range(len(gs)))
        s=s.reset_index(level=0).rename(columns={"level_0":"k"}); s["bw_id"]=s.bw_id+"_"+s.k.astype(str)
        ds.append(rho_site(s,a)[0]-rho_site(s,b)[0])
    return np.percentile(ds,[2.5,97.5])
for lab, x in (("rivers", d[d.kind!="lake"].copy()), ("lakes", d[d.kind=="lake"].copy())):
    x["rain_only"] = loso(x, ["lrain48","lrain24","doy_sin","doy_cos"])
    x["rain_plus_exposure"] = loso(x, ["lrain48","lrain24","doy_sin","doy_cos","logit_risk"])
    print(f"\nQ3 [{lab}] mean within-site Spearman with log10 count (sites with 15+ rows), groups {x.grp.nunique()}:")
    for s in ("lrain48","risk_model","rain_only","rain_plus_exposure"):
        m,k = rho_site(x,s); print(f"  {s:20s} {m:+.3f}  ({k} sites)")
    print("  rain_plus_exposure minus rain_only, 95% (site-group bootstrap):", np.round(boot(x,"rain_plus_exposure","rain_only"),3))
    print("  rain_only minus exposure alone:", np.round(boot(x,"rain_only","risk_model"),3))
    if lab=="rivers":
        xs = x[x.upstream>0]; print("  rivers with overflows upstream:", xs.bw_id.nunique(), "sites;", "rho rain_only", round(rho_site(xs,"rain_only")[0],3), "rain+exp", round(rho_site(xs,"rain_plus_exposure")[0],3))
        # Brier-type: pooled AUC within site for over 900
        from sklearn.metrics import roc_auc_score
        for s in ("lrain48","risk_model","rain_only","rain_plus_exposure"):
            a=[roc_auc_score(g.over,g[s]) for _,g in x.groupby("bw_id") if g.over.nunique()>1 and g.over.sum()>=3]
            print(f"  within-site AUC over 900, {s:20s} {np.mean(a):.3f} ({len(a)} sites)")
