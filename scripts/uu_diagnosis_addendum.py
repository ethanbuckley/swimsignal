"""The addendum to docs/UU-DIAGNOSIS-2026-11.md (A1 and A2), stated in that file before this ran. Same rows,
models and seed as scripts/uu_diagnosis.py; same arguments, of which --v2pooled and --radar are not read.
Seen rows, chosen after the main run was read: development evidence only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ARGV = sys.argv[1:]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import uu_diagnosis as ud  # noqa: E402

ccb, lsb, lst = ud.ccb, ud.lsb, ud.lst


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("events2025", "events2026", "coverage", "zip2026", "d2", "v2pooled", "radar", "out"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    a = ap.parse_args(_ARGV)
    cands, d2, prod, cal = lsb.load_models(a)
    lsb.NINE = [ud.UU]
    b = lsb.build(a)
    test, status, leadrows = b["test"], b["status"], b["leadrows"]
    y = test["y"].to_numpy().astype(float)
    site, N = test["site_id"], len(test)
    tw = lsb.TwoWay(site.to_numpy(), lsb.week_codes(test["day"]), np.random.default_rng(ud.SEED))
    P, D2 = prod.predict(test), d2.predict(test)
    if abs(ud.brier(P, y) - ud.FACE["production"]) > ud.FACE_TOL:
        raise SystemExit("production is not reproduced")
    rows = []

    def rec(check, name, pa, pb, mask, k, **extra):
        d = (pa - y) ** 2 - (pb - y) ** 2
        lo, hi = tw.interval(d, mask)
        rows.append({"check": check, "comparison": name, "lead": k, "rows": int(mask.sum()), "difference": float(d[mask].mean()),
                     "ci_low": lo, "ci_high": hi} | extra)

    for k in (1, 2, 3, 4):
        st = status.features(site, test["day"], k)
        unknown = st.isna().any(axis=1).to_numpy()
        x = pd.concat([test.drop(columns=[c for c in lsb.STATUS if c in test]), st], axis=1)
        pc = cands[k].predict(x)
        comb = ccb.combine(P, pc, D2, unknown)
        now = st["spilling_at_issue"].to_numpy() == 1
        narrow = np.where(now, comb, P)
        rec("A1", "combined-v1 minus production, spilling at issue", comb, P, now, k, observed=float(y[now].mean()),
            mean_production=float(P[now].mean()), mean_combined=float(comb[now].mean()), overflows=int(site[now].nunique()))
        rec("A1", "combined-v1 minus production, not spilling at issue", comb, P, ~now, k)
        rec("A2", "narrow rule minus production, all rows", narrow, P, np.ones(N, bool), k,
            brier_production=ud.brier(P, y), brier_narrow=ud.brier(narrow, y))
        # forecast rain: the same rule on mapped production
        pos, fr = leadrows[k]
        r = test.iloc[pos]
        fr = fr.copy()
        fr.index = r.index
        xk = pd.concat([r[["site_id", *lst.STATIC]], fr, st.iloc[pos]], axis=1)
        f_cal = ud._apply(cal[min(k, max(cal))], prod.predict(xk))
        f_comb = ccb.combine(f_cal, cands[k].predict(xk), d2.predict(xk), unknown[pos])
        fa, fb = np.zeros(N), np.zeros(N)
        fa[pos], fb[pos] = np.where(now[pos], f_comb, f_cal), f_cal
        lm = np.zeros(N, bool)
        lm[pos] = True
        rec("A2 forecast rain", "narrow rule on mapped production minus mapped production", fa, fb, lm, k,
            spilling_rows=int(now[pos].sum()))
    out = pd.DataFrame(rows)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    out.to_csv(Path(a.out) / "addendum.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(out.to_string(index=False, float_format=lambda v: f"{v:+.5f}"))


if __name__ == "__main__":
    main()
