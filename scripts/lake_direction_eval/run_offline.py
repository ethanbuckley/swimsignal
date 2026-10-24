"""scripts/lake_distance_eval/run_offline.py (from #199, #197 and #172): run a script with every outgoing network
connection refused, so a run cannot fetch anything. For docs/LAKE-DIRECTION-TEST-2026-10.md: with
LAKE_DIRECTION_PLACEBO=<csv> (make_placebos.py), transport.down_lake_m gives each lake row the flag the placebo file
assigns to its pin and entry point (left out, or not), in place of the rule's own. A row the file does not hold keeps
the rule's own value and is counted ("placebo misses"); the statement requires 0."""
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
    flag = {(round(px), round(py), round(ex), round(ey)): bool(d)
            for px, py, ex, ey, d in zip(t.pin_x, t.pin_y, t.entry_x, t.entry_y, t.dropped, strict=True)}
    real = transport.down_lake_m
    out_m = transport.LAKE_DOWN_MARGIN_M + 1.0

    def down_lake_m(net, pin, entry_xy):
        own = real(net, pin, entry_xy)
        f = [flag.get((round(pin.x), round(pin.y), round(ex), round(ey))) for ex, ey in entry_xy]
        misses.extend(i for i, v in enumerate(f) if v is None)
        return np.array([o if v is None else (out_m if v else 0.0) for o, v in zip(own, f, strict=True)])

    transport.down_lake_m = down_lake_m


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
script = sys.argv[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
sys.argv = sys.argv[1:]
if os.environ.get("LAKE_DIRECTION_PLACEBO"):
    _placebo(os.environ["LAKE_DIRECTION_PLACEBO"])
try:
    runpy.run_path(script, run_name="__main__")
finally:
    print("network attempts:", len(calls), file=sys.stderr)
    if os.environ.get("LAKE_DIRECTION_PLACEBO"):
        print("placebo misses:", len(misses), file=sys.stderr)
