"""The C3 data, for docs/RIVER-RISES-C3-2026-11.md. Builds on fetch.py's output; never changes it.

    uv run python scripts/river_rises_eval/fetch_c3.py --cache <cache dir> --base <fetch.py out dir> --out <new dir> [--fetch]

Research only: nothing here feeds the site. Two kinds of request, one CSV request per series (Hydrology API):
- **the 12 spot gauges left out of #627** that have a Hydrology 15-minute level series (no upstream gauge, or none
  with a series and a range): their whole series, FETCH_FROM to FRESH_TO;
- **every series fetch.py saved** (the 33 spot gauges and their upstream gauges): from EXTEND_FROM to FRESH_TO only.
  A combined series keeps fetch.py's values to 24 October 2026 23:45 unchanged and takes the new answer after it.

The caps are fetch.py's (river_rises_coverage.CappedClient): at most 300 requests a run, one at a time, 1.5 s apart,
EA https hosts only, no Open-Meteo, stop at the first 403, 429, 5xx, redirect or connection error, no retry, every
answer cached and every request logged in <cache>/requests.log. Without --fetch only cached answers are read.

The fresh week's labels are in these series. Nothing here reads a label; c3.py reads them only after the frozen models
are committed (its `fresh` stage).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import river_rises_coverage as rr  # noqa: E402
from river_rises_eval import protocol as pr  # noqa: E402

HY = rr.HY
READINGS_LIMIT = 200_000
EXTEND_FROM = pd.Timestamp("2026-10-24", tz="UTC")   # one day of overlap with fetch.py's series, for the look-back
FRESH_TO = pd.Timestamp("2026-11-02", tz="UTC")      # exclusive: the fresh week's last label window ends 1 Nov 00:00
SEEN_END = pr.TEST[1]                                 # fetch.py's series end before this (25 Oct 2026 00:00)


def ask(client: rr.CappedClient, measure: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    status, text = client.get(f"{HY}/id/measures/{measure}/readings.csv",
                              {"mineq-date": start.strftime("%Y-%m-%d"), "max-date": end.strftime("%Y-%m-%d"),
                               "_limit": READINGS_LIMIT})
    df = rr.read_csv_readings(text) if status == 200 else rr.read_csv_readings("")
    if len(df) >= READINGS_LIMIT:
        raise rr.Stop(f"{measure}: {len(df)} rows, at the limit asked; the series may be cut")
    return rr.to_grid(df, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))


def combine(old: pd.Series, new: pd.Series) -> pd.Series:
    """fetch.py's values before SEEN_END, unchanged; the new answer from SEEN_END on, on one 15-minute grid."""
    grid = pd.date_range(pr.FETCH_FROM, FRESH_TO, freq=rr.SLOT, inclusive="left")
    out = pd.Series(float("nan"), index=grid)
    o = old[old.index < SEEN_END]
    out.loc[o.index] = o.to_numpy()
    n = new[new.index >= SEEN_END]
    out.loc[n.index] = n.to_numpy()
    return out


def read_series(path: Path) -> pd.Series:
    d = pd.read_parquet(path)
    return pd.Series(d["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(d["time"]))


def write_series(path: Path, s: pd.Series) -> None:
    s.rename("value").rename_axis("time").reset_index().to_parquet(path, index=False)


def extra_gauges(gauges: pd.DataFrame) -> pd.DataFrame:
    """The spot gauges #627 left out that have a Hydrology series and an EA usual range."""
    g = gauges[(gauges["why"].fillna("") != "") & gauges["measure"].notna()]
    return g[(g["high"] > g["low"])]


def radar_cells(rows: pd.DataFrame, radar: Path | None) -> pd.DataFrame:
    from dipcast.ingest.rainfall import cell_key, grid_cell
    out = []
    for r in rows.itertuples(index=False):
        c = grid_cell(float(r.lat), float(r.lon))
        k = cell_key(float(c[0]), float(c[1]))
        out.append({"gauge": r.gauge, "cell": k, "cell_lat": float(c[0]), "cell_lon": float(c[1]),
                    "saved_months": len(list(radar.glob(f"radar_{k}_*.parquet"))) if radar else 0})
    return pd.DataFrame(out)


def run(args) -> dict:
    base, out = args.base, args.out
    (out / "series").mkdir(parents=True, exist_ok=True)
    gauges = pd.read_csv(base / "gauges.csv", dtype={"gauge": str, "system": str, "why": str, "measure": str})
    slots = pd.read_csv(base / "slots.csv", dtype={"gauge": str, "up": str, "measure": str})
    extra = extra_gauges(gauges)
    used = gauges[gauges["why"].fillna("") == ""]
    old_measures = sorted(set(used["measure"].dropna()) | set(slots["measure"].dropna()))
    client = rr.CappedClient(args.cache, args.fetch)
    summary = {"stopped": None, "started": datetime.now(UTC).isoformat(timespec="seconds"),
               "extra_gauges": extra["gauge"].tolist(), "old_series": len(old_measures)}
    try:
        for m in sorted(extra["measure"]):
            write_series(out / "series" / f"{m}.parquet", ask(client, m, pr.FETCH_FROM, FRESH_TO))
        for m in old_measures:
            old = read_series(base / "series" / f"{m}.parquet")
            write_series(out / "series" / f"{m}.parquet", combine(old, ask(client, m, EXTEND_FROM, FRESH_TO)))
    except rr.Stop as e:
        summary.update(stopped=str(e), requests_this_run=client.n)
        (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        print(f"stopped: {e}\nrun again to resume from the cache", file=sys.stderr)
        raise SystemExit(2) from None
    for name in ("gauges.csv", "slots.csv", "upstream.csv"):
        shutil.copy(base / name, out / name)
    cells = pd.concat([pd.read_csv(base / "radar_cells.csv", dtype={"gauge": str, "cell": str}),
                       radar_cells(extra, args.radar)], ignore_index=True).drop_duplicates(["gauge", "cell"])
    cells.to_csv(out / "radar_cells.csv", index=False)
    summary.update({"series": len(extra) + len(old_measures), "requests_this_run": client.n,
                    "extra_with_radar": int((cells[cells["gauge"].isin(extra["gauge"])]["saved_months"] > 0).sum()),
                    "finished": datetime.now(UTC).isoformat(timespec="seconds")})
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    return summary


def main(argv: list[str] | None = None) -> None:
    from dipcast import config
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=Path, required=True, help="answers are kept here (outside git)")
    ap.add_argument("--base", type=Path, required=True, help="fetch.py's --out directory (read only)")
    ap.add_argument("--out", type=Path, required=True, help="the C3 data directory (outside git)")
    ap.add_argument("--radar", type=Path, default=config.RAW / "met_office_radar", help="saved radar months, read only")
    ap.add_argument("--fetch", action="store_true", help="ask the EA for what is not cached, within the caps")
    args = ap.parse_args(argv)
    if args.radar and not args.radar.exists():
        args.radar = None
    if args.out.resolve() == args.base.resolve():
        raise SystemExit("--out must not be fetch.py's directory")
    run(args)


if __name__ == "__main__":
    main()
