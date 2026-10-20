"""Periodic jobs: refresh live status, rebuild the overflow table, score past forecasts."""

from __future__ import annotations

import logging
import time

from dipcast import config

log = logging.getLogger(__name__)


def refresh_all(net=None) -> dict:
    """Poll every live feed, rebuild the overflow table, re-score logged forecasts."""
    from dipcast.ingest.live import expected_rows, fetch_live, save_live
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import build_overflows

    t0 = time.time()
    expected = expected_rows()   # each feed's usual size, from the poll log: a short read is read again
    live = fetch_live(expected=expected)
    save_live(live, expected)
    if config.SCOTTISH_WATER:   # shadow poll, off by default: stores in state, shows and publishes nothing
        from dipcast.ingest.scottish_water import poll
        poll()   # logs its own summary and never raises
    net = net or RiverNetwork.load()
    ov = build_overflows(net)
    if config.DWR_CYMRU:   # off by default: no licence yet; stores in state, shows and publishes nothing
        from dipcast.ingest.dwr_cymru import poll
        poll()   # logs its own summary and never raises
    summary = {"live_rows": len(live), "discharging_now": int((live.status == 1).sum()),
               "overflows": len(ov), "seconds": round(time.time() - t0, 1)}
    try:
        from dipcast.forecast_log import verify_live
        v = verify_live()
        summary["verified_rows"] = int(v.get("n_scored", 0)) if v else 0
    except Exception as e:  # noqa: BLE001 - scoring must never block the refresh
        log.warning("live verification failed: %s", e)
    log.info("refresh done: %s", summary)
    return summary
