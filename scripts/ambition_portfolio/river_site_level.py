"""Development check, SEEN rows only (rivers 2023-26): does a site's own level, learned from other seasons,
improve production's form? Leave-one-season-out. Never opens heldout.parquet."""
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
d = pd.read_parquet(sys.argv[1]); assert set(d.part)=={"seen"}
r = d[d.kind=="river"].copy().reset_index(drop=True)
F = ["lrain48","lrain24","logit_risk","doy_sin","doy_cos"]
M = 10
def fit_pred(tr, te, cols):
    mu, sd = tr[cols].mean(), tr[cols].std().replace(0,1)
    m = LogisticRegression(C=1e6, max_iter=2000).fit((tr[cols]-mu)/sd, tr.over)
    return m.predict_proba((te[cols]-mu)/sd)[:,1]
for name in ("prod_form","prod_plus_site","site_rate","prod_plus_site_dry"):
    r[name]=np.nan
for s in sorted(r.season.unique()):
    tr, te = r[r.season!=s].copy(), r[r.season==s].copy()
    pooled = tr.over.mean()
    g = tr.groupby("bw_id").over.agg(["sum","count"])
    rate = (g["sum"]+M*pooled)/(g["count"]+M)
    dry = tr[tr.rain_48h<2]; pd_ = dry.over.mean(); gd = dry.groupby("bw_id").over.agg(["sum","count"])
    drate = (gd["sum"]+M*pd_)/(gd["count"]+M)
    for x in (tr,te):
        x["site_lo"] = np.log(x.bw_id.map(rate).fillna(pooled)/(1-x.bw_id.map(rate).fillna(pooled)))
        x["dry_lo"] = np.log(x.bw_id.map(drate).fillna(pd_)/(1-x.bw_id.map(drate).fillna(pd_)))
    r.loc[te.index,"prod_form"] = fit_pred(tr,te,F)
    r.loc[te.index,"prod_plus_site"] = fit_pred(tr,te,F+["site_lo"])
    r.loc[te.index,"prod_plus_site_dry"] = fit_pred(tr,te,F+["dry_lo"])
    r.loc[te.index,"site_rate"] = te.bw_id.map(rate).fillna(pooled).values
bs = lambda p,x=r: ((x[p]-x.over)**2).mean()
print("river rows", len(r), "over 900", r.over.sum(), "sites", r.bw_id.nunique(), "seasons", sorted(r.season.unique()))
for p in ("prod_form","site_rate","prod_plus_site","prod_plus_site_dry"):
    print(f"  Brier {p:20s} {bs(p):.4f}   mean pred {r[p].mean():.3f}")
rng=np.random.default_rng(20261115); sites=r.bw_id.unique(); per={s:r[r.bw_id==s] for s in sites}
def boot(a,b,n=4000):
    out=[]
    for _ in range(n):
        x=pd.concat([per[s] for s in rng.choice(sites,len(sites))]); out.append(bs(a,x)-bs(b,x))
    return np.percentile(out,[2.5,97.5])
for a in ("prod_plus_site","prod_plus_site_dry","site_rate"):
    print(f"  {a} minus prod_form: {bs(a)-bs('prod_form'):+.4f}  95% (site bootstrap) {np.round(boot(a,'prod_form'),4)}  skill {(1-bs(a)/bs('prod_form')):.1%}")
# forward only: train 2023-24(+25) -> test next
for cut in (2025,2026):
    tr, te = r[r.season<cut].copy(), r[r.season==cut].copy()
    pooled=tr.over.mean(); g=tr.groupby("bw_id").over.agg(["sum","count"]); rate=(g["sum"]+M*pooled)/(g["count"]+M)
    for x in (tr,te):
        x["site_lo"]=np.log(x.bw_id.map(rate).fillna(pooled)/(1-x.bw_id.map(rate).fillna(pooled)))
    a=fit_pred(tr,te,F); b=fit_pred(tr,te,F+["site_lo"])
    print(f"  forward to {cut}: n {len(te)}, Brier prod_form {((a-te.over)**2).mean():.4f}, plus site {((b-te.over)**2).mean():.4f}")
# dry-day picture
dry=r[r.rain_48h<2]
print("\nDry days (rain_48h<2 mm): rows",len(dry),"over 900",dry.over.sum())
print("  mean chance from production's form on dry-day results over 900:", dry[dry.over==1].prod_form.mean().round(3), "; with site level:", dry[dry.over==1].prod_plus_site.mean().round(3))
print("  dry-day Brier prod_form", round(bs('prod_form',dry),4), "plus site", round(bs('prod_plus_site',dry),4))
top=["River Tone at French Weir Park","Sheep's Green, River Cam","Nidd at the Lido, Knaresborough"]
t=dry[dry.name.isin(top)]; print("  at Tone, Cam, Nidd dry days: n",len(t),"over",t.over.sum(),"mean prod_form chance",t.prod_form.mean().round(3),"observed rate",t.over.mean().round(3))
# calibration by site: observed vs predicted
c=r.groupby("name").agg(n=("over","size"),obs=("over","mean"),prod=("prod_form","mean"),plus=("prod_plus_site","mean")).round(2)
print(c.sort_values("obs",ascending=False).to_string())
print("site-level |obs - pred| mean: prod_form", (c.obs-c["prod"]).abs().mean().round(3), "plus site", (c.obs-c.plus).abs().mean().round(3))
