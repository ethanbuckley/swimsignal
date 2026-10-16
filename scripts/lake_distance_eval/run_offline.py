"""scripts/lake_residence_eval/run_offline.py (from #199, #197 and #172): run a script with every outgoing network
connection refused, so a run cannot fetch anything. For docs/LAKE-DISTANCE-2026-10.md one thing is added: with
LAKE_DISTANCE_PLACEBO=<csv> (make_placebos.py), transport.spot_lake_m gives each lake row the straight line times the
ratio the placebo file assigns to its pin and overflow, in place of the through-water distance. A row the file does
not hold keeps the through-water distance and is counted ("placebo misses"); the statement requires 0."""
import os
import runpy
import socket
import sys

calls = []
misses = []


def _refuse(self, addr, *a, **k):
    calls.append(addr)
    raise OSError(f"network blocked: {addr}")


def _placebo(path: str) -> None:
    import numpy as np
    import pandas as pd

    from dipcast.model import transport

    t = pd.read_csv(path)
    ratio = {(round(x, 1), round(y, 1), s): r for x, y, s, r in zip(t.pin_x, t.pin_y, t.site_id, t.ratio, strict=True)}
    real = transport.spot_lake_m

    def spot_lake_m(net, pin, site_ids, entry_xy, mode):
        water = real(net, pin, site_ids, entry_xy, mode)
        line = real(net, pin, site_ids, entry_xy, "line")
        r = np.array([ratio.get((round(pin.x, 1), round(pin.y, 1), s), np.nan) for s in site_ids], dtype=float)
        misses.extend(np.flatnonzero(np.isnan(r)).tolist())
        return np.where(np.isnan(r), water, line * r)

    transport.spot_lake_m = spot_lake_m


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
script = sys.argv[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
sys.argv = sys.argv[1:]
if os.environ.get("LAKE_DISTANCE_PLACEBO"):
    _placebo(os.environ["LAKE_DISTANCE_PLACEBO"])
try:
    runpy.run_path(script, run_name="__main__")
finally:
    print("network attempts:", len(calls), file=sys.stderr)
    if os.environ.get("LAKE_DISTANCE_PLACEBO"):
        print("placebo misses:", len(misses), file=sys.stderr)
