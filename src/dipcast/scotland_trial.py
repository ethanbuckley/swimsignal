"""The Scotland trial: Scottish Water's overflows in the published forecasts, labelled as a trial.

Off unless DIPCAST_SCOTLAND_TRIAL=1 and DIPCAST_SCOTTISH_WATER=1 (config.SCOTLAND_TRIAL, config.SCOTTISH_WATER),
and the calibration map was fitted for the spill model in use. The evidence, and why it is a trial:

- Gate A (docs/SCOTLAND-HINDCAST-2026-11.md) passed on Scottish Water's 2022-25 records: the English spill
  model, with each overflow's own count from the year before (data/processed/sw_covariates.parquet), beat each
  overflow's earlier years at leads 0 to 3. It forecast about 70% of the spill-days that happened.
- The calibration map (scripts/scotland_recalibration.py, data/processed/scotland_calibration.json), fitted on
  2022-24 and checked on 2025, brings that to 0.98-1.03 at leads 0 to 3. The check year had been seen in
  aggregate, so the map is exploratory.
- Gate B, the live scores (scottish_shadow.py), has not passed: too few days so far. No outside review yet.
- The live feed names no licence ("an open license for reuse"); switching the trial on is the owner's call.

What it changes when on:

1. The overflow table (overflows.build_overflows) gains the Scottish overflows the shadow forecasts
   (scottish_shadow.overflow_table: snapped with Scotland's marine rule, emergency overflows left out), in
   England's columns, with each asset's live status and data state from ingest.scottish_water's snapshot.
2. Their spill chances take Scotland's map instead of England's lead calibration (calibrate), at every lead.
3. The spots in spots-scotland.csv are listed (build_site.load_spots), each marked `trial: "scotland"`.
4. Click-anywhere stays England only: build_site.write_any_point leaves these rows out (england_only).
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

import numpy as np
import pandas as pd

from dipcast import config

log = logging.getLogger(__name__)

COMPANY = "Scottish Water"
TRIAL = "scotland"
MAP_FILE = "scotland_calibration.json"
SPOTS_FILE = "spots-scotland.csv"


@lru_cache(maxsize=1)
def calibration_map() -> dict | None:
    """Scotland's Platt map, if present and fitted for the spill model in use; else None, with a warning."""
    p = config.PROCESSED / MAP_FILE
    if not p.exists():
        return None
    m = json.loads(p.read_text())
    from dipcast.model.forecast import MODEL_PATH
    stamp = hashlib.md5(MODEL_PATH.read_bytes()).hexdigest()[:8] if MODEL_PATH.exists() else None
    if m.get("spill_stamp") != stamp:
        log.warning("Scotland trial off: the calibration map was fitted for spill model %s, this one is %s",
                    m.get("spill_stamp"), stamp)
        return None
    return m


def enabled() -> bool:
    return config.SCOTLAND_TRIAL and config.SCOTTISH_WATER and calibration_map() is not None


def apply_map(p: np.ndarray) -> np.ndarray:
    """Scotland's map on raw spill chances; NaN stays NaN."""
    m = calibration_map()
    q = np.clip(p, 1e-6, 1 - 1e-6)
    out = 1 / (1 + np.exp(-(m["a"] + m["b"] * np.log(q / (1 - q)))))
    return np.where(np.isnan(p), np.nan, out)


def is_scottish(ov: pd.DataFrame) -> np.ndarray:
    return (ov["company"].eq(COMPANY).to_numpy(dtype=bool) if "company" in ov and len(ov)
            else np.zeros(len(ov), dtype=bool))


def calibrate(p_cal: np.ndarray, p_raw: np.ndarray, ov: pd.DataFrame) -> np.ndarray:
    """England's calibrated chances `p_cal`, with Scotland's map on the raw chances of Scottish rows."""
    rows = is_scottish(ov)
    if not rows.any() or calibration_map() is None:
        return p_cal
    out = p_cal.copy()
    out[rows] = apply_map(p_raw[rows])
    return out


def england_only(ov: pd.DataFrame | None) -> pd.DataFrame | None:
    """The table less Scottish Water's rows; anything without them (no table, no company column) as it is."""
    if ov is None or not len(ov) or "company" not in ov or not is_scottish(ov).any():
        return ov
    return ov[~is_scottish(ov)].reset_index(drop=True)


def overflow_rows(net) -> pd.DataFrame:
    """The Scottish overflows the shadow forecasts, in the overflow table's columns (module docstring, 1).
    Empty when the snapshot is missing."""
    from dipcast import scottish_shadow
    from dipcast.ingest import scottish_water as sw
    from dipcast.model.features import fill_covariates
    from dipcast.overflows import on_named
    path = config.state_read(sw.LATEST_FILE)
    if not path.exists():
        log.warning("Scotland trial: no Scottish Water snapshot (%s), so no Scottish overflows", path.name)
        return pd.DataFrame()
    snap = pd.read_parquet(path).drop_duplicates("site_id")
    table, arm = scottish_shadow.overflow_table(net, snap)
    t = table[table["forecast"]].drop(columns=["status", "data_state", "forecast", "abstain", "marine"])
    live = snap.set_index("site_id")
    for c in ("status", "data_state", "latest_event_start", "latest_event_end", "fetched_at", "feed_updated_at"):
        t[c] = t["site_id"].map(live[c]).to_numpy() if c in live else np.nan
    t["last_updated"] = t["site_id"].map(live["transmitted_at"]).to_numpy() if "transmitted_at" in live else pd.NaT
    t["status"] = pd.to_numeric(t["status"], errors="coerce").fillna(-1).astype(int)
    t["last_status"] = t["status"].astype(float)
    t["has_live"] = True
    t["record_stale"] = False
    t["feed_on_change"] = False
    t["trial"] = TRIAL
    t["position_source"] = "scottish_water_api"
    links = net.links.loc[t["link_id"]]
    t["start_node"] = links["start_node"].to_numpy()
    t["end_node"] = links["end_node"].to_numpy()
    t["link_length"] = links["length"].to_numpy()
    t = fill_covariates(t.reset_index(drop=True))
    t["on_named"] = on_named(net, t)
    log.info("Scotland trial: %d Scottish overflows (covariates %s); data states %s",
             len(t), arm, t["data_state"].value_counts().to_dict())
    return t
