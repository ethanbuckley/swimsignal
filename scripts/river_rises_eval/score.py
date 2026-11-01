"""The river-rises evaluation run, for docs/RIVER-RISES-SCOPE-2026-10.md. Offline: reads fetch.py's tables and series
and the saved radar months; makes no request. Not before 2 November 2026, alone on the machine (no heavy-run lock).

    # stage 1: the datum rule, the gate, the fits and the test-period predictions. Prints the gate, the gauges the
    # datum rule dropped and the predictions' SHA-256.
    uv run python scripts/river_rises_eval/score.py predict --data <fetch out dir> --out <run dir>
    # the run statement: JSON naming that SHA-256. B and H are fixed (protocol.MARGINS), not the statement's.
    # stage 2: every stated figure, the six conditions, the placebo, the labels and the report.
    uv run python scripts/river_rises_eval/score.py score --data <fetch out dir> --out <run dir> --statement <file>

Stage 1 reads labels only to fit on the training period and to count the gate. It writes the test-period labels
to <run dir>/rows_d*.parquet for stage 2 and prints nothing from them. Stage 2 refuses a statement that does not
name the predictions file, or that gives B or H other than Ethan's.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from river_rises_eval import protocol as pr  # noqa: E402

from dipcast import config  # noqa: E402

# name: (population, horizon h, delay h). P3d1 is the primary; the others are stated secondaries.
CONFIGS = {"P3d1": ("in_P", 3, pr.DELAY_H), "P6d1": ("in_P", 6, pr.DELAY_H),
           "P3d3": ("in_P", 3, pr.DELAY_SENS_H), "A3d1": ("in_A", 3, pr.DELAY_H)}
MAIN = "P3d1"
JUDGED = (("C1", "R3"), ("C2", "C1"))   # candidate, reference
MODELS = ("R1", "R2", "R3", "C1", "C2")


# ------------------------------------------------------------------ inputs
def read_series(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    d = pd.read_parquet(path)
    return pd.Series(d["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(d["time"]))


def read_rain(cells: pd.DataFrame, radar: Path | None) -> pd.Series | None:
    """The hourly radar mean over a gauge's cells, from the saved months (hour-ending labels)."""
    if radar is None or cells.empty:
        return None
    per = []
    for k in sorted(set(cells["cell"])):
        files = sorted(radar.glob(f"radar_{k}_*.parquet"))
        if not files:
            continue
        d = pd.concat([pd.read_parquet(f, columns=["time", "radar_mm"]) for f in files], ignore_index=True)
        per.append(pd.Series(d["radar_mm"].to_numpy(dtype=float), index=pd.DatetimeIndex(d["time"])).groupby(level=0).first())
    return pr.cell_mean(per)


def load(data: Path, radar: Path | None) -> tuple[list[pr.Gauge], pd.DataFrame, dict[str, int]]:
    g = pd.read_csv(data / "gauges.csv", dtype={"gauge": str, "system": str, "why": str}).fillna({"why": ""})
    g = g[g["why"] == ""]
    slots = pd.read_csv(data / "slots.csv", dtype={"gauge": str, "up": str}) if (data / "slots.csv").stat().st_size > 1 else pd.DataFrame()
    cells = pd.read_csv(data / "radar_cells.csv", dtype={"gauge": str, "cell": str}) if (data / "radar_cells.csv").stat().st_size > 1 else pd.DataFrame(columns=["gauge", "cell"])
    gauges = []
    for r in g.sort_values("gauge").itertuples(index=False):
        ups = {}
        for s in slots[slots["gauge"] == r.gauge].itertuples(index=False) if len(slots) else []:
            ups[s.slot] = pr.Upstream(s.up, float(s.low), float(s.high), read_series(data / "series" / f"{s.measure}.parquet"))
        gauges.append(pr.Gauge(r.gauge, str(r.system), float(r.low), float(r.high),
                               read_series(data / "series" / f"{r.measure}.parquet"), ups.get("same"), ups.get("trib"),
                               read_rain(cells[cells["gauge"] == r.gauge], radar)))
    return gauges, g, pr.system_folds(g["system"])


def load_checked(data: Path, radar: Path | None) -> tuple[list[pr.Gauge], dict[str, int], dict]:
    """load, then the datum rule (answer 6). The folds stay those of every fetched gauge, so the rule moves no
    river system to another fold. Both stages call this, so the placebo refits on the same gauges."""
    gauges, _, folds = load(data, radar)
    kept, datum = pr.datum_rule(gauges)
    return kept, folds, datum


def kinds(gauges: list[pr.Gauge]) -> dict[str, str]:
    return {g.ref: pr.upstream_kind(g) for g in gauges}


def rows_for(gauges, folds, delay_h, **kw) -> pd.DataFrame:
    rows = pr.build_rows(gauges, pr.issue_grid(), delay_h, folds, **kw)
    for c in ["word"] + [f"period{h}" for h in pr.HORIZONS_H]:
        rows[c] = rows[c].astype("category")
    return rows


def predict_config(rows: pd.DataFrame, pop: str, h: int, has_rain: bool) -> pd.DataFrame:
    y, per = f"y{h}", f"period{h}"
    p = {"R1": pr.base_rate(rows, y, per, pop)}
    if pop == "in_A":
        p["R2"] = pr.site_words(rows, y, per, pop)
    for m in ("R3", "C1", "C2"):
        if m != "C2" or has_rain:
            p[m] = pr.cross_fold(rows, pr.LOGISTIC[m], y, per, pop)
    te = (rows[per].to_numpy() == "test") & rows[pop].to_numpy(dtype=bool)
    out = rows.loc[te, ["gauge", "system", "issue"]].reset_index(drop=True)
    for m, v in p.items():
        out[m] = v[te]
    return out


# ------------------------------------------------------------------ stage 1
def stage_predict(args) -> dict:
    gauges, folds, datum = load_checked(args.data, args.radar)
    has_rain = any(g.rain is not None for g in gauges)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "datum.json").write_text(json.dumps(datum, indent=1, default=str))
    rows = {d: rows_for(gauges, folds, d) for d in sorted({c[2] for c in CONFIGS.values()})}
    gate = pr.gate(rows[pr.DELAY_H], sum(g.same is not None for g in gauges))
    (args.out / "gate.json").write_text(json.dumps(gate, indent=1))
    preds = []
    for name, (pop, h, d) in CONFIGS.items():
        preds.append(predict_config(rows[d], pop, h, has_rain).assign(config=name))
    pred = pd.concat(preds, ignore_index=True)
    pred_path = args.out / "predictions.parquet"
    pred.to_parquet(pred_path, index=False)
    for d, r in rows.items():
        r.to_parquet(args.out / f"rows_d{d:g}.parquet", index=False)
    summary = {"made": datetime.now(UTC).isoformat(timespec="seconds"), "gauges": len(gauges),
               "systems": len(set(folds)), "folds": folds, "has_rain": has_rain,
               "predictions_sha256": pr.sha256(pred_path), "margins": pr.MARGINS, "gate": gate,
               "upstream_kind": kinds(gauges), "predictions_alone": {}}
    for name in CONFIGS:
        sub = pred[pred["config"] == name]
        summary["predictions_alone"][name] = {
            m: {"n": int(sub[m].notna().sum()), "mean": float(sub[m].mean()),
                "share_at_or_above_line": float((sub[m] >= pr.LINE).mean()),
                "deciles": [float(x) for x in np.nanpercentile(sub[m], np.arange(10, 100, 10))] if sub[m].notna().any() else [],
                "histogram_10": np.histogram(sub[m].dropna(), bins=pr.BINS, range=(0, 1))[0].tolist()}
            for m in MODELS if m in sub}
    summary["index_check"] = datum
    (args.out / "prediction_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({"gate": gate, "datum_dropped": datum["dropped"],
                      "predictions_sha256": summary["predictions_sha256"]}, indent=1, default=str))
    return summary


# ------------------------------------------------------------------ stage 2
def table(sub: pd.DataFrame, y: np.ndarray) -> dict:
    out = {}
    for m in MODELS:
        if m not in sub or sub[m].isna().all():
            continue
        p = sub[m].to_numpy(dtype=float)
        out[m] = {"brier": pr.brier(p, y), "auc": pr.auc(p, y), **pr.hit_far(p, y),
                  "skill_vs_R3": pr.skill(p, sub["R3"], y) if "R3" in sub else None,
                  "skill_vs_R1": pr.skill(p, sub["R1"], y), "rows_scored": int(np.isfinite(p).sum())}
    return out


def placebo_gains(gauges, folds, cand: str, key: pd.DataFrame) -> list[float]:
    """Brier gain of the candidate over the real reference, refitted on shifted series, N_PLACEBO times."""
    if cand == "C1":
        refs = sorted({u.ref for g in gauges for u in (g.same, g.trib) if u is not None})
    else:
        refs = sorted(g.ref for g in gauges if g.rain is not None)
    gains = []
    for shift in pr.placebo_shifts(refs, n=pr.N_PLACEBO):
        kw = {"shifts": shift} if cand == "C1" else {"rain_weeks": shift}
        rows = rows_for(gauges, folds, pr.DELAY_H, **kw)
        p = pr.cross_fold(rows, pr.LOGISTIC[cand], f"y{pr.PRIMARY_H}", f"period{pr.PRIMARY_H}", "in_P")
        m = rows[["gauge", "issue", f"y{pr.PRIMARY_H}"]].assign(p=p).merge(key, on=["gauge", "issue"])
        y = m[f"y{pr.PRIMARY_H}"].to_numpy(dtype=float)
        ok = np.isfinite(y) & np.isfinite(m["p"]) & np.isfinite(m["ref"])
        gains.append(pr.brier(m["ref"][ok], y[ok]) - pr.brier(m["p"][ok], y[ok]))
    return gains


def stage_score(args) -> dict:
    pred_path = args.out / "predictions.parquet"
    statement = pr.read_statement(args.statement, pr.sha256(pred_path))
    gate = json.loads((args.out / "gate.json").read_text())
    pred = pd.read_parquet(pred_path)
    rows = {d: pd.read_parquet(args.out / f"rows_d{d:g}.parquet") for d in sorted({c[2] for c in CONFIGS.values()})}
    gauges, folds, datum = load_checked(args.data, args.radar)
    kind = kinds(gauges)
    res = {"scored": datetime.now(UTC).isoformat(timespec="seconds"), "gate": gate,
           "statement_sha256": pr.sha256(args.statement), "predictions_sha256": statement["predictions_sha256"],
           "margins": statement["margins"], "datum": datum, "upstream_kind": kind, "configs": {}, "judged": {}}
    joined = {}
    for name, (_pop, h, d) in CONFIGS.items():
        sub = pred[pred["config"] == name].merge(rows[d][["gauge", "issue", f"y{h}"]], on=["gauge", "issue"])
        joined[name] = sub
        y = sub[f"y{h}"].to_numpy(dtype=float)
        res["configs"][name] = {"rows_with_label": int(np.isfinite(y).sum()), "events": int(np.nansum(y)),
                                "pooled": table(sub, y)}
    main = joined[MAIN]
    y = main[f"y{pr.PRIMARY_H}"].to_numpy(dtype=float)
    res["configs"][MAIN]["reliability"] = {m: pr.reliability(main[m], y) for m in MODELS if m in main}
    res["configs"][MAIN]["by_system"] = {s: table(g, g[f"y{pr.PRIMARY_H}"].to_numpy(dtype=float))
                                         for s, g in main.groupby("system")}
    res["configs"][MAIN]["by_gauge"] = {s: table(g, g[f"y{pr.PRIMARY_H}"].to_numpy(dtype=float))
                                        for s, g in main.groupby("gauge")}
    by_kind = {}
    for k, g in main.groupby(main["gauge"].map(kind).fillna("none"), sort=True):
        yk = g[f"y{pr.PRIMARY_H}"].to_numpy(dtype=float)
        by_kind[str(k)] = {"gauges": int(g["gauge"].nunique()), "rows_with_label": int(np.isfinite(yk).sum()),
                           "events": int(np.nansum(yk)), "pooled": table(g, yk),
                           "skill": {f"{c} vs {r}": pr.skill(g[c], g[r], yk) for c, r in JUDGED if c in g and r in g}}
    res["configs"][MAIN]["by_upstream_kind"] = by_kind
    full = rows[pr.DELAY_H][["gauge", "system", "issue", "word"]]
    for cand, ref in JUDGED:
        if cand not in main or ref not in main:
            res["judged"][cand] = {"why": f"no {cand} or {ref} predictions"}
            continue
        boot = pr.cluster_skill(y, main[cand], main[ref], main["system"])
        leads = pr.lead_gained(full.merge(main[["gauge", "issue", cand]], on=["gauge", "issue"], how="left"), cand)
        s3 = joined["P3d3"]
        skill_d3 = pr.skill(s3[cand], s3[ref], s3[f"y{pr.PRIMARY_H}"])
        key = main[["gauge", "issue"]].assign(ref=main[ref].to_numpy())
        real = pr.brier(main[ref], y) - pr.brier(main[cand], y)
        pl = pr.placebo_holds(real, placebo_gains(gauges, folds, cand, key))
        conds = pr.conditions(y, main[cand], main[ref], main["system"], gate["episodes_by_system"], leads, skill_d3, pl, boot)
        secondary = {}
        for name in ("P3d3", "A3d1"):
            s = joined[name]
            secondary[name] = pr.cluster_skill(s[f"y{pr.PRIMARY_H}"], s[cand], s[ref], s["system"])
        B, H = float(pr.MARGINS[cand]["B"]), float(pr.MARGINS[cand]["H"])
        for v in secondary.values():
            v["label"] = pr.nearmiss_label(v["d"], v["L"], v["U"], B, H)
        harm = any(v["label"] in pr.SECONDARY_HARM for v in secondary.values())
        s6 = joined["P6d1"]
        res["judged"][cand] = {
            "against": ref, "conditions": conds, "verdict": pr.verdict(gate["judged"], conds),
            "label": pr.nearmiss_label(boot["d"], boot["L"], boot["U"], B, H, secondary_harm=harm), "B": B, "H": H,
            "secondary": secondary, "leads": leads.assign(onset=leads["onset"].astype(str)).to_dict("records"),
            "horizon_6h": pr.cluster_skill(s6["y6"], s6[cand], s6[ref], s6["system"])}
    (args.out / "result.json").write_text(json.dumps(res, indent=1, default=str))
    write_report(res, args.out / "report.md")
    print((args.out / "report.md").read_text())
    return res


# ------------------------------------------------------------------ the report
def f(x, n=4) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{n}f}" if isinstance(x, float) else str(x)


def write_report(res: dict, path: Path) -> None:
    """A plain summary of result.json: gate first, then each judged comparison, then the pooled tables."""
    g = res["gate"]
    L = ["# River rises: evaluation result", "",
         f"Scored {res['scored']}. Predictions SHA-256 `{res['predictions_sha256']}`; statement SHA-256 `{res['statement_sha256']}`.", "",
         "## Gate (checked before any score)", "",
         f"- Spot gauges with a pair: {g['paired_gauges']} (needs {pr.GATE_PAIRED_GAUGES}).",
         f"- Share of hourly issue times with a label: training {f(g['labelled_share'].get('train'), 3)}, "
         f"test {f(g['labelled_share'].get('test'), 3)} (needs {pr.GATE_LABELLED} in both).",
         f"- Label-1 episodes in P, test period: {g['episodes']} at {g['gauges_with_episode']} gauges in "
         f"{g['systems_with_episode']} river systems (needs {pr.GATE_EPISODES}, {pr.GATE_EP_GAUGES}, {pr.GATE_EP_SYSTEMS}).",
         f"- **{'Met' if g['judged'] else 'Not met: the scores below are description only, and nothing can pass'}.**", "",
         "Each gauge's share of hourly issue times with a label (reported; the gate uses the pooled share above):", "",
         "| Spot gauge | Training | Test |", "|---|---|---|"]
    for ref, sh in sorted(g.get("labelled_share_by_gauge", {}).items()):
        L.append(f"| {ref} | {f(sh.get('train'), 3)} | {f(sh.get('test'), 3)} |")
    dm = res.get("datum", {})
    lo, hi = dm.get("rule", pr.DATUM_INDEX)
    L += ["", "## Datum rule (stage 1, before any prediction)", "",
          f"A spot or upstream gauge whose training-period index median lies outside {lo} to {hi} is dropped."]
    if dm.get("dropped"):
        L += ["", "| Gauge | Role | Spot gauge | Median | 5th pct | 95th pct | Issue times | Why |",
              "|---|---|---|---|---|---|---|---|"]
        for d in dm["dropped"]:
            L.append(f"| {d['gauge']} | {d['role']} | {d['of'] or ''} | {f(d['median'], 3)} | {f(d['p5'], 3)} | "
                     f"{f(d['p95'], 3)} | {d['n']} | {d['why']} |")
    else:
        L.append("None dropped.")
    if dm.get("unchecked"):
        L += ["", "No training-period reading, so not checked (kept): "
              + ", ".join(f"{u['gauge']} ({u['role']})" for u in dm["unchecked"]) + "."]
    L.append("")
    for cand, j in res["judged"].items():
        L += [f"## {cand} against {j.get('against', '?')} (population P, 3 h, d = 1 h)", ""]
        if "conditions" not in j:
            L += [f"Not judged: {j['why']}.", ""]
            continue
        c = j["conditions"]
        L += [f"- 1. Brier skill {f(c['1']['d'])}, 95% interval {f(c['1']['L'])} to {f(c['1']['U'])} "
              f"({c['1']['clusters']} river systems): {'holds' if c['1']['holds'] else 'fails'}.",
              f"- 2. Skill above 0 in {c['2']['positive']} of {c['2']['systems']} river systems with "
              f"{pr.SYSTEM_EPISODES}+ episodes (needs {c['2']['needed']}): {'holds' if c['2']['holds'] else 'fails'}.",
              f"- 3. At {pr.LINE}: hit rate {f(c['3']['hit_rate'], 3)}, false-alarm ratio {f(c['3']['false_alarm_ratio'], 3)}: "
              f"{'holds' if c['3']['holds'] else 'fails'}.",
              f"- 4. Median lead gained {f(c['4']['median_lead_h'], 2)} h on {c['4']['caught']} of {c['4']['onsets']} onsets "
              f"caught: {'holds' if c['4']['holds'] else 'fails'}.",
              f"- 5. With d = 3 h, skill {f(c['5']['skill_d3'])}: {'holds' if c['5']['holds'] else 'fails'}.",
              f"- 6. Placebo: real gain {f(c['6']['real_gain'], 5)}, 95th percentile of {c['6']['draws']} shifts "
              f"{f(c['6']['p95'], 5)}: {'holds' if c['6']['holds'] else 'fails'}.",
              "", f"**Verdict: {j['verdict']}.** Near-miss label (B {f(j['B'])}, H {f(j['H'])}): **{j['label']}**.", "",
              "Secondary comparisons (own bootstrap, same B and H): "
              + "; ".join(f"{k} skill {f(v['d'])} [{f(v['L'])}, {f(v['U'])}], {v['label']}" for k, v in j["secondary"].items())
              + f". At 6 h: skill {f(j['horizon_6h']['d'])} [{f(j['horizon_6h']['L'])}, {f(j['horizon_6h']['U'])}].", ""]
        if j["label"] == "Promising, not shown":
            L += ["\"Promising, not shown\" leads to a winter shadow log under the forward step's conditions "
                  "(docs/LAKE-ECOLI-LINE-TEST-2026-10.md). Nothing reaches the site from this label; only a pass could.", ""]
    L += ["## By upstream gauge kind (reported apart; the conditions above are pooled)", "",
          "| Kind | Spot gauges | Rows with a label | Events | C1 skill vs R3 | C2 skill vs C1 |", "|---|---|---|---|---|---|"]
    for k, b in res["configs"].get(MAIN, {}).get("by_upstream_kind", {}).items():
        L.append(f"| {k} | {b['gauges']} | {b['rows_with_label']} | {b['events']} | "
                 f"{f(b['skill'].get('C1 vs R3'))} | {f(b['skill'].get('C2 vs C1'))} |")
    L += ["", "## Pooled scores", "", "| Config | Model | Brier | Skill vs R3 | Skill vs R1 | AUC | Hit rate | False-alarm ratio |",
          "|---|---|---|---|---|---|---|---|"]
    for name, cfg in res["configs"].items():
        for m, t in cfg["pooled"].items():
            L.append(f"| {name} | {m} | {f(t['brier'], 5)} | {f(t['skill_vs_R3'])} | {f(t['skill_vs_R1'])} | {f(t['auc'], 3)} | "
                     f"{f(t['hit_rate'], 3)} | {f(t['false_alarm_ratio'], 3)} |")
    L += ["", "By river system, by spot gauge and reliability: result.json.", "",
          "Whatever the result, nothing on the site changes because of this test."]
    path.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("predict", "score"))
    ap.add_argument("--data", type=Path, required=True, help="fetch.py's --out directory")
    ap.add_argument("--out", type=Path, required=True, help="this run's directory (outside git)")
    ap.add_argument("--radar", type=Path, default=config.RAW / "met_office_radar", help="saved radar months, read only")
    ap.add_argument("--statement", type=Path, help="score: the run statement (JSON) with B and H")
    args = ap.parse_args(argv)
    if datetime.now(UTC) < pr.NOT_BEFORE:
        raise SystemExit(f"the plan runs no earlier than {pr.NOT_BEFORE:%d %B %Y}")
    if args.radar and not args.radar.exists():
        args.radar = None
    stage_predict(args) if args.stage == "predict" else stage_score(args)


if __name__ == "__main__":
    main()
