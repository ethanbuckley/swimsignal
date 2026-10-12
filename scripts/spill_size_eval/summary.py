"""From PR #172 (scripts/urban_diagnosis/), unchanged but for this line. The measures of every finished variant, from each root's own outputs. Writes summary.csv.
Cross-site rho is recomputed unrounded from the rows (validate_ecoli_combined.between_site rounds it)."""
import json
import os
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
FULL = "rain + spill exposure + season (dipcast)"
out = []
for d in sorted((HERE / "logs").iterdir()):
    if not (d / "done").exists():
        continue
    p = HERE / "roots" / d.name / "data/processed"
    e = json.loads((p / "ecoli_model_eval.json").read_text())
    c = json.loads((p / "ecoli_validation_combined.json").read_text())
    r = pd.read_parquet(p / "ecoli_validation_rows.parquet")
    r = r[r.upstream > 0].dropna(subset=["rain_48h", "rain_24h", "risk_model", "log_ecoli"])
    s = r.groupby("bw_id").agg(risk=("risk_model", "mean"), ecoli=("log_ecoli", "mean"))
    rec = {"variant": d.name, "n": e["n_samples"]}
    for split in ("loyo", "loso"):
        t = {x["model"]: x for x in e[split]}[FULL]
        rec[f"{split}_brier"], rec[f"{split}_auc"], rec[f"{split}_auc_rivers"] = t["brier"], t["auc"], t["auc_river"]
    t = {x["model"]: x for x in e["forward"]["table"]}[FULL]
    rec["fwd_brier"], rec["fwd_auc"] = t["brier"], t["auc"]
    rec["cross_site_rho"] = float(spearmanr(s.risk, s.ecoli).statistic)
    rec["cross_site_rho_json"] = c["between_site_rho_risk"]
    rec["sites"] = len(s)
    rec["secs"] = int((d / "done").read_text()) - int((d / "start").read_text())
    rec["net_attempts"] = sum(int(l.split(":")[1]) for f in d.glob("*.log") for l in f.read_text().splitlines()
                              if l.startswith("network attempts:"))
    out.append(rec)
df = pd.DataFrame(out).set_index("variant")
df.to_csv(HERE / "summary.csv")
pd.set_option("display.width", 250)
print(df.round(4).to_string())
