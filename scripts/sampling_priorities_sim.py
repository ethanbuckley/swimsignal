"""The stated simulation of docs/SAMPLING-PRIORITIES-SIM-2026-10.md: does the informativeness plan learn site rates
better than a coverage plan and a random plan, for the same budget, in a synthetic world?

One process, no network, no file read. Writes the per-replication metrics and the summary to --out (JSON).

    uv run python scripts/sampling_priorities_sim.py --out docs/SAMPLING-PRIORITIES-SIM-2026-10.json
    uv run python scripts/sampling_priorities_sim.py --reps 100 --tau 0 --out ...      # sensitivity: no site offsets
    uv run python scripts/sampling_priorities_sim.py --reps 100 --per-week 6 --out ... # sensitivity: budget 120
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

from dipcast.sampling_priorities import (COLS_A, COLS_B, GH_WEIGHTS, WEEKDAYS, _member_chances, fit_ensemble,
                                         forecast_view, history_rows, plan, score_candidates, synthetic_world)

STRATEGIES = ("INFO", "COVER", "RANDOM", "RISK")
WEEKS = 20
PER_DAY = 2
N_BOOT = 20


def allowed(day_count: dict, site_day: set, site, day) -> bool:
    return day_count.get(day, 0) < PER_DAY and (site, day) not in site_day


def take(rows: pd.DataFrame, order, k: int) -> list:
    """The first k rows of `order` (index labels) within the limits."""
    day_count, site_day, out = {}, set(), []
    for i in order:
        s, d = rows.at[i, "site"], rows.at[i, "day"]
        if allowed(day_count, site_day, s, d):
            out.append(i); day_count[d] = day_count.get(d, 0) + 1; site_day.add((s, d))
        if len(out) == k:
            break
    return out


def site_rates(ens, held: pd.DataFrame) -> tuple[pd.Series, float]:
    """Predicted site rate over the held-out days, and the mean over sites of its variance across refits and nodes."""
    p = ens.predict(held, held["site"].to_numpy())
    rate = pd.Series(p, index=held.index).groupby(held["site"]).mean()
    i = ens.site_index(held["site"].to_numpy())
    pm = _member_chances(ens, held, i, *ens.offsets())                  # members x nodes x rows
    codes, uniq = pd.factorize(held["site"])
    sums = np.stack([np.bincount(codes, row, len(uniq)) for row in pm.reshape(-1, pm.shape[2])])
    r = (sums / np.bincount(codes, minlength=len(uniq))).reshape(pm.shape[0], pm.shape[1], len(uniq))
    w = GH_WEIGHTS[None, :, None] / pm.shape[0]
    mean = (r * w).sum((0, 1))
    var = ((r - mean) ** 2 * w).sum((0, 1))
    return rate, float(var.mean())


def run_rep(r: int, tau: float, per_week: int) -> dict:
    gamma = 0.0 if r % 2 == 0 else 0.6
    w = synthetic_world(20261026 + r, tau=tau, gamma=gamma)
    hist = history_rows(w, 1000000 + r)
    names = w.sites["site"].tolist()
    A = fit_ensemble(hist, hist.y, hist.site, COLS_A, "A", names, n_boot=N_BOOT, seed=r)
    B = fit_ensemble(hist, hist.y, hist.site, COLS_B, "B", names, n_boot=N_BOOT, seed=r)
    season = w.days[(w.days.season == 2) & (w.days.dow < WEEKDAYS)]
    held = w.days[(w.days.season == 3) & (w.days.dow < WEEKDAYS)]
    rng = np.random.default_rng(4000000 + r)
    fc = forecast_view(season, rng)
    U = pd.Series(rng.random(len(season)), index=season.index)
    true_rate = held.groupby("site")["p_true"].mean()
    never = set(w.sites.loc[~w.sites.sampled, "site"])

    rng_random, rng_cover = np.random.default_rng(2000000 + r), np.random.default_rng(3000000 + r)
    picks = {s: [] for s in STRATEGIES}
    state = None
    counts = hist["site"].value_counts().reindex(names, fill_value=0)
    for wk in range(WEEKS):
        cand = fc[fc.week == wk]
        got, state = plan(cand, A, B, budget=per_week, per_day=PER_DAY, state=state)
        picks["INFO"] += list(got.index)
        picks["RANDOM"] += take(cand, rng_random.permutation(cand.index.to_numpy()), per_week)
        sc = score_candidates(cand, A, B)
        picks["RISK"] += take(cand, sc.sort_values("p_mean", ascending=False, kind="stable").index, per_week)
        perm = rng_cover.permutation(names)
        order = counts.loc[perm].sort_values(kind="stable").index
        chosen, day_count = [], {}
        for s in order:
            days = [d for d in rng_cover.permutation(cand.loc[cand.site == s, "day"].to_numpy())
                    if day_count.get(d, 0) < PER_DAY]
            if days:
                d = days[0]
                chosen.append(cand.index[(cand.site == s) & (cand.day == d)][0]); day_count[d] = day_count.get(d, 0) + 1
            if len(chosen) == per_week:
                break
        picks["COVER"] += chosen
        counts.loc[[season.at[i, "site"] for i in chosen]] += 1

    # the history-only fit (U1): no new rows, so the pick is A
    base_rate, _ = site_rates(A, held)
    out = {"r": r, "gamma": gamma, "tau_fit_history": A.tau,
           "P_history_only": float(((base_rate - true_rate) ** 2).mean())}
    sets = {}
    for s in STRATEGIES:
        idx = picks[s]
        new = season.loc[idx].assign(y=(U.loc[idx] < season.loc[idx, "p_true"]).astype(int).to_numpy())
        sets[s] = set(zip(new.site, new.week, strict=True))
        ll = {}
        for name, ens in (("A", A), ("B", B)):
            p = np.clip(ens.predict(new, new["site"].to_numpy()), 1e-9, 1 - 1e-9)
            ll[name] = float(-np.mean(new.y * np.log(p) + (1 - new.y) * np.log(1 - p)))
        pick = "B" if ll["B"] < ll["A"] else "A"
        data = pd.concat([hist, new], ignore_index=True)
        ens = fit_ensemble(data, data.y, data.site, COLS_B if pick == "B" else COLS_A, pick, names,
                           n_boot=N_BOOT, seed=r)
        rate, spread = site_rates(ens, held)
        err = (rate - true_rate) ** 2
        p_day = ens.predict(held, held["site"].to_numpy())
        out[s] = {"P": float(err.mean()), "P_never": float(err[err.index.isin(never)].mean()),
                  "P_sampled": float(err[~err.index.isin(never)].mean()),
                  "S1": float(np.mean((p_day - held["p_true"].to_numpy()) ** 2)), "S2": spread,
                  "pick": pick, "pick_right": pick == ("B" if gamma > 0 else "A"),
                  "S4_exceedances": int(new.y.sum()), "expected_exceedances": float(new.p_true.sum()),
                  "n": len(new), "share_never_sampled_sites": float(new.site.isin(never).mean()),
                  "share_lakes": float((new.kind == "lake").mean()),
                  "mean_rain48": float(new.rain_48h.mean()), "sites_visited": int(new.site.nunique())}
    out["overlap_info_cover"] = len(sets["INFO"] & sets["COVER"]) / max(1, len(sets["INFO"]))
    return out


def boot_ci(d: np.ndarray, n: int = 2000, seed: int = 1) -> list[float]:
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(1)
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def summarise(reps: list[dict]) -> dict:
    P = {s: np.array([x[s]["P"] for x in reps]) for s in STRATEGIES}
    summ = {"n_reps": len(reps), "by_strategy": {}}
    for s in STRATEGIES:
        summ["by_strategy"][s] = {k: float(np.mean([x[s][k] for x in reps]))
                                  for k in ("P", "P_never", "P_sampled", "S1", "S2", "S4_exceedances",
                                            "expected_exceedances", "share_never_sampled_sites", "share_lakes",
                                            "mean_rain48", "sites_visited")}
        for g, lab in ((0.0, "truth_A"), (0.6, "truth_B")):
            sub = [x[s]["pick_right"] for x in reps if x["gamma"] == g]
            summ["by_strategy"][s][f"S3_pick_right_{lab}"] = float(np.mean(sub)) if sub else None
    rule = {}
    for base in ("COVER", "RANDOM"):
        d = P[base] - P["INFO"]
        ci = boot_ci(d)
        rule[base] = {"share_info_lower": float((d > 0).mean()), "mean_gain": float(d.mean()), "ci95": ci,
                      "relative_gain": float(d.mean() / P[base].mean()),
                      "cond1": bool((d > 0).mean() >= 0.6), "cond2": bool(ci[0] > 0)}
    risk_d = P["RANDOM"] - P["RISK"]
    rule["RISK_vs_RANDOM_description"] = {"share_risk_lower": float((risk_d > 0).mean()),
                                          "mean_gain": float(risk_d.mean()), "ci95": boot_ci(risk_d)}
    hist_P = float(np.mean([x["P_history_only"] for x in reps]))
    means = [P[s].mean() for s in ("INFO", "COVER", "RANDOM")]
    u1 = not P["RANDOM"].mean() < hist_P
    u2 = all(abs(m - P["RANDOM"].mean()) < 0.02 * P["RANDOM"].mean() for m in means)
    u3 = float(np.mean([x["overlap_info_cover"] for x in reps]))
    passed = all(rule[b]["cond1"] and rule[b]["cond2"] for b in ("COVER", "RANDOM"))
    verdict = "uninformative" if (u1 or u2 or u3 > 0.8) else ("pass" if passed else "fail")
    summ.update(rule=rule, P_history_only=hist_P, U1_broken=u1, U2_no_useful_difference=u2,
                U3_overlap_info_cover=u3, verdict=verdict)
    return summ


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--tau", type=float, default=0.7)
    ap.add_argument("--per-week", type=int, default=3)
    ap.add_argument("--first", type=int, default=0, help="first replication; the stated run starts at 0")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    reps = []
    for r in range(a.first, a.first + a.reps):
        reps.append(run_rep(r, a.tau, a.per_week))
        if len(reps) % 20 == 0:
            print(f"{len(reps)} replications, {time.time() - t0:.0f} s", flush=True)
    summ = summarise(reps)
    summ.update(first=a.first, tau_world=a.tau, budget=a.per_week * WEEKS, seconds=round(time.time() - t0, 1))
    print(json.dumps(summ, indent=1))
    with open(a.out, "w") as f:
        json.dump({"summary": summ, "replications": reps}, f, indent=1)


if __name__ == "__main__":
    main()
