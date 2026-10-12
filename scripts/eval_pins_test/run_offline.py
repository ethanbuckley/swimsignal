"""From PR #197 (scripts/spill_size_eval/ at 34924c1), itself from PR #172, unchanged but for this line. Run a script with every outgoing network connection refused, so a run cannot fetch anything."""
import os
import runpy
import socket
import sys

calls = []


def _refuse(self, addr, *a, **k):
    calls.append(addr)
    raise OSError(f"network blocked: {addr}")


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
script = sys.argv[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
sys.argv = sys.argv[1:]
try:
    runpy.run_path(script, run_name="__main__")
finally:
    print("network attempts:", len(calls), file=sys.stderr)
