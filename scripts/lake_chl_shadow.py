"""The research shadow log for satellite chlorophyll candidates (docs/SATELLITE-CHL-CANDIDATES-2026-11.md, amendment
1): beside each new usable reading, the value each frozen model in data/research/satellite/chl_shadow_model.v1.json
gives, the baseline's, and the fallback, so pairs made after contract 1.4 can test the candidates prospectively.

Inputs are the reading's own measurements at reading time (the core reading, contract 1.4's brightness, pixel IQR and
low-signal mark), so no request is added. Values are log10 of the EA's acetone-extract chlorophyll result (determinand
7887) as a frozen fit on seen 2021-2026 pairs would estimate it: research records only. They go into their own
versioned file, which no page reads and the site build does not copy, never into the published lake observation file
or the pilot's run record (which the Research Lab publishes). They are not measurements. With no model file nothing is
written.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "data" / "research" / "satellite" / "chl_shadow_model.v1.json"
# A local trial points this elsewhere (as satellite_pilot.py's DIPCAST_PILOT_RUNS does for the run record).
LOG = Path(os.environ.get("DIPCAST_CHL_SHADOW_LOG", HERE.parent / "data" / "research" / "satellite" / "chl_shadow_log.v1.json"))
UNIT = "log10 of the EA Water Quality Archive result for determinand 7887 (chlorophyll, acetone extract)"
SCHEMA, VERSION = "swimsignal.lake-chl-shadow-log", "1.0.0"
sys.path.insert(0, str(HERE))


def load(path: Path = MODEL) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _r(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 4)


def _num(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def values(model: dict, reading: float | None, brightness: float | None, iqr: float | None,
           low_signal: bool | None) -> dict:
    """Each frozen model's value for one reading, and the fallback. A model with no value for a reading (A on a
    low-signal reading, C without measured signal) is None: the fallback stands in for it when it is read."""
    m = model["models"]
    have = reading is not None and np.isfinite(reading)
    signal = brightness is not None and iqr is not None
    out = {"fallback": _r(model["reference"])}
    if "B0" in m:
        out["B0"] = _r(m["B0"]["a"] + m["B0"]["b"] * reading) if have else None
    if "A" in m:
        out["A"] = _r(m["A"]["a"] + m["A"]["b"] * reading) if have and low_signal is False else None
    if "B" in m:
        b = m["B"]
        if have and signal:
            q = np.log(max(iqr, 0) + model["iqr_floor"]) - np.log(max(brightness, model["bright_floor"]))
            v = np.exp(b["c"] + b["g"] * q)
            f = b["a"] + b["b"] * reading
            out["B"] = _r((f / v + b["reference"] / b["reference_variance"]) / (1 / v + 1 / b["reference_variance"]))
        else:
            out["B"] = None
    if "C" in m:
        if have and signal:
            lb = np.log10(max(brightness, model["bright_floor"]))
            out["C"] = _r(float(np.dot(m["C"]["beta"], [1.0, reading, lb, iqr, reading * lb])))
        else:
            out["C"] = None
    return out


def rows_for(scene_rows: list[dict], model: dict, read_at: str, source: str, site_key: str) -> list[dict]:
    """Shadow rows for the usable readings among a run's scene rows (the pilot's or the refresher's)."""
    from export_lake_observations import low_signal
    out = []
    for r in scene_rows:
        reading = _num(r.get("reading"))
        if not r.get("usable") or reading is None:
            continue
        bright, iqr = _num(r.get("core_brightness")), _num(r.get("index_iqr"))
        mark = low_signal(bright, iqr)
        out.append({"source": source, "site": r[site_key], "item_id": r["item_id"], "tile": r.get("tile"),
                    "acquired": r.get("datetime"), "read_at": read_at, "model_version": model["version"],
                    "inputs": {"reading": round(reading, 6), "core_brightness": bright, "index_iqr": iqr,
                               "low_signal": mark},
                    "values": values(model, reading, bright, iqr, mark)})
    return out


def model_sha(path: Path = MODEL) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def empty(model: dict | None = None) -> dict:
    return {"schema": SCHEMA, "version": VERSION,
            "description": "Research shadow log: frozen candidate values beside each new satellite reading, for a "
                           "prospective comparison with lab chlorophyll. Not measurements; not shown on the site.",
            "protocol": "docs/SATELLITE-CHL-CANDIDATES-2026-11.md", "values_unit": UNIT,
            "model": None if model is None else {"version": model["version"], "sha256": model_sha()},
            "rows": []}


def append(rows: list[dict], path: Path = LOG, model: dict | None = None) -> int:
    """Add rows not already logged (a site and scene once per source); returns how many were added. The file is
    replaced whole (written beside it, then renamed), and only when there is something to add or it does not exist."""
    doc = json.loads(path.read_text()) if path.exists() else empty(model)
    if model is not None and doc.get("model") is None:
        doc["model"] = {"version": model["version"], "sha256": model_sha()}
    seen = {(r["source"], r["site"], r["item_id"]) for r in doc["rows"]}
    new = [r for r in rows if (r["source"], r["site"], r["item_id"]) not in seen]
    if not new and path.exists():
        return 0
    doc["rows"] += new
    doc["updated"] = datetime.now(UTC).isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n")
    tmp.replace(path)
    return len(new)


def log_run(scene_rows: list[dict], source: str, site_key: str, read_at: str, path: Path = LOG) -> int | None:
    """What the pilot and the refresher call after a run: None with no model; otherwise the rows added. A failure here
    is reported by the caller and never changes the reading or the run's own record."""
    model = load()
    if model is None:
        return None
    return append(rows_for(scene_rows, model, read_at, source, site_key), path, model)
