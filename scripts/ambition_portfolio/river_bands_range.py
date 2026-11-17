"""Development checks, SEEN river rows only (2023-26), leave-one-season-out. Never opens heldout.parquet.
(1) share over 900 by band of the season-out chance from production's form; pairs needed for a paired test.
(2) an 80% range from a log10 model with a site level: coverage on the held-out season."""
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from scipy.stats import norm, binom
d = pd.read_parquet(sys.argv[1]); assert set(d.part)=={"seen"}
r = d[d.kind=="river"].copy().reset_index(drop=True)
F = ["lrain48","lrain24","logit_risk","doy_sin","doy_cos"]
r["p"]=np.nan; r["mu"]=np.nan; r["sd"]=np.nan; r["mu_ns"]=np.nan; r["sd_ns"]=np.nan
for s in sorted(r.season.unique()):
    tr, te = r[r.season!=s], r[r.season==s]
    mu, sd = tr[F].mean(), tr[F].std()
    m = LogisticRegression(C=1e6,max_iter=2000).fit((tr[F]-mu)/sd, tr.over)
    r.loc[te.index,"p"] = m.predict_proba((te[F]-mu)/sd)[:,1]
    # log10 model, pooled slopes, site level shrunk toward the pooled level (m=10 rows)
    A = np.c_[np.ones(len(tr)), tr[F].values]; b = np.linalg.lstsq(A, tr.log_ecoli.values, rcond=None)[0]
    res = tr.log_ecoli.values - A@b
    g = pd.DataFrame({"bw":tr.bw_id.values,"res":res}).groupby("bw").res.agg(["sum","count"])
    lvl = g["sum"]/(g["count"]+10)
    At = np.c_[np.ones(len(te)), te[F].values]
    off_tr = tr.bw_id.map(lvl).fillna(0).values; s_site = np.std(res-off_tr, ddof=len(F)+1)
    r.loc[te.index,"mu"] = At@b + te.bw_id.map(lvl).fillna(0).values; r.loc[te.index,"sd"] = s_site
    r.loc[te.index,"mu_ns"] = At@b; r.loc[te.index,"sd_ns"] = np.std(res, ddof=len(F)+1)
print("(1) share over 900 by band of the season-out chance (production's form), rivers:")
bands=[(0,.1),(.1,.2),(.2,.4),(.4,.6),(.6,1.01)]
for lo,hi in bands:
    x=r[(r.p>=lo)&(r.p<hi)]
    print(f"   chance {lo:.1f}-{min(hi,1):.1f}: n {len(x):4d} ({len(x)/len(r):.0%} of samples), over 900 {x.over.mean():.0%}")
hi_=r[r.p>=.4].over.mean(); lo_=r[r.p<.1].over.mean()
print(f"   high band (>=0.4) rate {hi_:.2f}; low band (<0.1) rate {lo_:.2f}")
# pairs needed: discordant-pair sign test, one-sided 5%, power 90%
def power(n, ph, pl, sims=20000, seed=1):
    rng=np.random.default_rng(seed); a=rng.random((sims,n))<ph; b=rng.random((sims,n))<pl
    up=(a&~b).sum(1); dn=(~a&b).sum(1); k=up+dn
    pv=binom.sf(up-1, np.maximum(k,1), 0.5); pv[k==0]=1
    return (pv<0.05).mean()
for n in (10,15,20,25,30,40):
    print(f"   {n} pairs: power {power(n,hi_,lo_):.2f}; at half the gap ({(hi_+lo_)/2+ (hi_-lo_)/4:.2f} vs {(hi_+lo_)/2-(hi_-lo_)/4:.2f}): {power(n,(hi_+lo_)/2+(hi_-lo_)/4,(hi_+lo_)/2-(hi_-lo_)/4):.2f}")
print("\n(2) 80% range from a log10 model on the held-out season, rivers:")
z=norm.ppf(.9)
for lab,m_,s_ in (("with site level","mu","sd"),("no site level","mu_ns","sd_ns")):
    inside=((r.log_ecoli>=r[m_]-z*r[s_])&(r.log_ecoli<=r[m_]+z*r[s_]))
    print(f"   {lab}: residual sd {r[s_].mean():.2f} log10; inside the 80% range {inside.mean():.1%}; by season {inside.groupby(r.season).mean().round(2).to_dict()}; width x{10**(2*z*r[s_].mean()):.0f} from low end to high end")
    cs=inside.groupby(r.bw_id).mean(); print(f"      sites with coverage under 65%: {(cs<.65).sum()} of {len(cs)}; over 92%: {(cs>.92).sum()}")
from scipy.stats import spearmanr
rs=[spearmanr(g.mu,g.log_ecoli)[0] for _,g in r.groupby('bw_id') if len(g)>=15]; rp=[spearmanr(g.p,g.log_ecoli)[0] for _,g in r.groupby('bw_id') if len(g)>=15]
print(f"   within-site rho: log10 median {np.mean(rs):.3f}; production-form chance {np.mean(rp):.3f}")
print(f"   typical median {10**r.mu.median():.0f}; example range at the median: {10**(r.mu.median()-z*r.sd.mean()):.0f} to {10**(r.mu.median()+z*r.sd.mean()):.0f}")
