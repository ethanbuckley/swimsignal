"""Model inputs for river samples, built as the bench builds them (docs/RIVER-UNSEEN-PROTOCOL-2026-11.md, amendment 1,
section 7): rain in the 48 and 24 hours before each sample and the lead-0 hindcast exposure, through
`lake_range_hindcast.build_rows` unchanged. Offline, in a scratch root, with the rain cache it should read:

    export DIPCAST_ROOT=<scratch copy of data/> DIPCAST_STATE=<scratch>/state DIPCAST_CACHE=<ERA5-Land cells>/cache
    python scripts/river_unseen/build_rows.py points <samples.parquet> docs/river-unseen/points.csv \\
        docs/river-unseen/systems.csv <out.parquet> [held_out|development]
    python scripts/river_unseen/build_rows.py bathing <bench seen.parquet> <out.parquet>

`points` joins sample results to inputs. It is part of the read: run it only after the candidate's hash is
committed. It prints counts and drops, never a result. `bathing` rebuilds the bench's seen river rows on the rain
cache in use (for `river-range-v0e`); those samples are already seen."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/London"
RESULT = re.compile(r"^\s*([<>]?)\s*=?\s*([0-9]+(?:\.[0-9]+)?)\s*$")


def parse_result(text) -> tuple[float, str]:
    """A result as (value, qualifier): "<10" is (10, "<"), ">20000" is (20000, ">"), "350" is (350, "=").
    (nan, "") for anything else."""
    m = RESULT.match(str(text))
    return (float(m.group(2)), m.group(1) or "=") if m else (np.nan, "")


def one_per_point_and_time(s: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Amendment 1, section 4: of rows sharing a point and time, equal results keep one, unequal keep the higher."""
    dup = s.duplicated(["point", "time"], keep=False)
    groups = s[dup].groupby(["point", "time"])["ecoli"].nunique()
    kept = s.sort_values("ecoli", ascending=False).drop_duplicates(["point", "time"]).sort_index()
    return kept, {"groups_equal": int((groups == 1).sum()), "groups_unequal": int((groups > 1).sum()),
                  "rows_dropped": int(len(s) - len(kept))}


def point_samples(samples: pd.DataFrame, points: pd.DataFrame, systems: pd.DataFrame, span: str) -> tuple[pd.DataFrame, dict]:
    """The kept rows of `span` at kept points, shaped as build_rows wants them."""
    kp = points[points["kept_point"]].set_index("point")
    s = samples[samples["kept"] & (samples["span"] == span) & samples["point"].isin(kp.index)].copy()
    parsed = s["result"].map(parse_result)
    s["ecoli"], s["ecoli_qual"] = [p[0] for p in parsed], [p[1] for p in parsed]
    audit = {"rows": int(len(s)), "unparsed_results": int(s["ecoli"].isna().sum())}
    s = s.dropna(subset=["ecoli"])
    s, audit["same_point_and_time"] = one_per_point_and_time(s)
    s["sample_time"] = pd.to_datetime(s["time"].str.slice(0, 19)).dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT")
    audit["times_not_placeable"] = int(s["sample_time"].isna().sum())
    s = s.dropna(subset=["sample_time"])
    s["day"] = s["sample_time"].dt.floor("D")
    sysm = systems.set_index("point")
    out = pd.DataFrame({"bw_id": s["point"], "name": s["point"].map(kp["label"]), "kind": "river",
                        "lat": s["point"].map(kp["lat"]), "lon": s["point"].map(kp["lon"]),
                        "sample_time": s["sample_time"], "day": s["day"], "ecoli": s["ecoli"],
                        "ecoli_qual": s["ecoli_qual"], "purpose": s["purpose_code"],
                        "system": s["point"].map(sysm["system"]), "band": s["point"].map(sysm["band"])})
    return out.reset_index(drop=True), audit


def bathing_samples(seen: pd.DataFrame) -> pd.DataFrame:
    """The bench's seen river samples, without their old inputs."""
    assert set(seen["part"]) == {"seen"}, "seen rows only"
    r = seen[seen["kind"] == "river"]
    return r[["bw_id", "name", "kind", "lat", "lon", "sample_time", "day", "ecoli", "ecoli_qual"]].reset_index(drop=True)


def point_up(net, ov, bw_id: str, lat: float, lon: float):
    """A sampling point's pin and upstream overflows: a river pin at its position, the bench's velocity."""
    from dipcast.model.transport import locate_pin, river_velocity, upstream_overflows
    pin = locate_pin(net, lon, lat, kind_hint="river")
    return pin, upstream_overflows(net, pin, ov, velocity_ms=river_velocity(None))


def build(samples: pd.DataFrame, at_points: bool) -> tuple[pd.DataFrame, dict]:
    assert all(k in os.environ for k in ("DIPCAST_ROOT", "DIPCAST_STATE", "DIPCAST_CACHE")), \
        "set a scratch DIPCAST_ROOT and DIPCAST_STATE, and DIPCAST_CACHE to the rain cache to read"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import lake_range_hindcast as lrh
    from validate_ecoli import load_rain

    from dipcast.model.ecoli import THRESHOLD, features
    from dipcast.model.features import daily_rain_features
    from dipcast.model.spill_model import SpillModel
    from dipcast.network.rivers import RiverNetwork
    from dipcast.overflows import load_overflows
    if at_points:
        lrh._site_up = point_up   # build_rows itself is unchanged: only where a site's pin comes from
    net = RiverNetwork.load()
    ov = load_overflows(net)
    rain = load_rain()
    hourly = rain.set_index(["cell_lat", "cell_lon"]).sort_index()
    rows, drops = lrh.build_rows(samples, net, ov, SpillModel.load(), hourly, daily_rain_features(rain))
    x = features(rows["rain_48h"], rows["rain_24h"], rows["risk_model"], np.zeros(len(rows)), rows["sample_time"])
    rows = pd.concat([rows.reset_index(drop=True), x.drop(columns=["lake"])], axis=1)
    rows["season"], rows["month"] = rows["sample_time"].dt.year, rows["sample_time"].dt.month
    rows["over"] = (rows["ecoli"] > THRESHOLD).astype(int)
    rows["log_ecoli"] = np.log10(rows["ecoli"].clip(lower=1))
    return rows, {"samples_in": int(len(samples)), "rows_out": int(len(rows)), "sites_out": int(rows["bw_id"].nunique()),
                  "drops": drops, "rain_cache": os.environ["DIPCAST_CACHE"]}


def main(argv: list[str]) -> None:
    if argv[0] == "points":
        samples, audit = point_samples(pd.read_parquet(argv[1]), pd.read_csv(argv[2]), pd.read_csv(argv[3]),
                                       argv[5] if len(argv) > 5 else "held_out")
        out = Path(argv[4])
    else:
        samples, audit, out = bathing_samples(pd.read_parquet(argv[1])), {}, Path(argv[2])
    rows, built = build(samples, at_points=argv[0] == "points")
    rows.to_parquet(out, index=False)
    audit.update(built)
    audit["rows_by_season"] = {str(int(k)): int(v) for k, v in rows.groupby("season").size().items()}
    out.with_suffix(".audit.json").write_text(json.dumps(audit, indent=1) + "\n")
    print(json.dumps(audit, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
