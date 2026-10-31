"""The weekly satellite-observation pilot (#472, docs/SATELLITE-PILOT-2026-11.md): five monitored lake sites refreshed
from Sentinel-2 by the satellite test's own code and saved masks, and published into the lake observation file the
site's /lakes.html reads.

    satellite_pilot.py run <root> [--days 14] [--max-requests 300] [--max-mb 100] [--max-minutes 20]
    satellite_pilot.py publish [--as-of YYYY-MM-DD]

`run` reads, for each pilot site, every Sentinel-2 Collection 1 L2A scene of the last `days` days: the scene
classification around the site, and for a scene with at least 80% of its core pixels clear, bands B4 and B5 and the
median NDCI. Every request goes through the test's capped client (public hosts only, no account, no retries, stop on any
error status). A cap or the time limit stops the run where it is; what was read is kept and the stop is recorded. The
run, its costs, each site's status and every scene's diagnostics are appended to data/research/satellite/pilot_runs.json.

`publish` applies every recorded run to data/research/lake_observations.v1.json (export_lake_observations.apply_refresh:
the quality rules of contract 1.1, idempotent), sets each pilot site's `operation` (last run, its status, last success,
newest reading) and the file's `pilot` block, recomputes every site's age for today, and checks the contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lake_algae_sat_eval"))
import export_lake_observations as ex  # noqa: E402

PILOT = ROOT / "data" / "research" / "satellite" / "pilot.json"
CORES = ROOT / "data" / "research" / "satellite" / "cores"
# The committed files; a local trial points these at scratch copies (DIPCAST_PILOT_RUNS, DIPCAST_PILOT_OBS).
RUNS = Path(os.environ.get("DIPCAST_PILOT_RUNS", ROOT / "data" / "research" / "satellite" / "pilot_runs.json"))
OBS = Path(os.environ.get("DIPCAST_PILOT_OBS", ex.OUT))
SCHEDULE = "weekly, Mondays about 06:17 UTC, plus manual recovery runs (.github/workflows/satellite-pilot.yml)"
SITE_STATUS = ex.PILOT_STATUS


class Deadline(RuntimeError):
    """The run's time limit: stop where it is."""


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pilot_sites() -> list[dict]:
    return json.loads(PILOT.read_text())["sites"]


def site_cores(lake_id: str) -> dict[str, np.ndarray]:
    z = np.load(CORES / f"{lake_id}.npz")
    return {k.replace("_", "-"): z[k] for k in z.files}


def read_scene(net, it: dict, site: dict, core: dict[str, np.ndarray]) -> dict:
    """One scene at one site, exactly as refresh_lake_observations.run reads it, with its quality diagnostics."""
    import protocol as pr
    import stac
    from refresh_lake_observations import scene_quality, sun_elevation
    t = it["properties"]["grid:code"]
    w, _ = stac.site_scl(net, it, site["lon"], site["lat"])
    clear, usable = pr.scene_clear(w, core[t])
    value, index = float("nan"), None
    if usable:
        b4_dn, b5_dn = stac.site_bands(net, it, site["lon"], site["lat"])
        b4 = pr.b4_to_20m(pr.reflectance(b4_dn, it["assets"]["red"]["raster:bands"][0]))
        b5 = pr.reflectance(b5_dn, it["assets"]["rededge1"]["raster:bands"][0])
        index = pr.ndci(b4, b5)
        _, _, value = pr.scene_reading(w, core[t], index)
    p = it["properties"]
    return {"lake_id": site["lake_id"], "tile": t, "item_id": it["id"], "scene_date": p["datetime"][:10],
            "datetime": p["datetime"], "processing_baseline": p.get("s2:processing_baseline"),
            "sun_elevation_deg": round(sun_elevation(p["datetime"], site["lat"], site["lon"]), 1),
            "clear_core": int(clear), "n_core": int(core[t].sum()), "usable": bool(usable),
            "reading": None if np.isnan(value) else float(value), **scene_quality(w, core[t], index)}


def run(root: Path, days: int, max_requests: int, max_mb: int, max_minutes: float, today: date | None = None) -> dict:
    import net as netmod
    import protocol as pr
    import stac
    from stage1 import ITEM_FIELDS, check_items
    root.mkdir(parents=True, exist_ok=True)
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=days - 1)
    net = netmod.Capped(ledger=root / "ledger.jsonl", max_requests=max_requests, max_bytes=max_mb * 1024**2,
                        max_requests_total=max_requests, max_bytes_total=max_mb * 1024**2)
    t0 = time.monotonic()
    deadline = t0 + max_minutes * 60
    rec = {"run_id": os.environ.get("GITHUB_RUN_ID") or f"local-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
           "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
           "started": datetime.now(UTC).isoformat(timespec="seconds"),
           "window": {"from": start.isoformat(), "to": end.isoformat()},
           "caps": {"requests": max_requests, "megabytes": max_mb, "minutes": max_minutes},
           "sites": {}, "stop_reason": None}
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else []
    # A scene an earlier run read is not read again: the 14-day windows overlap, the requests would not.
    seen = {(r["lake_id"], r["item_id"]) for prev in runs for r in prev["rows"]}
    rows = []
    for site in pilot_sites():
        st = {"scenes": 0, "already_read": 0, "read": 0, "status": None, "error": None}
        rec["sites"][site["lake_id"]] = st
        if rec["stop_reason"]:
            st["status"] = "not_reached"
            continue
        try:
            if time.monotonic() > deadline:
                raise Deadline("time limit")
            core = site_cores(site["lake_id"])
            items = stac.search(net, site["lon"], site["lat"], start.isoformat(), end.isoformat(), fields=ITEM_FIELDS)
            items = sorted({i["id"]: i for i in items}.values(), key=lambda i: (i["properties"]["datetime"], i["id"]))
            check_items(items)
            items = [i for i in items if i["properties"]["grid:code"] in core
                     and pr.passes_size_rule(core[i["properties"]["grid:code"]])]
            st["scenes"] = len(items)
            items = [i for i in items if (site["lake_id"], i["id"]) not in seen]
            st["already_read"] = st["scenes"] - len(items)
            for it in items:
                if time.monotonic() > deadline:
                    raise Deadline("time limit")
                rows.append(read_scene(net, it, site, core))
                st["read"] += 1
            st["status"] = "ok"
        except netmod.CapReached as e:
            rec["stop_reason"] = f"cap reached: {e}"
            st["status"] = "partial"
        except Deadline as e:
            rec["stop_reason"] = str(e)
            st["status"] = "partial"
        except netmod.Stop as e:   # 429, 5xx or another unexpected status: stop the run, retry nothing
            rec["stop_reason"] = f"stopped: {e}"
            st["status"], st["error"] = "failed", str(e)[:200]
        except Exception as e:  # noqa: BLE001 - one site's error is recorded; the others still run
            st["status"], st["error"] = "failed", f"{type(e).__name__}: {e}"[:200]
    statuses = [s["status"] for s in rec["sites"].values()]
    rec.update({"finished": datetime.now(UTC).isoformat(timespec="seconds"),
                "seconds": round(time.monotonic() - t0, 1), "requests": net.requests,
                "megabytes": round(net.bytes / 1024**2, 2),
                "status": "ok" if all(s == "ok" for s in statuses) else
                          "failed" if all(s == "failed" for s in statuses) else "partial",
                "rows": rows})
    (root / "run.json").write_text(json.dumps({k: v for k, v in rec.items() if k != "rows"}, indent=1))
    runs.append(rec)
    RUNS.write_text(json.dumps(runs, separators=(",", ":")) + "\n")
    return rec


def record_crash(days: int, error: str) -> None:
    """A run that stopped before it could record itself still shows on the page, as failed at every site."""
    now = datetime.now(UTC)
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else []
    runs.append({"run_id": os.environ.get("GITHUB_RUN_ID") or f"local-{now.strftime('%Y%m%dT%H%M%SZ')}",
                 "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"), "started": now.isoformat(timespec="seconds"),
                 "finished": now.isoformat(timespec="seconds"),
                 "window": {"from": (now.date() - timedelta(days=days - 1)).isoformat(), "to": now.date().isoformat()},
                 "caps": None, "seconds": 0, "requests": None, "megabytes": None, "status": "failed",
                 "stop_reason": error, "rows": [],
                 "sites": {s["lake_id"]: {"scenes": 0, "already_read": 0, "read": 0, "status": "failed", "error": error}
                           for s in pilot_sites()}})
    RUNS.write_text(json.dumps(runs, separators=(",", ":")) + "\n")


def site_status(st: dict, rows: pd.DataFrame) -> str:
    """From the run's own record, so publishing again gives the same answer. Its rows are scenes no earlier run read."""
    if st["status"] in ("partial", "failed", "not_reached"):
        return st["status"]
    if not st["scenes"]:
        return "no_scenes"
    if not st["read"]:
        return "no_new_scenes"
    if any(ex.refresh_decision(r) is None for r in rows.itertuples()):
        return "new_reading"
    return "no_new_clear_image"


def publish(as_of: date | None = None) -> dict:
    as_of = as_of or datetime.now(UTC).date()
    doc = json.loads(OBS.read_text())
    runs = json.loads(RUNS.read_text()) if RUNS.exists() else []
    lakes = {lk["lake_id"]: lk for lk in doc["lakes"]}
    ids = [s["lake_id"] for s in pilot_sites()]
    op = {i: {"pilot": True, "schedule": SCHEDULE, "runs": 0} for i in ids}
    summaries = []
    for r in runs:
        source = f"refresh:pilot-{r['run_id']}"
        df = pd.DataFrame(r["rows"])
        info = {"source": source, "set": "pilot", "from": r["window"]["from"], "to": r["window"]["to"],
                "requests": r["requests"], "bytes": int((r["megabytes"] or 0) * 1024**2),
                "rows_sha256": sha256(json.dumps(r["rows"], sort_keys=True).encode())}
        site_states = {}
        for lid, st in r["sites"].items():
            lk = lakes.get(lid)
            if lk is None:
                continue
            rf = df[df["lake_id"] == lid] if len(df) else df
            if st["status"] == "ok":
                ex.apply_refresh(lk, rf, info, as_of)
            elif st["status"] == "partial" and len(rf):
                # Only as far as the scenes actually read: an unread scene must not look processed.
                ex.apply_refresh(lk, rf, {**info, "to": str(rf["scene_date"].max()), "partial": True}, as_of)
            status = site_status(st, rf)
            site_states[lid] = status
            o = op.setdefault(lid, {"pilot": True, "schedule": SCHEDULE, "runs": 0})
            o.update({"runs": o["runs"] + 1, "last_run_id": r["run_id"], "last_run_at": r["finished"],
                      "last_window": r["window"], "last_status": status, "last_error": st.get("error")})
            if status in ("new_reading", "no_new_clear_image", "no_new_scenes", "no_scenes"):
                o["last_success_at"] = r["finished"]
        summaries.append({k: r[k] for k in ("run_id", "trigger", "started", "finished", "seconds", "requests",
                                            "megabytes", "status", "stop_reason", "window", "caps")} | {"sites": site_states})
    for lid, o in op.items():
        lk = lakes.get(lid)
        if lk is None:
            continue
        # The newest clear image the pilot found, whichever release first published it (the one-off October refresh
        # already holds some of the same scenes).
        found = {r["item_id"] for run in runs for r in run["rows"] if r["lake_id"] == lid
                 and ex.refresh_decision(pd.Series(r)) is None}
        newest = max((x["date"] for x in lk["series"] if x["item_id"] in found), default=None)
        lk["operation"] = {**o, "last_success_at": o.get("last_success_at"), "newest_pilot_reading": newest}
    for lk in doc["lakes"]:   # every site's age for today, not frozen at the last export
        lk["latest"] = ex.latest_block(lk["series"], lk["mask"]["passes_size_rule"], lk["series_scope"], as_of,
                                       lk["processed_to"])
    doc["as_of"] = as_of.isoformat()
    doc["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    doc["version"] = ex.VERSION
    doc["pilot"] = {"sites": ids, "schedule": SCHEDULE,
                    "note": "Five monitored sites refreshed weekly as a pilot. Only these show current operation; every "
                            "other site is the historical record.",
                    "runs": summaries, "code_sha256": sha256((HERE / "satellite_pilot.py").read_bytes())}
    rel = doc["release"]
    rel["refreshed_sites"] = sorted(lk["lake_id"] for lk in doc["lakes"] if lk["refreshes"])
    rel["pilot_sites"] = ids
    rel["label"] = ex.release_label(rel["historical_to"], rel["refreshed_sites"], ids)
    doc["coverage"] = ex.coverage(doc["lakes"])
    problems = ex.check(doc)
    if problems:
        raise SystemExit("the published file would break the contract:\n" + "\n".join(problems[:20]))
    OBS.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"runs": len(runs), "pilot": summaries[-1] if summaries else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["run", "publish"])
    ap.add_argument("root", type=Path, nargs="?")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--max-requests", type=int, default=300)
    ap.add_argument("--max-mb", type=int, default=100)
    ap.add_argument("--max-minutes", type=float, default=20)
    ap.add_argument("--as-of", type=date.fromisoformat)
    a = ap.parse_args()
    if a.step == "run":
        if a.root is None:
            raise SystemExit("run needs a root")
        try:
            rec = run(a.root, a.days, a.max_requests, a.max_mb, a.max_minutes)
        except Exception as e:
            record_crash(a.days, f"{type(e).__name__}: {e}"[:200])
            raise
        print(json.dumps({k: v for k, v in rec.items() if k != "rows"}, indent=1))
    else:
        print(json.dumps(publish(a.as_of), indent=1))


if __name__ == "__main__":
    main()
