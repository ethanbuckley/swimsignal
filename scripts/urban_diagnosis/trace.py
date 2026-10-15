"""H3b: a replay of validate_ecoli.py's risk_model that keeps each overflow's daily effect apart.

For each bathing water: the upstream overflows (dilution 'urban'), their spill probabilities on a
continuous daily grid exactly as validate_ecoli.main computes them, shifted by travel time and clipped
(transport.daily_effects without the weight), kept on the sample days only. With base_i, the weight
without its dilution term, the exposure for any A vector is
    risk = 1 - prod_i (1 - E_i * base_i * urban_dilution(A_i, spot))
and for 'flow' the same with flow_dilution(spot). Run with DIPCAST_DILUTION_MODE=urban and a root
whose overflow_urban_area.parquet is the real one. Writes trace.pkl next to this file.
"""
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate_ecoli as V

from dipcast import config
from dipcast.model import transport as T

HERE = Path(os.environ["DIAG_DIR"])   # roots/, logs/, tables/ and outputs
assert config.DILUTION_MODE == "urban" and config.VELOCITY_MODE == "fixed"

samples = pd.read_parquet(config.RAW / "bwq_samples.parquet").dropna(subset=["ecoli", "sample_time"]).copy()
samples["day"] = samples["sample_time"].dt.floor("D")
net = V.RiverNetwork.load(); ov = V.load_overflows(net)
model = V.SpillModel.load()
rain = V.load_rain()
daily = V.daily_rain_features(rain)
del rain
cols = ["site_id", "lat", "lon", "company", "lta_spills", "spill_hours", "edm_operational_pct"]
sites = {}
for bw_id, g in samples.groupby("bw_id"):
    s = g.iloc[0]
    pin = T.locate_pin(net, float(s.lon), float(s.lat))
    up = T.upstream_overflows(net, pin, ov, velocity_ms=T.river_velocity(None))
    sample_days = pd.DatetimeIndex(sorted(g["day"].unique()))
    if not len(up):
        continue
    spot = net.upstream_m.get(pin.trace_node, 0.0) + (pin.trace_offset_m if pin.mode == "river" else 0.0)
    A = T.overflow_urban_km2(up).to_numpy(float)
    base = up["weight"].to_numpy(float) / np.asarray(T.urban_dilution(A, spot), float)
    upf = T.upstream_overflows(net, pin, ov, velocity_ms=T.river_velocity(None), dilution_mode="flow")
    wf = upf.set_index("site_id")["weight"].reindex(up["site_id"]).to_numpy(float)
    assert np.allclose(wf, base * float(T.flow_dilution(spot)), rtol=1e-12, atol=0), bw_id   # internal check
    lead_days = T.history_days(up["travel_h"])
    days = pd.date_range(sample_days.min() - pd.Timedelta(days=lead_days), sample_days.max(), freq="D")
    sd = V.build_site_days(up[cols], daily, days)
    sd = sd.astype({f: np.float32 for f in V.ALL_FEATURES}).fillna({f: 0.0 for f in V.ALL_FEATURES})
    sd["p"] = model.predict(sd)
    mat = sd.pivot(index="site_id", columns="day", values="p").reindex(index=up["site_id"], columns=days)
    pm = V.calibrate_at_lead(np.nan_to_num(mat.to_numpy(dtype=float)), lead=0)
    tr = up["travel_h"].to_numpy(float)
    E = np.clip(T.shift_by_travel(np.nan_to_num(pm, nan=0.0), tr), 0, 1)
    pos = days.get_indexer(sample_days)
    assert (pos >= 0).all()
    # check: the chain's own combine_daily with the urban weights, on the sample days
    risk_chain = T.combine_daily(pm, up["weight"].to_numpy(float), tr)[pos]
    sites[bw_id] = {"name": s["name"], "kind": s["kind"], "mode": pin.mode, "spot_up_m": spot, "sample_days": sample_days,
                    "site_ids": up["site_id"].to_numpy(), "A": A, "base": base, "travel_h": tr,
                    "E": E[:, pos], "risk_urban_chainfn": risk_chain}
    print(bw_id, s["name"], len(up), len(sample_days), flush=True)
(HERE / "trace.pkl").write_bytes(pickle.dumps({"sites": sites, "q_spill": T.Q_SPILL_M3S}))
print("TRACE DONE", len(sites))
