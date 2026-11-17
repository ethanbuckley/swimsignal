"""Level history at the river bathing waters' own gauges, for docs/LEVEL-RISE-CHECK-2026-11.md. Off CI, by hand:

    python scripts/level_rise_check/fetch.py docs/level-rise-check/gauges.csv <out dir>

One CSV request a gauge to the Environment Agency's Hydrology API: its 15-minute level series from 28 April 2023 to
1 October 2026. At most 25 requests, 2 s apart; a refusal (401, 403, 429) or a server error stops the run. A series
already on disk is not asked for again. <out dir>/ledger.jsonl has one line a request. Suspect, rejected and missing
readings are dropped. Data: Environment Agency, Open Government Licence v3.0."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
START, END, LIMIT, CAP, PACE_S = "2023-04-28", "2026-10-01", 200_000, 25, 2.0
BAD = ("Suspect", "Rejected", "Missing")


def clean(text: str) -> pd.DataFrame:
    """The readings as time (UTC) and value, without the ones the EA marks suspect, rejected or missing."""
    d = pd.read_csv(io.StringIO(text), dtype=str) if text.strip() else pd.DataFrame(columns=["dateTime", "value"])
    if "quality" in d:
        d = d[~d["quality"].isin(BAD)]
    out = pd.DataFrame({"time": pd.to_datetime(d["dateTime"], utc=True, errors="coerce"),
                        "value": pd.to_numeric(d["value"], errors="coerce")}).dropna()
    return out.sort_values("time").drop_duplicates("time").reset_index(drop=True)


def main(gauges: Path, out: Path) -> None:
    sys.path.insert(0, str(REPO / "src"))
    from dipcast import config   # the Hydrology address, and the User-Agent that names the project to the EA

    (out / "series").mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(gauges).dropna(subset=["measure"])
    sent = 0
    with httpx.Client(timeout=180, headers=config.EA_HEADERS) as client:
        for r in g.itertuples():
            f = out / "series" / f"{r.gauge}.parquet"
            if f.exists():
                continue
            if sent >= CAP:
                raise SystemExit(f"cap of {CAP} requests reached")
            if sent:
                time.sleep(PACE_S)
            url = f"{config.EA_HYDROLOGY}/id/measures/{r.measure}/readings.csv"
            params = {"mineq-date": START, "max-date": END, "_limit": LIMIT}
            t0, sent = time.monotonic(), sent + 1
            resp = client.get(url, params=params)
            d = clean(resp.text) if resp.status_code == 200 else pd.DataFrame()
            row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "n": sent, "gauge": r.gauge, "url": url,
                   "params": params, "status": resp.status_code, "bytes": len(resp.content), "rows": int(len(d)),
                   "sha256": hashlib.sha256(resp.content).hexdigest(), "seconds": round(time.monotonic() - t0, 2)}
            with (out / "ledger.jsonl").open("a") as h:
                h.write(json.dumps(row, sort_keys=True) + "\n")
            if resp.status_code != 200:
                raise SystemExit(f"{r.gauge}: HTTP {resp.status_code}; stopped")
            if len(d) >= LIMIT:
                raise SystemExit(f"{r.gauge}: {len(d)} rows, at the limit asked; the series may be cut")
            d.to_parquet(f, index=False)
            print(f"{r.gauge}: {len(d)} readings, {row['seconds']} s", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
