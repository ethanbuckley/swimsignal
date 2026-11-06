"""The river-rises evaluation's data, for docs/RIVER-RISES-SCOPE-2026-10.md ("Running"). Run through run_fetch.sh,
which waits for the group's heavy-run lock:

    bash scripts/river_rises_eval/run_fetch.sh <cache dir> <out dir>
    # or, under the lock yourself:
    uv run python scripts/river_rises_eval/fetch.py --cache <cache dir> --out <out dir> [--fetch]

Not before 2 November 2026 (the plan's date). Research only: nothing here feeds the site.

- **Spot gauges:** as scripts/river_rises_coverage.py: flows.station_pick for each river spot, through the capped
  client; usable when on the spot's river with a usual range; with a Hydrology 15-minute level series.
- **Upstream gauges:** every EA level station upstream of the spot gauge along the network within UP_MAX_KM and at
  least SAME_SITE_KM away (as the coverage run). Two are chosen per spot gauge: `same`, the nearest on the same
  river name at least PAIR_MIN_KM up with at least PAIR_MIN_AREA of the catchment (the pairing rule), and `trib`,
  the one on another river name with the largest catchment. Each must have a Hydrology series and an EA usual range
  (one stage-scale request each, in candidate order until one has both).
- **River system:** the network outlet the spot gauge drains to (protocol.outlet).
- **Radar cells:** the rain cells holding the spot gauge and each of its upstream gauges (read later from the saved
  months in data/raw/met_office_radar; never fetched).
- **Readings:** each chosen gauge's 15-minute level series from protocol.FETCH_FROM to protocol.TEST[1], one CSV
  request each, on a regular grid (Suspect, Rejected and Missing dropped), to <out>/series/<measure>.parquet.

The caps are the coverage run's (river_rises_coverage.CappedClient): at most 300 requests a run, one at a time,
1.5 s apart, EA https hosts only, no Open-Meteo, stop at the first 403, 429, 5xx, redirect or connection error,
every answer cached. A run that stops at the cap is resumed by running it again: cached answers do not count. The
same cache directory as the coverage run makes its station requests free.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import river_rises_coverage as rr  # noqa: E402
from river_rises_eval import protocol as pr  # noqa: E402

from dipcast import config  # noqa: E402
from dipcast.ingest import flows  # noqa: E402

READINGS_LIMIT = 200_000      # rows asked per readings call; two years of 15-minute readings is about 70,000
FM, HY = rr.FM, rr.HY


def stage_range(client: rr.CappedClient, station: dict) -> tuple[float | None, float | None]:
    """An upstream gauge's EA usual range: the stage scale embedded in its station item, or one request for it."""
    scale = station.get("stageScale")
    if isinstance(scale, dict):
        return flows._num(scale.get("typicalRangeLow")), flows._num(scale.get("typicalRangeHigh"))
    ref = station.get("stationReference")
    url = flows._ea_link(scale) if isinstance(scale, str) else f"{FM}/id/stations/{ref}/stageScale"
    if url is None:
        return None, None
    js = client.get_json(url, {"_view": "full"})
    items = (js or {}).get("items", {})
    items = items[0] if isinstance(items, list) and items else items
    if not isinstance(items, dict):
        return None, None
    return flows._num(items.get("typicalRangeLow")), flows._num(items.get("typicalRangeHigh"))


def choose(cands: pd.DataFrame, client, fm_by_ref: dict, hindex: dict) -> dict | None:
    """The first candidate, in the given order, with a Hydrology series and an EA usual range."""
    for u in cands.itertuples():
        st = fm_by_ref.get(u.up, {"stationReference": u.up})
        hu = rr.hydrology_for(st, hindex)
        if not hu:
            continue
        lo, hi = stage_range(client, st)
        if lo is None or hi is None or not hi > lo:
            continue
        return {"up": u.up, "up_label": u.up_label, "up_river": u.up_river, "along_km": u.along_km,
                "area_ratio": u.area_ratio, "low": lo, "high": hi, "measure": hu["measure"],
                "lat": float(st["lat"]), "lon": float(st["long"])}
    return None


def run(args) -> dict:
    from dipcast.ingest.rainfall import cell_key, grid_cell
    from dipcast.model import transport as T
    from dipcast.network.names import same_river
    from dipcast.network.rivers import RiverNetwork, lonlat_to_bng

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from glofas_check import catchment_at, km

    client = rr.CappedClient(args.cache, args.fetch)
    out = args.out
    (out / "series").mkdir(parents=True, exist_ok=True)
    summary: dict = {"stopped": None, "started": datetime.now(UTC).isoformat(timespec="seconds")}
    net = RiverNetwork.load(args.network)
    try:
        # 1. spot -> the site's gauge (the coverage run's requests, so its cache answers them)
        picks = []
        for r in rr.spots_frame().itertuples(index=False):
            if r.kind != "river":
                continue
            kind, river_hint = T.spot_hints(r.kind, r.river)
            pin = T.locate_pin(net, float(r.lon), float(r.lat), kind_hint=kind, river_hint=river_hint, name=r.name)
            river = r.river or pin.watercourse
            with rr.routed(client):
                try:
                    p = flows.station_pick(float(r.lat), float(r.lon), rr.SPOT_GAUGE_KM, river or None)
                except httpx.HTTPStatusError:
                    continue
            if p is None or not river or same_river(river, p["river"]) is not True:
                continue
            if None in (p["typical_low"], p["typical_high"]) or not p["typical_high"] > p["typical_low"]:
                continue
            picks.append({"spot": r.id, "gauge": p["ref"], "label": p["station"], "river": p["river"],
                          "lat": p["lat"], "lon": p["lon"], "low": p["typical_low"], "high": p["typical_high"]})
        spots = pd.DataFrame(picks)
        gauges = spots.drop_duplicates("gauge").set_index("gauge")

        # 2. every level station; the ones upstream of each spot gauge
        fm = client.get_json(f"{FM}/id/stations", {"parameter": "level", "type": "SingleLevel", "_limit": 10000})
        fm_items = [s for s in (fm or {}).get("items", [])
                    if isinstance(s.get("lat"), (int, float)) and isinstance(s.get("long"), (int, float))]
        fm_by_ref = {s.get("stationReference"): s for s in fm_items}
        near = [s for s in fm_items if any(km(s["lat"], s["long"], g.lat, g.lon) <= rr.UP_MAX_KM for g in gauges.itertuples())]
        snaps = {}
        for s in near + [{"stationReference": g, "lat": row.lat, "long": row.lon} for g, row in gauges.iterrows()]:
            x, y = lonlat_to_bng(float(s["long"]), float(s["lat"]))
            sn = net.snap_xy(x, y, max_m=rr.GAUGE_SNAP_M, forms=rr.RIVER_FORMS)
            if sn is not None:
                snaps[s.get("stationReference")] = (sn.link_id, sn.frac)
        near_by_ref = {s.get("stationReference"): s for s in near}
        ups = []
        for g, row in gauges.iterrows():
            if g not in snaps:
                continue
            area_g = catchment_at(net, *snaps[g])
            cands = {ref: snaps[ref] for ref, s in near_by_ref.items()
                     if ref != g and ref in snaps and km(s["lat"], s["long"], row.lat, row.lon) <= rr.UP_MAX_KM}
            for ref, d in sorted(rr.upstream_of(net, snaps[g], cands, rr.UP_MAX_KM * 1000).items()):
                if d < rr.SAME_SITE_KM * 1000:
                    continue
                s = near_by_ref[ref]
                area_u = catchment_at(net, *snaps[ref])
                ups.append({"gauge": g, "up": ref, "up_label": s.get("label"), "up_river": rr.name_of(s.get("riverName")),
                            "lat": float(s["lat"]), "lon": float(s["long"]), "along_km": round(d / 1000, 2),
                            "area_ratio": round(area_u / area_g, 3) if area_g else None,
                            "same_name": bool(same_river(rr.name_of(s.get("riverName")), rr.name_of(row.river)))})
        ups_df = pd.DataFrame(ups, columns=["gauge", "up", "up_label", "up_river", "lat", "lon", "along_km",
                                            "area_ratio", "same_name"])
        ups_df["area_ratio"] = pd.to_numeric(ups_df["area_ratio"], errors="coerce")

        # 3. Hydrology series; the two chosen upstream gauges; the river system; the radar cells
        hy = client.get_json(f"{HY}/id/stations.json", {"observedProperty": "waterLevel", "_limit": 10000})
        hindex = rr.hydrology_index((hy or {}).get("items", []))
        rows, slots, cells = [], [], []
        for g, row in gauges.iterrows():
            hd = rr.hydrology_for(fm_by_ref.get(g, {"stationReference": g}), hindex)
            mine = ups_df[ups_df["gauge"] == g]
            why = "" if hd else "no Hydrology series"
            if not why and g not in snaps:
                why = "spot gauge not on a river link"
            if not why and mine.empty:
                why = "no upstream gauge"
            chosen = {}
            if not why:
                same = mine[mine["same_name"] & (mine["along_km"] >= rr.PAIR_MIN_KM)
                            & (mine["area_ratio"] >= rr.PAIR_MIN_AREA)].sort_values(["along_km", "up"])
                trib = mine[~mine["same_name"]].sort_values(["area_ratio", "along_km", "up"], ascending=[False, True, True])
                for slot, cand in (("same", same), ("trib", trib)):
                    c = choose(cand, client, fm_by_ref, hindex)
                    if c:
                        chosen[slot] = c
                        slots.append({"gauge": g, "slot": slot, **c})
                if not chosen:
                    why = "no upstream gauge with a series and a range"
            system = pr.outlet(net.graph, net.links.at[snaps[g][0], "end_node"], net.upstream_m) if g in snaps else None
            rows.append({"gauge": g, "label": row.label, "river": row.river, "lat": row.lat, "lon": row.lon,
                         "low": row.low, "high": row.high, "measure": hd["measure"] if hd else None,
                         "system": system, "spots": ";".join(spots.loc[spots["gauge"] == g, "spot"].astype(str)),
                         "paired": "same" in chosen, "why": why})
            if not why:
                for lat, lon in [(row.lat, row.lon)] + list(zip(mine["lat"], mine["lon"], strict=True)):
                    c = grid_cell(lat, lon)
                    k = cell_key(float(c[0]), float(c[1]))
                    cells.append({"gauge": g, "cell": k, "cell_lat": float(c[0]), "cell_lon": float(c[1]),
                                  "saved_months": len(list(args.radar.glob(f"radar_{k}_*.parquet"))) if args.radar else 0})
        gauges_df = pd.DataFrame(rows)
        slots_df = pd.DataFrame(slots)
        cells_df = pd.DataFrame(cells).drop_duplicates(["gauge", "cell"]) if cells else pd.DataFrame()
        gauges_df.to_csv(out / "gauges.csv", index=False)
        slots_df.to_csv(out / "slots.csv", index=False)
        ups_df.to_csv(out / "upstream.csv", index=False)
        cells_df.to_csv(out / "radar_cells.csv", index=False)

        # 4. the readings, one request a series
        used = gauges_df[gauges_df["why"] == ""]
        measures = sorted(set(used["measure"].dropna()) | set(slots_df.get("measure", pd.Series(dtype=str)).dropna()))
        start, end = pr.FETCH_FROM.strftime("%Y-%m-%d"), pr.TEST[1].strftime("%Y-%m-%d")
        done = 0
        for m in measures:
            dest = out / "series" / f"{m}.parquet"
            status, text = client.get(f"{HY}/id/measures/{m}/readings.csv",
                                      {"mineq-date": start, "max-date": end, "_limit": READINGS_LIMIT})
            df = rr.read_csv_readings(text) if status == 200 else rr.read_csv_readings("")
            if len(df) >= READINGS_LIMIT:
                raise rr.Stop(f"{m}: {len(df)} rows, at the limit asked; the series may be cut")
            s = rr.to_grid(df, start, end)
            s.rename("value").rename_axis("time").reset_index().to_parquet(dest, index=False)
            done += 1
    except rr.Stop as e:
        summary.update(stopped=str(e), requests_this_run=client.n)
        (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        print(f"stopped: {e}\nrun again to resume from the cache", file=sys.stderr)
        raise SystemExit(2) from None

    summary.update({
        "spot_gauges_usable": int(len(gauges_df)), "why": gauges_df["why"].replace("", "used").value_counts().to_dict(),
        "gauges_used": int(len(used)), "gauges_paired": int(used["paired"].sum()),
        "with_trib": int(slots_df[slots_df["slot"] == "trib"]["gauge"].nunique()) if len(slots_df) else 0,
        "systems": int(used["system"].nunique()), "series": done,
        "gauges_with_radar": int(cells_df[cells_df["saved_months"] > 0]["gauge"].nunique()) if len(cells_df) else 0,
        "requests_this_run": client.n, "finished": datetime.now(UTC).isoformat(timespec="seconds")})
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=Path, required=True, help="answers are kept here (outside git)")
    ap.add_argument("--out", type=Path, required=True, help="tables and series (outside git)")
    ap.add_argument("--network", type=Path, default=config.PROCESSED / "river_network.pkl")
    ap.add_argument("--radar", type=Path, default=config.RAW / "met_office_radar", help="saved radar months, read only")
    ap.add_argument("--fetch", action="store_true", help="ask the EA for what is not cached, within the caps")
    args = ap.parse_args(argv)
    if datetime.now(UTC) < pr.NOT_BEFORE and args.fetch:
        raise SystemExit(f"the plan runs no earlier than {pr.NOT_BEFORE:%d %B %Y}")
    if args.radar and not args.radar.exists():
        args.radar = None
    run(args)


if __name__ == "__main__":
    main()
